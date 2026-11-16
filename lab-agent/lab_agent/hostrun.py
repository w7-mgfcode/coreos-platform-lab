"""host-run: the owner-executed path for privileged work on the Proxmox host (Mode B).

What it does:
  1. renders one complete bash script from a fixed action file (or a validated cleanup
     manifest), the shared helpers and shell-quoted parameters;
  2. shows the whole script, its sha256 and what changed since the owner last approved
     this action;
  3. runs it only after the owner types the first 8 characters of that sha256 on a TTY;
  4. runs it over ssh with the passphrase-protected root key, with no ssh-agent, no
     connection sharing and no forwarding; the passphrase is typed into ssh, not here.

What it does NOT prove (stated so nobody mistakes it for a stronger boundary):
  * Git state proves nothing about review, so it is not used as an approval signal.
  * The approval record lives under the owner's user like everything else; the agent
    could edit it. It only powers the "changed since last approval" display. The gate is
    the human reading the script and typing the hash prefix at run time.
  * The TTY and Claude-ancestry checks stop accidental runs by an agent; they are not a
    security boundary against code running as the same OS user.
  * ptrace_scope=1 keeps non-descendant processes from reading ssh's memory, but the same
    user can still, for example, drive a terminal pane. Run host-run in a terminal no agent
    controls.
"""

from __future__ import annotations

import datetime as dt
import difflib
import errno
import hashlib
import json
import os
import re
import secrets
import shlex
import socket
import stat
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from . import classify as cl
from . import config as cv
from . import inventory as inv
from . import manifest as mf
from .config import (Config, ConfigError, check_private_file, is_refusal, open_private_dir,
                     open_private_subdir)
from .redact import SecretScrubber, redact, redact_uuids

AGENT_DIR = Path(__file__).resolve().parent.parent
HOST_DIR = AGENT_DIR / "host"

# The owner-path ssh connection uses port 22 and nothing else. There is deliberately no
# setting for it: a different port would be one more value that reaches a command line. A
# PVE_HOST that carries a port, and a PVE_SSH_PORT line in the settings file, are refused
# with a message that says so (config.validate_host, config.parse_env_text).
SSH_PORT = 22

_PUBKEY = re.compile(r"^(ssh-ed25519|sk-ssh-ed25519@openssh\.com|ecdsa-sha2-nistp(256|384|521)) [A-Za-z0-9+/]+={0,3}$")
TOKEN_LINE = "CORELAB_TOKEN_SECRET="


@dataclass(frozen=True)
class Action:
    name: str
    params: tuple[tuple[str, str], ...]  # (script variable, config key)
    output: str = "terminal"              # terminal | token | file:<suffix>
    summary: str = ""


ACTIONS: dict[str, Action] = {a.name: a for a in (
    Action("preflight", (), summary="read-only: versions, fingerprints, root login settings"),
    Action("bootstrap", (("CL_EXPIRE_DAYS", "PVE_TOKEN_EXPIRE_DAYS"),), output="token",
           summary="create the routine user and a read-only token"),
    Action("discover-host", (), output="file:discover-host.txt",
           summary="read-only: disks, network files, sshd, apt sources"),
    Action("backup-config", (), output="file:host-config.tar.gz",
           summary="read-only: tar.gz of the host configuration"),
    Action("prepare", (("CL_POOL", "PVE_POOL"), ("CL_LAB_STORAGE", "PVE_LAB_STORAGE"),
                       ("CL_LAB_STORAGE_PATH", "PVE_LAB_STORAGE_PATH"), ("CL_VM_STORAGE", "PVE_VM_STORAGE"),
                       ("CL_BRIDGE", "PVE_BRIDGE"), ("CL_WORKSTATION_ADDR", "PVE_WORKSTATION_ADDR")),
           summary="pool, project storage, snippet writer, routine ACLs (idempotent)"),
    Action("sentinel", (("CL_SENTINEL_VMID", "PVE_SENTINEL_VMID"), ("CL_VM_STORAGE", "PVE_VM_STORAGE"),
                        ("CL_SENTINEL_BACKUP_STORAGE", "PVE_SENTINEL_BACKUP_STORAGE"),
                        ("CL_LAB_STORAGE", "PVE_LAB_STORAGE"), ("CL_LAB_STORAGE_PATH", "PVE_LAB_STORAGE_PATH")),
           summary="BLOCKED in this version (run refuses; open review finding): fixtures for the negative RBAC tests"),
    Action("fcos-template", (("CL_TEMPLATE_VMID", "PVE_TEMPLATE_VMID"), ("CL_POOL", "PVE_POOL"),
                             ("CL_VM_STORAGE", "PVE_VM_STORAGE"), ("CL_LAB_STORAGE_PATH", "PVE_LAB_STORAGE_PATH"),
                             ("CL_BRIDGE", "PVE_BRIDGE"), ("CL_FCOS_IMAGE_URL", "FCOS_IMAGE_URL"),
                             ("CL_FCOS_IMAGE_SHA256", "FCOS_IMAGE_SHA256"),
                             # The project VMID block and the sentinel: the script can check the
                             # template VMID against them again on the host (CL_VMID_RANGE is "lo-hi").
                             ("CL_VMID_RANGE", "PVE_VMID_RANGE"), ("CL_SENTINEL_VMID", "PVE_SENTINEL_VMID")),
           summary="build the FCOS template inside the pool"),
    Action("apply-manifest", (("CL_POOL", "PVE_POOL"), ("CL_SENTINEL_VMID", "PVE_SENTINEL_VMID")),
           summary="DISABLED in this version (run refuses); show validates a manifest and prints a preview"),
)}

