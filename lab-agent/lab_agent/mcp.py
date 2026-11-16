"""Install and launch the pinned Proxmox MCP server (ry-ops/proxmox-mcp-server).

Selection and review notes: lab-agent/docs/mcp-server-review.md.
The server is installed from one reviewed commit with its own frozen ``uv.lock``; the
launcher passes the token through the server's environment only, never through
``.mcp.json``, and always sets a CA bundle so TLS is verified against the cluster CA.

Trust model of this module (offline-tested only, see the review document):

* Every path that is used after the working directory changes is made absolute first.
* ``git`` and ``uv`` are looked up in the caller's ``PATH`` only if every entry is absolute.
  The symlink-resolved target is what is checked and what is run. It is refused when it
  resolves inside the install or run directory, or when it or any directory above it up to
  ``/`` belongs to someone other than root or this user or is writable by group or others (a
  sticky directory owned by root, such as ``/tmp``, is allowed). The ``PATH`` is still chosen
  by the caller: a trusted-looking directory the caller controls is not detected.
* ``<state>/mcp`` is validated (private, not a symlink) on every install and every launch,
  before git or the project is used.
* ``git`` and ``uv`` run with an allow-listed environment, so ``GIT_DIR`` and similar
  variables of the caller cannot redirect them. User ``uv`` configuration files are still read.
"""

from __future__ import annotations

import os
import stat
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from .config import Config, ConfigError, open_private_dir, open_private_subdir

PIN = {
    "repo": "https://github.com/ry-ops/proxmox-mcp-server.git",
    "commit": "69686b06347c89d85c3725cf4a730c979b0148b7",
    "version": "2.14.0",
    "license": "MIT",
}
# API areas the routine agent needs. Not loaded: access, firewall, disks, ceph, acme, sdn,
# notifications, appliances, lxc, pdm.
TOOLSETS = "nodes,qemu,storage,pools,cluster"
# The server expands protected ranges into a set and rejects a range with ``hi - lo > 100_000``.
# Each range built here spans _GUARD_SPAN IDs, which is inside that limit.
_GUARD_SPAN = 100_000
# Proxmox VE accepts guest IDs from 100 to 999,999,999.
_MIN_VMID = 100
_MAX_VMID = 999_999_999

# Variables copied to the server, and to git and uv. HOME and TMPDIR only when absolute.
_PASS = ("HOME", "LANG", "TMPDIR")
# Also copied to git and uv, never to the server: network settings for the install.
_NETWORK = ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY", "https_proxy", "http_proxy",
            "all_proxy", "no_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR")


def _state(cfg: Config) -> Path:
    """The state directory as an absolute path (resolved against the caller's directory)."""
    return Path(os.path.abspath(cfg.state_dir()))


def install_dir(cfg: Config) -> Path:
    """``<state>/mcp/proxmox-mcp-server-<commit>``, absolute. The layout matters:
    ``installed_commit`` derives the directories it must not take programs from."""
    return _state(cfg) / "mcp" / f"proxmox-mcp-server-{PIN['commit'][:12]}"


def protected_vmids(lo: int, hi: int) -> str:
    """IDs on both sides of the project range, so MCP write tools refuse them.

    Defence in depth for VMID hygiene only; Proxmox RBAC remains the boundary. IDs more
    than 100,000 away from the range are not covered (server limit). A side that would lie
    outside the Proxmox ID space (below 100 or above 999,999,999) is left out, so a range
    that touches an end of the space yields one range, and a range that fills it yields "".
    """
    parts = []
    if lo > _MIN_VMID:
        parts.append(f"{max(_MIN_VMID, lo - _GUARD_SPAN)}-{lo - 1}")
    if hi < _MAX_VMID:
        parts.append(f"{hi + 1}-{min(_MAX_VMID, hi + _GUARD_SPAN)}")
    return ",".join(parts)


# --- executables and environments ------------------------------------------------------------

def _within(candidate: str, root: Path) -> bool:
    real, base = os.path.realpath(candidate), os.path.realpath(root)
    return real == base or real.startswith(base + os.sep)


def checked_path(path_value: str | None, roots: Sequence[Path]) -> list[str]:
    """The entries of a PATH value, or ConfigError.

    Refused: an unset or empty value, an empty entry (it means the current directory), a
    relative entry, and an entry that resolves inside one of ``roots``. The message never
    echoes the value."""
    if not path_value:
        raise ConfigError("PATH is not set; refusing to look up git or uv")
    entries = path_value.split(os.pathsep)
    for entry in entries:
        if not entry or not os.path.isabs(entry):
            raise ConfigError("PATH holds an empty or relative entry; refusing to look up git or uv")
        if any(_within(entry, root) for root in roots):
            raise ConfigError("PATH holds an entry inside the lab-agent install or run directory")
    return entries


def _untrusted(st: os.stat_result) -> bool:
    return st.st_uid not in (0, os.getuid()) or bool(st.st_mode & (stat.S_IWGRP | stat.S_IWOTH))


def _require_private(name: str, real: str) -> None:
    """``real`` (already resolved, so no symlink is involved) must be a regular file that only root
    or this user owns and nobody else can write, and so must **every** directory above it up to
    ``/``. The one exception is a sticky directory owned by root (such as ``/tmp``): others can
    create entries in it but cannot rename or remove ours."""
    st = os.stat(real)
    if not stat.S_ISREG(st.st_mode):
        raise ConfigError(f"{name} is not a regular file")
    if _untrusted(st):
        raise ConfigError(f"{name}: its file is owned by another user or writable by group or others")
    directory = os.path.dirname(real)
    while True:
        dst = os.stat(directory)
        if not (dst.st_uid == 0 and dst.st_mode & stat.S_ISVTX) and _untrusted(dst):
            raise ConfigError(f"{name}: its directory (or one above it) is owned by another user or "
                              "writable by group or others")
        parent = os.path.dirname(directory)
        if parent == directory:
            return
        directory = parent


def find_executable(name: str, path_value: str | None, roots: Sequence[Path]) -> str:
    """The first ``name`` on a checked PATH, as the absolute path of its **resolved target**.

    The caller executes exactly the path that was checked: a symlink in a PATH directory that
    is replaced afterwards changes nothing, because the symlink is not what is run. Raises
    ConfigError when it is not found, when the target is inside one of ``roots``, or when the
    target or any directory above it is not private (see ``_require_private``). A program that
    needs its own name to behave (a multi-call binary) is not supported."""
    for entry in checked_path(path_value, roots):
        candidate = os.path.join(entry, name)
        if not (os.path.isfile(candidate) and os.access(candidate, os.X_OK)):
            continue
        real = os.path.realpath(candidate)
        if any(_within(real, root) for root in roots):
            raise ConfigError(f"{name} resolves inside the lab-agent install or run directory; refusing")
        _require_private(name, real)
        return real
    raise ConfigError(f"{name} not found on PATH")


def _base_env(base: Mapping[str, str], path_entries: Sequence[str] | None) -> dict[str, str]:
    env = {} if path_entries is None else {"PATH": os.pathsep.join(path_entries)}
    for key in _PASS:
        value = base.get(key)
        if value is not None and (key == "LANG" or os.path.isabs(value)):
            env[key] = value
    return env


def tool_env(base: Mapping[str, str], path_entries: Sequence[str], network: bool = True) -> dict[str, str]:
    """An allow-listed environment for git and uv. Nothing named GIT_* or UV_* is inherited,
    and git reads no system or user configuration (the user-level switch needs git 2.32)."""
    env = _base_env(base, path_entries)
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"})
    if network:
        env.update({k: base[k] for k in _NETWORK if k in base})
    return env


def server_env(cfg: Config, base: Mapping[str, str]) -> dict[str, str]:
    """The environment of the server process. Every path in it is absolute."""
    lo, hi = cfg.vmid_range()
    user, token_name = cfg.token_id().split("!", 1)
    ca = Path(os.path.abspath(cfg.path("PVE_CA_FILE")))
    if not ca.is_file():
        raise ConfigError("PVE_CA_FILE does not exist; copy /etc/pve/pve-root-ca.pem first")
    state = _state(cfg)
    env = _base_env(base, checked_path(base["PATH"], [state / "mcp", state / "mcp-run"]) if "PATH" in base else None)
    env.update({
        "PROXMOX_HOST": cfg.host(),  # validated: a malformed setting never reaches the server
        "PROXMOX_PORT": str(cfg.port()),
        "PROXMOX_USER": user,
        "PROXMOX_TOKEN_NAME": token_name,
        "PROXMOX_TOKEN_VALUE": cfg.token_secret(),
        # Set empty so a stray .env cannot supply a password: python-dotenv never overrides a
        # variable that is already set.
        "PROXMOX_PASSWORD": "",
        "PROXMOX_CA_BUNDLE": str(ca),
        "PROXMOX_TOOLSETS": TOOLSETS,
        "PROXMOX_PROTECTED_VMIDS": protected_vmids(lo, hi),
        "PROXMOX_AUDIT_LOG": str(state / "mcp-audit.jsonl"),
    })
    return env


# --- install and launch ----------------------------------------------------------------------