# Destructive execution is disabled in this version (owner decision of 2026-11-16). The cleanup
# manifest path stops, backs up in stop mode, destroys and frees; its safety is not established
# (open check-then-command window, unproven listing completeness and backing relationships,
# inactive storages) and it has never run on a real host. ``run`` still validates the request and
# lists the plan (so every refusal of a bad manifest, inventory or overrides file is unchanged) and
# then refuses, always: before the ssh arguments are built, before the state directory is touched,
# and before anything is rendered, shown for approval or sent. No setting, argument or value of
# ``env`` changes this in ``run``. ``show`` still validates and prints the script. That text is a
# preview, not something to apply by hand: its first command is ``cl_destructive_gate``
# (``host/lib.sh``), and the destructive commands themselves are not in it (the library carries them
# only as ``# DISABLED-COMMAND:`` comments), so even a shell whose ``exit`` has been replaced finds
# nothing destructive to run.
DESTRUCTIVE_ACTIONS = frozenset({"apply-manifest"})

# Actions ``run`` refuses in this version although they are not destructive: an independent review
# found a defect that is not fixed. ``show`` still prints them; a reason names the finding.
BLOCKED_ACTIONS = {
    "sentinel": ("sentinel is blocked in this version of the tooling: the script creates directories and the "
                 "dummy ISO under PVE_LAB_STORAGE_PATH without checking that this directory is the project "
                 "storage `prepare` made (its provenance record and marker) or that nothing is mounted at or "
                 "beneath it (an open blocking review finding, not fixed; see lab-agent/README.md). Nothing was "
                 "rendered, shown for approval or sent"),
}
DESTRUCTIVE_DISABLED = ("{action} is disabled in this version of the tooling: destructive execution (stop, "
                        "stop-mode backup, destroy, free) is not established as safe. The request was validated "
                        "and the plan listed; nothing was rendered, shown for approval or sent. Validation and "
                        "preview still work: `lab-agent manifest check`, `lab-agent manifest dry-run`, and "
                        "`show {action}`")


class HostRunError(Exception):
    pass


# --------------------------------------------------------------------------- parameters

TOKEN_EXPIRE_DAYS_MAX = 3650


def _project_range(cfg: Config) -> tuple[int, int] | None:
    return cfg.vmid_range() if cfg.has("PVE_VMID_RANGE") else None


def _sentinel_vmid(cfg: Config) -> int:
    """The sentinel's VMID: a real VMID (not 0, which protects nothing) outside the project range."""
    vmid = cv.validate_vmid("PVE_SENTINEL_VMID", cfg.get("PVE_SENTINEL_VMID"))
    span = _project_range(cfg)
    if span is not None and span[0] <= vmid <= span[1]:
        raise ConfigError("PVE_SENTINEL_VMID lies inside PVE_VMID_RANGE; the sentinel must be outside the project range")
    return vmid


def _template_vmid(cfg: Config) -> int:
    """The template's VMID: inside the project range, and never the sentinel."""
    vmid = cv.validate_vmid("PVE_TEMPLATE_VMID", cfg.get("PVE_TEMPLATE_VMID"))
    lo, hi = cfg.vmid_range()
    if not lo <= vmid <= hi:
        raise ConfigError(f"PVE_TEMPLATE_VMID must lie inside PVE_VMID_RANGE ({lo}-{hi})")
    if vmid == _sentinel_vmid(cfg):
        raise ConfigError("PVE_TEMPLATE_VMID equals PVE_SENTINEL_VMID")
    return vmid


_PARAM_CHECKS: dict[str, Callable[[Config], str]] = {
    "PVE_WORKSTATION_ADDR": lambda c: c.workstation_addr(),
    "PVE_TOKEN_EXPIRE_DAYS": lambda c: str(cv.validate_int("PVE_TOKEN_EXPIRE_DAYS", c.get("PVE_TOKEN_EXPIRE_DAYS"),
                                                           1, TOKEN_EXPIRE_DAYS_MAX)),
    "PVE_POOL": lambda c: cv.validate_pve_id("PVE_POOL", c.get("PVE_POOL")),
    "PVE_LAB_STORAGE": lambda c: cv.validate_pve_id("PVE_LAB_STORAGE", c.get("PVE_LAB_STORAGE")),
    "PVE_VM_STORAGE": lambda c: cv.validate_pve_id("PVE_VM_STORAGE", c.get("PVE_VM_STORAGE")),
    "PVE_SENTINEL_BACKUP_STORAGE": lambda c: cv.validate_pve_id("PVE_SENTINEL_BACKUP_STORAGE",
                                                                c.get("PVE_SENTINEL_BACKUP_STORAGE")),
    "PVE_BRIDGE": lambda c: cv.validate_bridge("PVE_BRIDGE", c.get("PVE_BRIDGE")),
    "PVE_LAB_STORAGE_PATH": lambda c: cv.validate_abs_path("PVE_LAB_STORAGE_PATH", c.get("PVE_LAB_STORAGE_PATH")),
    "PVE_SENTINEL_VMID": lambda c: str(_sentinel_vmid(c)),
    "PVE_TEMPLATE_VMID": lambda c: str(_template_vmid(c)),
    "PVE_VMID_RANGE": lambda c: "{}-{}".format(*c.vmid_range()),
    "FCOS_IMAGE_URL": lambda c: cv.validate_https_url("FCOS_IMAGE_URL", c.get("FCOS_IMAGE_URL")),
    "FCOS_IMAGE_SHA256": lambda c: cv.validate_sha256("FCOS_IMAGE_SHA256", c.get("FCOS_IMAGE_SHA256")),
}


def action_params(action: Action, cfg: Config) -> list[tuple[str, str]]:
    """The ``CL_*`` parameters of an action as (variable, validated value). Each value is checked
    by type before anything is rendered; a setting without a check is refused (fail closed), so
    a parameter added to an action cannot reach the root script unchecked. Raises ConfigError."""
    out = []
    for var, key in action.params:
        check = _PARAM_CHECKS.get(key)
        if check is None:
            raise HostRunError(f"{action.name}: no validation rule for {key}; refusing to export {var}")
        out.append((var, check(cfg)))
    return out


# --------------------------------------------------------------------------- rendering

def _heredoc_function(fname: str, content: str) -> str:
    marker = "CORELAB_EOF_" + hashlib.sha256(content.encode()).hexdigest()[:12].upper()
    if marker in content:
        raise HostRunError("embedded file contains its own heredoc marker")
    body = content if content.endswith("\n") else content + "\n"
    return f"{fname}() {{\ncat <<'{marker}'\n{body}{marker}\n}}\n"


def _snip_pubkey(cfg: Config) -> str:
    pub = Path(str(cfg.path("PVE_SNIP_KEY")) + ".pub")
    try:
        fields = pub.read_text(encoding="utf-8").split()
    except FileNotFoundError:
        raise HostRunError(f"{pub.name} not found; create the snippet key first") from None
    key = " ".join(fields[:2])
    if not _PUBKEY.match(key):
        raise HostRunError("snippet public key is not an ed25519/ecdsa public key")
    return key


def apply_classification(cfg: Config, inventory: dict[str, Any],
                         overrides: dict[str, dict[str, str]] | None) -> dict[str, dict[str, str]]:
    """Recompute the classification from the inventory and the owner's overrides.

    The privileged path never trusts a classification file: the rules (PRESERVE cannot be
    overridden, REMOVE_CANDIDATE needs written evidence) are applied again here."""
    return cl.classify(inventory, overrides=overrides, **cl.config_context(cfg))


def render(action_name: str, cfg: Config, manifest: dict[str, Any] | None = None, *,
           inventory: dict[str, Any] | None = None,
           overrides: dict[str, dict[str, str]] | None = None) -> str:
    """The exact script the host will execute. Nothing is added after this point.

    apply-manifest renders only after the full validation against ``inventory`` (the one
    the manifest was built from) and the classification recomputed with ``overrides``."""
    if action_name not in ACTIONS:
        raise HostRunError(f"unknown action {action_name!r}; known: {', '.join(sorted(ACTIONS))}")
    action = ACTIONS[action_name]
    classification = None
    if action.name == "apply-manifest":
        if manifest is None or inventory is None:
            raise HostRunError("apply-manifest needs --manifest, --inventory and --overrides")
        classification = apply_classification(cfg, inventory, overrides)
        mf.validate_for_apply(manifest, inventory, classification)
    q = shlex.quote
    user, token = cfg.token_id().split("!", 1)
    lines = ["set -euo pipefail", "umask 077", f"# corelab host-run action: {action.name}",
             f"export CL_USER={q(user)} CL_TOKEN={q(token)}"]
    # Every value is validated by type first (the workstation address goes into a from=
    # restriction, so it is a single validated IP); quoting is the second line of defence.
    for var, value in action_params(action, cfg):
        lines.append(f"export {var}={q(value)}")
    script = "\n".join(lines) + "\n\n" + (HOST_DIR / "lib.sh").read_text(encoding="utf-8") + "\n"
    if action.name == "prepare":
        lines_extra = [f"export CL_SNIP_PUBKEY={q(_snip_pubkey(cfg))}",
                       _heredoc_function("cl_file_snippet_writer",
                                         (HOST_DIR / "snippet-writer" / "corelab-snippet-put").read_text()),
                       _heredoc_function("cl_file_snippet_writer_conf",
                                         (HOST_DIR / "snippet-writer" / "snippet-writer.conf").read_text())]
        script += "\n".join(lines_extra) + "\n"
    if action.name == "apply-manifest":
        assert manifest is not None and inventory is not None and classification is not None
        script += mf.render_host_script(manifest, inventory, classification)
    else:
        if manifest is not None or inventory is not None or overrides is not None:
            raise HostRunError(f"{action.name} does not take a manifest, an inventory or overrides")
        script += (HOST_DIR / "actions" / f"{action.name}.sh").read_text(encoding="utf-8")
    return script


def script_hash(script: str) -> str:
    return hashlib.sha256(script.encode()).hexdigest()


# --------------------------------------------------------------------------- approval