def installed_commit(path: Path, environ: Mapping[str, str] | None = None) -> str | None:
    """``HEAD`` of the checkout at ``path``, or None when there is no usable checkout.

    ``.git`` must be a real directory (not a file or symlink that redirects git elsewhere).
    git is the trusted one from ``find_executable`` and runs with ``tool_env``, so the
    caller's GIT_DIR, GIT_WORK_TREE and friends cannot point it at another repository.
    ConfigError when PATH or git is not trustworthy."""
    environ = os.environ if environ is None else environ
    path = Path(os.path.abspath(path))
    gitdir = path / ".git"
    if gitdir.is_symlink() or not gitdir.is_dir():
        return None
    roots = [path.parent, path.parent.parent / "mcp-run"]
    git = find_executable("git", environ.get("PATH"), roots)
    env = tool_env(environ, checked_path(environ.get("PATH"), roots), network=False)
    try:
        out = subprocess.run([git, "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True, env=env)
    except OSError:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _step(label: str, cmd: list[str], env: Mapping[str, str]) -> None:
    """Run one install step. A failure to run it, or a non-zero exit, becomes ConfigError
    naming the step. The message holds neither the command line nor the program's output;
    the program's own stdout and stderr are inherited and appear unfiltered on the terminal."""
    try:
        subprocess.run(cmd, check=True, env=dict(env))
    except subprocess.CalledProcessError as exc:
        raise ConfigError(f"{label} failed (exit {exc.returncode})") from None
    except OSError as exc:
        raise ConfigError(f"{label}: could not run ({exc.strerror or type(exc).__name__})") from None


def install(cfg: Config) -> Path:
    path = install_dir(cfg)
    roots = [path.parent, path.parent.parent / "mcp-run"]
    base = os.environ
    _private_subdir(path.parent.parent, path.parent.name)  # always, also for an installed checkout
    git = find_executable("git", base.get("PATH"), roots)
    uv = find_executable("uv", base.get("PATH"), roots)
    env = tool_env(base, checked_path(base.get("PATH"), roots))
    if installed_commit(path, base) != PIN["commit"]:
        if not path.exists():
            _step("git clone", [git, "clone", "--quiet", "--no-checkout", PIN["repo"], str(path)], env)
        _step("git checkout", [git, "-C", str(path), "-c", "advice.detachedHead=false", "checkout", "--quiet",
                               "--detach", PIN["commit"]], env)
        if installed_commit(path, base) != PIN["commit"]:
            raise ConfigError("checked-out commit does not match the pin")
    _step("uv sync", [uv, "sync", "--frozen", "--no-dev", "--project", str(path)], env)
    return path


def _private_subdir(parent: Path, name: str) -> None:
    """Create ``parent/name`` as a private directory (700 whatever the umask; a symlink, another
    owner or another mode is refused), through descriptors."""
    parent_fd = open_private_dir(parent)
    try:
        os.close(open_private_subdir(parent_fd, name, name))
    finally:
        os.close(parent_fd)


def _check_install_parent(state: Path) -> bool:
    """Validate ``<state>/mcp`` without creating it: False when it does not exist, ConfigError
    when it is a symlink, belongs to another user or has a mode other than 700."""
    state_fd = open_private_dir(state)
    try:
        try:
            os.lstat("mcp", dir_fd=state_fd)
        except FileNotFoundError:
            return False
        os.close(open_private_subdir(state_fd, "mcp", "mcp", create=False))
        return True
    finally:
        os.close(state_fd)


def open_run_dir(cfg: Config) -> int:
    """Open the private working directory of the server process and return its descriptor.

    It is created if missing (mode 700) and must be a real directory of this user with mode 700
    exactly (see ``config.open_private_subdir``) holding no ``.env*`` entry. It is not required
    to be empty: what the server itself may write there is unobserved. python-dotenv's search
    starts from the calling file, not from here (not verified on this machine), so this is a
    second line of defence. The caller closes the descriptor."""
    state_fd = open_private_dir(_state(cfg))
    try:
        fd = open_private_subdir(state_fd, "mcp-run", "mcp-run")
    finally:
        os.close(state_fd)
    try:
        if any(name.startswith(".env") for name in os.listdir(fd)):
            raise ConfigError("mcp-run holds an .env file; remove it")
    except BaseException:
        os.close(fd)
        raise
    return fd


def run_dir(cfg: Config) -> Path:
    """The (absolute) path of the directory ``open_run_dir`` checks; for messages and tests."""
    os.close(open_run_dir(cfg))
    return _state(cfg) / "mcp-run"


def launch(cfg: Config) -> None:
    """Replace this process with the MCP server (stdio).

    Everything that depends on the caller's working directory (state, CA and install paths,
    the token file) is resolved before the directory changes."""
    path = install_dir(cfg)
    state = _state(cfg)
    # The install parent is checked before git or the project is used, installed or not.
    if not _check_install_parent(state) or installed_commit(path) != PIN["commit"]:
        raise ConfigError("pinned MCP server not installed; run: lab-agent/bin/lab-agent mcp-install")
    env = server_env(cfg, os.environ)
    uv = find_executable("uv", os.environ.get("PATH"), [state / "mcp", state / "mcp-run"])
    fd = open_run_dir(cfg)  # a dedicated directory with no .env, never the caller's
    try:
        os.fchdir(fd)  # by descriptor: the path cannot be swapped after the check
    finally:
        os.close(fd)
    os.execve(uv, ["uv", "run", "--frozen", "--no-sync", "--project", str(path), "proxmox-mcp-server"], env)