def approvals_path(state: Path) -> Path:
    return state / "approvals.jsonl"


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _state_fd(state: Path, *, create: bool) -> int:
    try:
        return open_private_dir(state, create=create)
    except ConfigError as exc:
        raise HostRunError(str(exc)) from None


def _subdir_fd(parent_fd: int, name: str, parent: Path, *, create: bool) -> int:
    try:
        return open_private_subdir(parent_fd, name, parent / name, create=create)
    except ConfigError as exc:
        raise HostRunError(str(exc)) from None


def _read_regular(dir_fd: int, name: str) -> str | None:
    """Read ``name`` inside the directory ``dir_fd``. None when it does not exist. A symlink,
    or anything that is not a regular file of this user, is refused: the record would show the
    owner something the tool did not write."""
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dir_fd)
    except FileNotFoundError:
        return None
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise HostRunError(f"{name}: is a symlink; refusing to read it as a record") from None
        raise
    with os.fdopen(fd, "r", encoding="utf-8") as fh:
        st = os.fstat(fh.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
            raise HostRunError(f"{name}: not a regular file of this user; refusing to read it as a record")
        return fh.read()


def last_approved(state: Path, action: str) -> tuple[dict[str, Any] | None, str | None]:
    """Most recent approval record for the action and the script it approved, if kept."""
    if not os.path.lexists(state):
        return None, None
    dfd = _state_fd(state, create=False)
    try:
        record = None
        for line in (_read_regular(dfd, "approvals.jsonl") or "").splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict) and entry.get("action") == action:
                record = entry
        if record is None:
            return None, None
        sha = record.get("sha256")
        if not isinstance(sha, str) or not _SHA256.match(sha):
            return record, None  # never build a file name from a value that is not a hash
        try:
            os.lstat("approved", dir_fd=dfd)
        except FileNotFoundError:
            return record, None
        adfd = _subdir_fd(dfd, "approved", state, create=False)
        try:
            return record, _read_regular(adfd, f"{sha}.sh")
        finally:
            os.close(adfd)
    finally:
        os.close(dfd)


def review_text(action: str, script: str, state: Path) -> str:
    sha = script_hash(script)
    record, previous = last_approved(state, action)
    head = [f"action: {action} — {ACTIONS[action].summary}", f"sha256: {sha}"]
    if record is None:
        head.append("first run of this action: review the whole script below")
    elif record.get("sha256") == sha:
        head.append(f"unchanged since you approved it on {record.get('time')}")
    else:
        head.append(f"CHANGED since your approval on {record.get('time')}: diff follows, then the full script")
        if previous is not None:
            head += list(difflib.unified_diff(previous.splitlines(), script.splitlines(),
                                              "approved", "now", lineterm=""))
    numbered = [f"{n:4d}  {line}" for n, line in enumerate(script.splitlines(), start=1)]
    return "\n".join(head + ["", "----- script -----"] + numbered + ["----- end -----"])


def confirmation_matches(answer: str, sha: str) -> bool:
    return answer.strip().lower() == sha[:8]


def record_approval(state: Path, action: str, script: str, now: str | None = None) -> None:
    """Keep a copy of the approved script and append the approval record. Both go through the
    descriptor of the (private, checked) state directory and its ``approved`` subdirectory;
    neither follows a symlink."""
    sha = script_hash(script)
    dfd = _state_fd(state, create=True)
    try:
        adfd = _subdir_fd(dfd, "approved", state, create=True)
        try:
            name = f"{sha}.sh"
            try:
                _create_exclusive_at(adfd, name, script.encode())
            except FileExistsError:
                if not stat.S_ISREG(os.lstat(name, dir_fd=adfd).st_mode):
                    raise HostRunError(f"{name} exists and is not a regular file (symlink?); refusing") from None
        finally:
            os.close(adfd)
        entry = {"time": now or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                 "action": action, "sha256": sha}
        _append_private(dfd, approvals_path(state).name, (json.dumps(entry) + "\n").encode())
    finally:
        os.close(dfd)


def check_state_subdirs(state: Path) -> None:
    """Create ``approved/`` and ``runs/`` under the state directory as mode 700 when missing and
    refuse them (symlink, other owner, any other mode) when they exist, before anything is shown."""
    sfd = _state_fd(state, create=True)
    try:
        for name in ("approved", "runs"):
            os.close(_subdir_fd(sfd, name, state, create=True))
    finally:
        os.close(sfd)


def _append_private(dir_fd: int, name: str, data: bytes) -> None:
    """Append to ``name`` inside ``dir_fd``. A new file is created exclusively and set to mode
    600 before anything is written, whatever the umask. An existing one is used only if it is a
    regular file of this user, mode 600 exactly, with a single link (a second name for the same
    file would let this append corrupt that other file). Never through a symlink."""
    flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    created = False
    try:
        fd = os.open(name, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=dir_fd)
        created = True
    except FileExistsError:
        try:
            fd = os.open(name, flags, dir_fd=dir_fd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise HostRunError(f"{name}: is a symlink; refusing to append to it") from None
            if isinstance(exc, PermissionError):
                raise HostRunError(f"{name}: exists but cannot be opened for appending: expected 600 "
                                   "(chmod 600 it)") from None
            raise
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise HostRunError(f"{name}: is a symlink; refusing to append to it") from None
        raise
    with os.fdopen(fd, "ab") as fh:
        if created:
            os.fchmod(fh.fileno(), 0o600)  # the umask may have taken owner bits away
        st = os.fstat(fh.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
            raise HostRunError(f"{name}: not a regular file of this user; refusing to append to it")
        if st.st_nlink != 1:
            raise HostRunError(f"{name}: has {st.st_nlink} links; refusing to append to a file that is also "
                               "another name for something else")
        if st.st_mode & 0o777 != 0o600:
            raise HostRunError(f"{name}: mode {oct(st.st_mode & 0o777)}, expected 600 (chmod 600 it)")
        fh.write(data)
        fh.flush()


# --------------------------------------------------------------------------- guards

def running_under_agent(env: Mapping[str, str], ancestors: Iterable[str]) -> str | None:
    """Reason to refuse if this looks like an agent session; None otherwise.

    A usability guard against accidental runs, not a security boundary.
    """
    if env.get("CLAUDECODE"):
        return "CLAUDECODE is set: this is a Claude Code shell; run host-run in your own terminal"
    for name in ancestors:
        if name in ("claude", "claude-code") or name.startswith("claude"):
            return f"a parent process is {name!r}; run host-run in a terminal no agent started"
    return None


def process_ancestors(pid: int | None = None) -> list[str]:
    names = []
    pid = pid or os.getppid()
    for _ in range(64):
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
        except OSError:
            break
        name = stat[stat.index("(") + 1: stat.rindex(")")]
        ppid = int(stat[stat.rindex(")") + 2:].split()[1])
        names.append(name)
        if ppid <= 1:
            break
        pid = ppid
    return names


def check_root_key(path: Path, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> None:
    """The root key must be a private file and must be passphrase-protected."""
    try:
        check_private_file(path)
    except ConfigError as exc:
        raise HostRunError(f"root key: {exc}") from None
    # With an empty passphrase, ssh-keygen -y succeeds only for an unencrypted key.
    probe = runner(["ssh-keygen", "-y", "-P", "", "-f", str(path)],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if probe.returncode == 0:
        raise HostRunError("root key is NOT passphrase-protected; refusing (ssh-keygen -p to add one)")


def ssh_command(cfg: Config) -> list[str]:
    """``-F none``: no user or system ssh configuration, so nothing inherited (ProxyJump,
    ProxyCommand, BindInterface, another BindAddress) can defeat the explicit options.

    Host keys: only ``PVE_KNOWN_HOSTS`` counts (``GlobalKnownHostsFile=/dev/null``), nothing
    is added to it (``UpdateHostKeys=no``) and DNS is not asked (``VerifyHostKeyDNS=no``).
    Authentication: the public key only; keyboard-interactive, password, host-based and GSSAPI
    are off. Port: 22 (``SSH_PORT``). ``KbdInteractiveAuthentication`` needs an OpenSSH that
    knows the option; an older client refuses it as a bad option, which fails closed.
    Every value that reaches the argument list is validated first (host, address, paths)."""
    return ["ssh", "-F", "none", "-T",
            "-i", str(cfg.ssh_path("PVE_ROOT_KEY")),
            "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none",
            "-o", "ControlMaster=no", "-o", "ControlPath=none",
            "-o", "ForwardAgent=no", "-o", "ForwardX11=no", "-o", "ClearAllForwardings=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={cfg.ssh_path('PVE_KNOWN_HOSTS')}",
            "-o", "GlobalKnownHostsFile=/dev/null", "-o", "UpdateHostKeys=no", "-o", "VerifyHostKeyDNS=no",
            "-o", "BatchMode=no", "-o", "PreferredAuthentications=publickey",
            "-o", "PasswordAuthentication=no", "-o", "KbdInteractiveAuthentication=no",
            "-o", "HostbasedAuthentication=no", "-o", "GSSAPIAuthentication=no",
            "-o", f"Port={SSH_PORT}",
            "-o", f"BindAddress={cfg.workstation_addr()}",
            f"root@{cfg.host()}", "bash -s"]


def local_address_check(addr: str, socket_factory: Callable[..., Any] = socket.socket) -> None:
    """Refuse unless ``addr`` is assigned to this machine: bind (addr, 0), never connect,
    so no packet is sent."""
    family = socket.AF_INET6 if ":" in addr else socket.AF_INET
    sock = socket_factory(family, socket.SOCK_STREAM)
    try:
        sock.bind((addr, 0))
    except OSError as exc:
        raise HostRunError(f"PVE_WORKSTATION_ADDR {addr} is not an address of this machine "
                           f"({exc.strerror or exc}); ssh would fail to bind to it. Check the setting "
                           "and `ip -br addr`") from None
    finally:
        sock.close()


def child_env(env: Mapping[str, str]) -> dict[str, str]:
    """Environment for ssh: no agent socket, nothing that could carry a credential."""
    keep = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM")
    return {k: env[k] for k in keep if k in env}


# --------------------------------------------------------------------------- output

def check_private_dir(path: Path) -> None:
    """Refuse a directory that is a symlink, belongs to another user or that others can enter."""
    try:
        os.close(open_private_dir(path, create=False))
    except ConfigError as exc:
        raise HostRunError(str(exc)) from None


def private_parent(path: Path) -> Path:
    """Create ``path``'s missing parent with mode 700 (and every missing ancestor, whatever
    the umask), then refuse it unless it is a private directory of this user."""
    parent = path.parent
    try:
        os.close(open_private_dir(parent))
    except ConfigError as exc:
        raise HostRunError(str(exc)) from None
    return parent


_TMP_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def _write_fd(fd: int, data: bytes) -> None:
    with os.fdopen(fd, "wb") as fh:  # closes fd
        os.fchmod(fh.fileno(), 0o600)
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def _unlink_quiet(dir_fd: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=dir_fd)
    except FileNotFoundError:
        pass


def _create_exclusive_at(dir_fd: int, name: str, data: bytes) -> None:
    """Create ``name`` inside ``dir_fd`` itself with O_EXCL|O_NOFOLLOW (never overwrites, never
    follows a symlink; FileExistsError says something is there); remove it again if writing
    fails."""
    fd = os.open(name, _TMP_FLAGS, 0o600, dir_fd=dir_fd)
    try:
        _write_fd(fd, data)
    except BaseException:
        _unlink_quiet(dir_fd, name)
        raise


def write_private(path: Path, data: bytes, *, exclusive: bool = False) -> None:
    """Write ``data`` to ``path`` with mode 600, atomically, in a private directory.

    The parent is opened once as a directory descriptor (created 700 with its missing
    ancestors if absent; refused unless it is a real directory of this user with mode 700
    exactly) and every later step is relative to that descriptor, so swapping the parent's path
    after the check redirects nothing. The temporary file has an unpredictable name in the same
    directory and is created with O_EXCL and O_NOFOLLOW; it is removed on any failure. A symlink
    or non-regular file at ``path`` is refused, never followed. With ``exclusive`` an existing
    ``path`` (even a dangling symlink) is refused instead of replaced.

    Exclusive writes carry a secret that exists only once. If both the hard link and the direct
    create then fail, the temporary file is kept (mode 600, same directory) and the error names
    it, so the data is never silently dropped.
    """
    path = Path(path)
    name = path.name
    if name in ("", ".", ".."):
        raise HostRunError(f"{path}: not a file name")
    try:
        dfd = open_private_dir(path.parent)
    except ConfigError as exc:
        raise HostRunError(str(exc)) from None
    try:
        _write_private_at(dfd, name, data, exclusive)
    finally:
        os.close(dfd)


def _write_private_at(dfd: int, name: str, data: bytes, exclusive: bool) -> None:
    try:
        dest = os.lstat(name, dir_fd=dfd)
    except FileNotFoundError:
        dest = None
    if dest is not None:
        if exclusive:
            raise HostRunError(f"{name} already exists; refusing to overwrite it")
        if not stat.S_ISREG(dest.st_mode):
            raise HostRunError(f"{name} exists and is not a regular file (symlink?); refusing")
    for _ in range(16):
        tmp = f".{name}.{secrets.token_hex(8)}.tmp"
        try:
            fd = os.open(tmp, _TMP_FLAGS, 0o600, dir_fd=dfd)
            break
        except FileExistsError:
            continue
    else:
        raise HostRunError(f"could not create a temporary file next to {name}")
    keep = False
    try:
        _write_fd(fd, data)
        if exclusive:
            try:
                # fails if anything exists at name; never replaces it
                os.link(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd, follow_symlinks=False)
            except FileExistsError:
                raise HostRunError(f"{name} already exists; refusing to overwrite it") from None
            except OSError:
                try:
                    _create_exclusive_at(dfd, name, data)  # no hard links here: create the destination itself
                except FileExistsError:
                    raise HostRunError(f"{name} already exists; refusing to overwrite it") from None
                except OSError as exc:
                    keep = True
                    raise HostRunError(f"could not place {name} ({exc.strerror or 'I/O error'}); its data is kept "
                                       f"in {tmp} (mode 600) in the same directory: move it to {name}") from None
            os.unlink(tmp, dir_fd=dfd)
        else:
            # rename replaces the entry itself, never a symlink's target
            os.replace(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd)
    except BaseException:
        if not keep:
            _unlink_quiet(dfd, tmp)
        raise


def handle_output(stream: IO[bytes], mode: str, out: IO[str], log: IO[str],
                  token_file: Path | None = None, out_file: Path | None = None,
                  scrubber: SecretScrubber | None = None) -> dict[str, Any]:
    """Route the host's stdout: show it, store it, or extract the token secret from it.

    ``scrubber`` holds every secret learned so far. The token secret is registered the moment it
    is parsed, before anything is attempted with it, so a failure to store it cannot make later
    lines (here or in ``_drain``) show it. The caller passes the same scrubber to ``_drain``."""
    scrubber = scrubber if scrubber is not None else SecretScrubber()
    result: dict[str, Any] = {"token_written": False, "bytes": 0}
    if mode.startswith("file:"):
        data = stream.read()
        assert out_file is not None
        write_private(out_file, data)
        result["bytes"] = len(data)
        msg = f"[host-run] {len(data)} bytes written to {out_file}\n"
        out.write(msg)
        log.write(msg)
        return result
    for raw in iter(stream.readline, b""):
        line = raw.decode(errors="replace")
        if mode == "token" and line.startswith(TOKEN_LINE):
            secret = line[len(TOKEN_LINE):].strip()
            if not secret or result["token_written"]:
                raise HostRunError("unexpected token output")
            scrubber.add(secret)  # before the write: a failed write must not unlearn it
            assert token_file is not None
            try:
                write_private(token_file, (secret + "\n").encode(), exclusive=True)
            except (HostRunError, OSError) as exc:
                if isinstance(exc, HostRunError) and "is kept in" in str(exc):
                    raise  # the secret is in a named private file next to the destination
                reason = str(exc) if isinstance(exc, HostRunError) else (exc.strerror or "I/O error")
                raise HostRunError(f"{reason}. The token secret was received but could not be stored; it was "
                                   "not shown or logged and it is not kept. The token exists on the host: "
                                   "remove it there and run bootstrap again") from None
            result["token_written"] = True
            line = f"[host-run] token secret written to {token_file} (not shown)\n"
        safe = scrubber.scrub(redact(line))
        if mode == "token":
            # A token secret is a UUID: no other line of this action may show one, in any shape.
            safe = redact_uuids(safe)
        out.write(safe)
        log.write(safe)
    return result


def _drain(stream: IO[bytes], mode: str, log: IO[str], scrubber: SecretScrubber | None = None) -> None:
    """Read what the host still prints after an output error, into the log only, redacted and
    scrubbed of every secret learned so far (the same scrubber ``handle_output`` used). The remote
    script keeps running to its end instead of being cut off by a broken pipe."""
    scrubber = scrubber if scrubber is not None else SecretScrubber()
    for raw in iter(stream.readline, b""):
        safe = scrubber.scrub(redact(raw.decode(errors="replace")))
        log.write(redact_uuids(safe) if mode == "token" else safe)


# --------------------------------------------------------------------------- main flow

def _read_json(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except RecursionError:  # a deeply nested file is a bad input, not a crash
        raise ValueError(f"{Path(path).name}: JSON nested too deeply") from None


def run(action_name: str, cfg: Config, *, manifest_path: str | None = None, expected_sha: str | None = None,
        inventory_path: str | None = None, overrides_path: str | None = None,
        stdin: IO[str] = sys.stdin, stdout: IO[str] = sys.stdout,
        env: Mapping[str, str] = os.environ, ancestors: Iterable[str] | None = None,
        is_tty: Callable[[], bool] | None = None,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
        addr_check: Callable[[str], None] = local_address_check) -> int:
    reason = running_under_agent(env, process_ancestors() if ancestors is None else ancestors)
    if reason:
        raise HostRunError(reason)
    tty = is_tty() if is_tty else (sys.stdin.isatty() and sys.stdout.isatty())
    if not tty:
        raise HostRunError("host-run needs an interactive terminal (stdin and stdout must be a TTY)")
    if action_name in BLOCKED_ACTIONS:  # before a setting is validated, anything is rendered, shown or sent
        raise HostRunError(BLOCKED_ACTIONS[action_name])
    if action_name in ACTIONS and action_name != "apply-manifest":
        action_params(ACTIONS[action_name], cfg)  # a bad setting is refused before anything is shown

    manifest = inventory = overrides = None
    if action_name == "apply-manifest":
        if not manifest_path or not expected_sha:
            raise HostRunError("apply-manifest needs --manifest FILE --sha256 HASH --inventory INV --overrides OV")
        manifest = mf.load(manifest_path)
        actual = mf.manifest_hash(manifest)
        if actual != expected_sha.lower():
            raise HostRunError(f"manifest hash is {actual}, not the {expected_sha} you gave")
        if not inventory_path or not overrides_path:
            raise HostRunError("apply-manifest needs --inventory INV (the one the manifest was built from) "
                               "and --overrides OV")
        inventory, overrides = _read_json(inventory_path), _read_json(overrides_path)
        # Full check before anything is shown, rendered or sent: bound to this inventory,
        # every item REMOVE_CANDIDATE under the recomputed classification, state unchanged.
        mf.validate_for_apply(manifest, inventory, apply_classification(cfg, inventory, overrides))
        # The sentinel is checked by the classification above, with its own refusal; the other
        # parameters are checked here, still before the dry-run listing is shown.
        action_params(ACTIONS["apply-manifest"], cfg)
        stdout.write(mf.dry_run(manifest) + "\n\n")
    if action_name in DESTRUCTIVE_ACTIONS:
        # DISABLED (see DESTRUCTIVE_ACTIONS). Unconditional: every path through this function for a
        # destructive action ends here or in a refusal above. The request was validated and the plan
        # was listed; nothing below this line (ssh arguments, the address bind, the state directory,
        # rendering, the approval prompt, the connection) is reached.
        raise HostRunError(DESTRUCTIVE_DISABLED.format(action=action_name))

    action = ACTIONS.get(action_name)
    token_file = cfg.path("PVE_TOKEN_FILE") if action and action.output == "token" else None
    if token_file is not None and os.path.lexists(token_file):
        raise HostRunError(f"{token_file.name} already exists; move it away before creating a new token")
    # Check where the output will go before anything runs: the token secret is shown once.
    if token_file is not None:
        private_parent(token_file)
    if action is not None and action.output.startswith("file:"):
        private_parent(cfg.state_dir() / "host-backup" / "x")
    # Build the whole ssh argument list before the prompt: every value that reaches it (host,
    # address, key and known-hosts paths) is validated now, not after the owner has typed the hash.
    ssh_argv = ssh_command(cfg)
    if not cfg.ssh_path("PVE_KNOWN_HOSTS").is_file():
        raise HostRunError("PVE_KNOWN_HOSTS does not exist; pin the host key first (see README, L2)")
    addr_check(cfg.workstation_addr())  # before the prompt: ssh will bind to this address

    if action_name in DESTRUCTIVE_ACTIONS:  # second, independent refusal: never render for a prompt
        raise HostRunError(DESTRUCTIVE_DISABLED.format(action=action_name))
    state = cfg.state_dir()
    check_state_subdirs(state)  # approved/ and runs/: made 700 or refused, before the prompt
    script = render(action_name, cfg, manifest, inventory=inventory, overrides=overrides)
    sha = script_hash(script)
    stdout.write(review_text(action_name, script, state) + "\n")
    stdout.write(f"\nType the first 8 characters of the sha256 ({sha[:2]}…) to run on "
                 f"{cfg.host()}, anything else aborts: ")
    stdout.flush()
    if not confirmation_matches(stdin.readline(), sha):
        stdout.write("aborted; nothing was sent to the host\n")
        return 1
    check_root_key(cfg.path("PVE_ROOT_KEY"), runner)
    record_approval(state, action_name, script)

    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    assert action is not None
    runs = state / "runs"
    log_name = f"{stamp}-{action_name}.log"
    log_path = runs / log_name
    out_file = state / "host-backup" / f"{stamp}-{action.output[5:]}" if action.output.startswith("file:") else None

    # The runs directory is opened as a private directory and the log is created inside it
    # by descriptor: exclusive, never through a symlink.
    sfd = _state_fd(state, create=True)
    try:
        rfd = _subdir_fd(sfd, "runs", state, create=True)
    finally:
        os.close(sfd)
    try:
        try:
            fd = os.open(log_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600,
                         dir_fd=rfd)
        except FileExistsError:
            raise HostRunError(f"{log_name} already exists; refusing to overwrite it") from None
    finally:
        os.close(rfd)
    os.fchmod(fd, 0o600)  # created exclusively; the umask may have taken owner bits away
    with os.fdopen(fd, "w", encoding="utf-8") as log:
        log.write(f"action={action_name} sha256={sha} host={cfg.host()}\n")
        proc = popen(ssh_argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=child_env(env))
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(script.encode())
        proc.stdin.close()
        scrubber = SecretScrubber()
        try:
            handle_output(proc.stdout, action.output, stdout, log, token_file=token_file, out_file=out_file,
                          scrubber=scrubber)
        except (HostRunError, OSError) as exc:
            # The remote script still runs to its end. Let it finish into the log (redacted,
            # and scrubbed of the secret learned before the failure), record how it ended, then
            # report the error.
            _drain(proc.stdout, action.output, log, scrubber)
            code = proc.wait()
            log.write(f"exit={code}\noutput error: {type(exc).__name__}\n")
            stdout.write(f"[host-run] the remote script ended with exit {code}; log {log_path}\n")
            raise
        code = proc.wait()
        log.write(f"exit={code}\n")
    if action.output == "token" and code == 0 and not (token_file and token_file.exists()):
        stdout.write("[host-run] WARNING: the action succeeded but no token secret was received\n")
    stdout.write(f"[host-run] exit {code}; log {log_path}\n")
    return code


def main(argv: list[str] | None = None) -> int:
    import argparse

    from .config import load

    p = argparse.ArgumentParser(prog="host-run", description="Owner-executed privileged actions (Mode B).")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list actions")
    show = sub.add_parser("show", help="print the rendered script without running it")
    show.add_argument("action")
    r = sub.add_parser("run", help="review, confirm and run an action")
    r.add_argument("action")
    r.add_argument("--sha256")
    for parser in (show, r):
        parser.add_argument("--manifest")
        parser.add_argument("--inventory", help="apply-manifest: the inventory the manifest was built from")
        parser.add_argument("--overrides", help="apply-manifest: the overrides the classification came from")
    args = p.parse_args(argv)
    try:
        if args.cmd == "list":
            for a in sorted(ACTIONS.values(), key=lambda a: a.name):
                print(f"{a.name:15s} {a.summary}")
            return 0
        cfg = load()
        if args.cmd == "show":
            manifest = mf.load(args.manifest) if args.manifest else None
            inventory = _read_json(args.inventory) if args.inventory else None
            overrides = _read_json(args.overrides) if args.overrides else None
            print(render(args.action, cfg, manifest, inventory=inventory, overrides=overrides), end="")
            return 0
        return run(args.action, cfg, manifest_path=args.manifest, expected_sha=args.sha256,
                   inventory_path=args.inventory, overrides_path=args.overrides)
    except Exception as exc:  # noqa: BLE001
        # Every refusal type any lab_agent module raises (and OS and value errors, which include
        # bad JSON) is an exit 2 with one line. Anything else is a bug and keeps its traceback.
        if not is_refusal(exc):
            raise
        print(f"host-run: {redact_uuids(redact(str(exc)))}", file=sys.stderr)
        return 2
