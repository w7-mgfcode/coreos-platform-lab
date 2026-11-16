"""Load the lab-agent settings without ever printing a secret.

The settings live in a KEY=VALUE file outside the repository (default
``~/.config/corelab-lab-agent/env``, overridable with ``PVE_AGENT_ENV``). The file is
parsed, never sourced, so a value cannot run code. Secret material (the token secret)
lives in its own file and is read only by the code that needs it.
"""

from __future__ import annotations

import errno
import ipaddress
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ENV = Path("~/.config/corelab-lab-agent/env")

# Every key the tooling understands. Unknown keys are rejected so a typo fails loudly.
KNOWN_KEYS = {
    "PVE_HOST": "API and SSH address of the Proxmox host",
    "PVE_PORT": "API port (default 8006)",
    "PVE_NODE": "node name",
    "PVE_CA_FILE": "local copy of /etc/pve/pve-root-ca.pem",
    "PVE_TOKEN_ID": "routine token id, USER@REALM!TOKENID",
    "PVE_TOKEN_FILE": "file holding the routine token secret, mode 600",
    "PVE_ROOT_KEY": "passphrase-protected root SSH key, used only by host-run",
    "PVE_SNIP_KEY": "snippet-writer SSH key (its .pub is installed by prepare)",
    "PVE_KNOWN_HOSTS": "known_hosts file pinning the host key",
    "PVE_LAB_STATE": "local state directory for inventory, logs and backups",
    "PVE_POOL": "project pool (default corelab)",
    "PVE_VM_STORAGE": "storage for project VM disks",
    "PVE_LAB_STORAGE": "dedicated directory storage id (default corelab)",
    "PVE_LAB_STORAGE_PATH": "filesystem path of the dedicated storage on the host",
    "PVE_BRIDGE": "bridge the project guests use",
    "PVE_VMID_RANGE": "VMID block reserved for project guests, e.g. 9100-9199",
    "PVE_SENTINEL_VMID": "VMID of the sentinel guest outside the pool",
    "PVE_SENTINEL_BACKUP_STORAGE": "non-project storage that holds the sentinel backup",
    "PVE_TEMPLATE_VMID": "VMID of the FCOS template inside the pool",
    "PVE_WORKSTATION_ADDR": "the one fixed IP address this workstation uses towards the host: ssh binds "
                            "to it, the API client uses it as source address, from= names it",
    "PVE_TOKEN_EXPIRE_DAYS": "token lifetime in days (default 90)",
    "FCOS_IMAGE_URL": "URL of the FCOS proxmoxve qcow2 image",
    "FCOS_IMAGE_SHA256": "expected sha256 of that image",
}

DEFAULTS = {
    "PVE_PORT": "8006",
    "PVE_POOL": "corelab",
    "PVE_LAB_STORAGE": "corelab",
    "PVE_TOKEN_EXPIRE_DAYS": "90",
}

_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")
_TOKEN_ID = re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9._-]+![A-Za-z][A-Za-z0-9._-]*$")
_RANGE = re.compile(r"([0-9]+)-([0-9]+)", re.ASCII)


class ConfigError(Exception):
    """A setting is missing, malformed or a secret file is not protected."""


def parse_env_text(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines. Comments and blank lines are skipped; quotes are stripped."""
    values: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE.match(line)
        if not m:
            raise ConfigError(f"line {number}: expected KEY=VALUE")
        key, value = m.group(1), m.group(2).strip()
        if key == "PVE_SSH_PORT":
            raise ConfigError(f"line {number}: there is no ssh port setting: the owner-path ssh and the "
                              "snippet writer use port 22 only (PVE_PORT is the API port)")
        if key not in KNOWN_KEYS:
            raise ConfigError(f"line {number}: unknown key {key}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key] = value
    return values


def check_private_file(path: Path) -> None:
    """Refuse a secret file that others can read or that belongs to another user."""
    try:
        st = path.stat()
    except FileNotFoundError:
        raise ConfigError(f"{path.name}: file not found") from None
    if not stat.S_ISREG(st.st_mode):
        raise ConfigError(f"{path.name}: not a regular file")
    if st.st_uid != os.getuid():
        raise ConfigError(f"{path.name}: owned by another user")
    if st.st_mode & 0o077:
        raise ConfigError(f"{path.name}: mode {oct(st.st_mode & 0o777)}, expected 600")


def is_refusal(exc: BaseException) -> bool:
    """True for an error the tooling raises on purpose (a refusal): an OS or value error, or any
    exception class defined inside ``lab_agent``. A ``RecursionError`` counts too: the only
    recursion in these tools is JSON parsing of a file the owner or the host supplied, and a
    module that parses JSON itself (the manifest loader) would otherwise end in a traceback.
    The command lines map these to exit 2 with a one-line message; every other exception (a
    bug) keeps its traceback and exits 1."""
    return (isinstance(exc, (OSError, ValueError, RecursionError))
            or type(exc).__module__.split(".")[0] == "lab_agent")


# --------------------------------------------------------------------------- private directories

_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
_PRIVATE_DIR_MODE = 0o700


def check_private_dir_fd(fd: int, label: object) -> None:
    """Refuse an open directory that is not a directory, belongs to another user or has any
    mode other than 700 (group or world access, sticky, setuid or setgid). Checked on the
    descriptor, so the answer cannot change between the check and the use."""
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode):
        raise ConfigError(f"{label}: not a directory")
    if st.st_uid != os.getuid():
        raise ConfigError(f"{label}: owned by another user")
    if st.st_mode & 0o7777 != _PRIVATE_DIR_MODE:
        raise ConfigError(f"{label}: mode {oct(st.st_mode & 0o7777)}, expected 700 (chmod 700 it)")


def _open_dir_nofollow(name: object, *, dir_fd: int | None = None) -> int:
    try:
        return os.open(name, _DIR_FLAGS | os.O_NOFOLLOW, dir_fd=dir_fd)
    except FileNotFoundError:
        raise ConfigError(f"{name}: directory not found") from None
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            try:
                is_link = stat.S_ISLNK(os.lstat(name, dir_fd=dir_fd).st_mode)
            except OSError:
                is_link = exc.errno == errno.ELOOP
            if is_link:
                raise ConfigError(f"{name}: is a symlink; refusing to write a private file through it") from None
            raise ConfigError(f"{name}: not a directory") from None
        raise


def open_private_subdir(parent_fd: int, name: str, label: object, *, create: bool = True) -> int:
    """Open (and with ``create`` make, mode 700 whatever the umask) the directory ``name`` inside
    the directory ``parent_fd``; refuse a symlink and anything that is not private. Returns a
    descriptor the caller closes."""
    made = False
    if create:
        try:
            os.mkdir(name, _PRIVATE_DIR_MODE, dir_fd=parent_fd)
            made = True
        except FileExistsError:
            pass
    fd = _open_dir_nofollow(name, dir_fd=parent_fd)
    try:
        if made:
            os.fchmod(fd, _PRIVATE_DIR_MODE)  # the umask may have taken bits away
        check_private_dir_fd(fd, label)
    except BaseException:
        os.close(fd)
        raise
    return fd


def open_private_dir(path: str | os.PathLike[str], *, create: bool = True) -> int:
    """Open the directory ``path`` as a private directory and return its descriptor.

    A missing directory is created with mode 700, and so is every missing ancestor, whatever
    the umask. The final component is never a symlink, must belong to this user and must be
    mode 700 exactly. Ancestors that already exist are used as they are (a symlinked ancestor
    such as a relocated home is fine; their mode is not judged). Everything after this call
    uses the descriptor, so swapping the path afterwards redirects nothing."""
    target = Path(os.path.abspath(os.fspath(path)))
    missing: list[str] = []
    probe = target
    while True:
        try:
            os.lstat(probe)
            break
        except FileNotFoundError:
            if not create:
                raise ConfigError(f"{target}: directory not found") from None
            if probe.parent == probe:
                raise ConfigError(f"{target}: no existing ancestor") from None
            missing.append(probe.name)
            probe = probe.parent
    if not missing:
        fd = _open_dir_nofollow(target)
        try:
            check_private_dir_fd(fd, target)
        except BaseException:
            os.close(fd)
            raise
        return fd
    try:
        fd = os.open(probe, _DIR_FLAGS)
    except NotADirectoryError:
        raise ConfigError(f"{probe}: not a directory") from None
    try:
        for index, name in enumerate(reversed(missing)):
            label = target if index == len(missing) - 1 else probe / name
            nfd = open_private_subdir(fd, name, label)
            os.close(fd)
            fd = nfd
    except BaseException:
        os.close(fd)
        raise
    return fd


_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_HEX_LABEL = re.compile(r"^0[xX][0-9A-Fa-f]*$")
_HOST_BAD_CHARS = set("@/\\%[]\"' \t\r\n,;*")


def validate_host(raw: str) -> str:
    """``raw`` as an IP literal (canonical form) or a syntactically valid host name.

    Refused: empty, surrounding or inner white space, ``@``, ``/``, ``:`` in a name (no port),
    brackets, a zone id, a leading ``-`` (it would read as an ssh option), a name whose last
    label is all digits or hexadecimal (``inet_aton`` would read it as an address), and
    unspecified, broadcast and multicast addresses."""
    explain = ("PVE_HOST must be an IP address or a host name (letters, digits, hyphens and dots; "
               "no port, user, path, brackets or option). ssh uses port 22 only; the API port is PVE_PORT")
    if not raw or raw != raw.strip() or raw.startswith("-") or _HOST_BAD_CHARS & set(raw):
        raise ConfigError(explain)
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        addr = None
    if addr is not None:
        if addr.is_unspecified or addr.is_multicast or addr == ipaddress.IPv4Address(2**32 - 1):  # broadcast
            raise ConfigError("PVE_HOST is a wildcard, broadcast or multicast address, not a host")
        if addr.version == 6 and addr.ipv4_mapped is not None:
            raise ConfigError("PVE_HOST is an IPv4-mapped IPv6 address; write the IPv4 address")
        return str(addr)
    if len(raw) > 253 or raw.endswith("."):
        raise ConfigError(explain)
    labels = raw.split(".")
    if not all(_HOST_LABEL.match(label) for label in labels):
        raise ConfigError(explain)
    if labels[-1].isdigit() or _HEX_LABEL.match(labels[-1]):
        raise ConfigError("PVE_HOST looks like a number, not a host name; write a full IP address or a name")
    return raw


def validate_port(raw: str) -> int:
    if not (raw.isascii() and raw.isdigit() and 1 <= int(raw) <= 65535):
        raise ConfigError("PVE_PORT must be a number from 1 to 65535")
    return int(raw)


_SSH_UNSAFE = re.compile(r"[\s\"'\\%$]")

# --------------------------------------------------------------------------- action parameters
# Every value that host-run exports into the root script is checked by type first (they are also
# shell-quoted, but a quoted string still reaches Bash arithmetic, a path or a command argument).
# Messages name the setting and the rule, never the value.

_PVE_ID = re.compile(r"[A-Za-z](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9])?")  # pool and storage ids
_IFACE = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,14}")                    # bridge: a Linux interface name
_PATH_CHARS = re.compile(r"/[A-Za-z0-9._+@/-]*")
_SHA256 = re.compile(r"[0-9A-Fa-f]{64}")
_URL_FORBIDDEN = set("\"'`\\<>{}|^ ")
VMID_MIN, VMID_MAX = 100, 999_999_999


def validate_int(key: str, value: str, lo: int, hi: int) -> int:
    """A decimal integer from ``lo`` to ``hi``: ASCII digits only, no sign, no space, no base prefix."""
    if not (value.isascii() and value.isdigit() and lo <= int(value) <= hi):
        raise ConfigError(f"{key} must be a whole number from {lo} to {hi}")
    return int(value)


def validate_vmid(key: str, value: str) -> int:
    return validate_int(key, value, VMID_MIN, VMID_MAX)


def validate_pve_id(key: str, value: str) -> str:
    """A Proxmox pool or storage identifier: starts with a letter, then letters, digits, ``.``,
    ``_`` and ``-``, and does not end with a symbol."""
    if not _PVE_ID.fullmatch(value):
        raise ConfigError(f"{key} must be a Proxmox identifier: a letter first, then letters, digits, '.', '_' "
                          "or '-', at most 64 characters, not ending in a symbol")
    return value


def validate_bridge(key: str, value: str) -> str:
    if not _IFACE.fullmatch(value):
        raise ConfigError(f"{key} must be a network interface name: a letter first, then letters, digits, "
                          "'.', '_' or '-', at most 15 characters")
    return value


def validate_abs_path(key: str, value: str) -> str:
    """An absolute, normalized path: no ``..``, ``.``, empty component, trailing slash or the
    root itself, and only letters, digits and ``._+@-`` between slashes."""
    parts = value.split("/")
    if (not _PATH_CHARS.fullmatch(value) or value == "/" or value.endswith("/")
            or any(p in ("", ".", "..") for p in parts[1:])):
        raise ConfigError(f"{key} must be an absolute normalized path (no '..', '.', '//' or trailing '/'; "
                          "letters, digits and ._+@- only)")
    return value


def validate_https_url(key: str, value: str) -> str:
    """One https URL: ASCII, no white space, quote, backslash, brace, user information or
    fragment, a valid host name or IP literal, an optional numeric port."""
    import urllib.parse
    bad = (not value.isascii() or len(value) > 2048 or any(c in _URL_FORBIDDEN or ord(c) < 32 or ord(c) == 127
                                                              for c in value))
    if not bad:
        try:
            parts = urllib.parse.urlsplit(value)
            port = parts.port
            host = parts.hostname
            bad = (parts.scheme != "https" or not host or "@" in parts.netloc or bool(parts.fragment)
                   or (port is not None and not 1 <= port <= 65535))
            if not bad:
                validate_host(host)
        except (ValueError, ConfigError):
            bad = True
    if bad:
        raise ConfigError(f"{key} must be one https URL (a host name or IP address, no user information, "
                          "white space, quote or fragment)")
    return value


def validate_sha256(key: str, value: str) -> str:
    if not _SHA256.fullmatch(value):
        raise ConfigError(f"{key} must be 64 hexadecimal characters")
    return value.lower()


@dataclass
class Config:
    values: dict[str, str]
    source: Path | None = None
    _token_cache: str | None = field(default=None, repr=False)

    def get(self, key: str) -> str:
        if key not in KNOWN_KEYS:
            raise KeyError(key)
        value = self.values.get(key) or DEFAULTS.get(key)
        if not value:
            raise ConfigError(f"{key} is not set ({KNOWN_KEYS[key]})")
        return value

    def path(self, key: str) -> Path:
        return Path(self.get(key)).expanduser()

    def has(self, key: str) -> bool:
        return bool(self.values.get(key) or DEFAULTS.get(key))

    def host(self) -> str:
        """PVE_HOST validated: an IP literal (canonical form) or a host name. Used for the API
        URL, the ssh destination and every message; ``get("PVE_HOST")`` is the raw text."""
        return validate_host(self.get("PVE_HOST"))

    def port(self) -> int:
        """PVE_PORT validated: the API port. There is no ssh port setting (ssh uses 22 only)."""
        return validate_port(self.get("PVE_PORT"))

    def ssh_path(self, key: str) -> Path:
        """A configured path that goes into an ssh command line: absolute, with no white space,
        quote, backslash, ``%`` or ``$`` (ssh would split or expand them inside an option)."""
        path = self.path(key)
        text = str(path)
        if not path.is_absolute() or _SSH_UNSAFE.search(text) or any(ord(c) < 32 for c in text):
            raise ConfigError(f"{key} must be an absolute path without white space, quotes, backslash, % or $ "
                              "(it is passed to ssh)")
        return path

    def vmid_range(self) -> tuple[int, int]:
        m = _RANGE.fullmatch(self.get("PVE_VMID_RANGE"))
        if not m:
            raise ConfigError("PVE_VMID_RANGE must look like 9100-9199")
        lo, hi = int(m.group(1)), int(m.group(2))
        if not 100 <= lo <= hi <= 999_999_999:
            raise ConfigError("PVE_VMID_RANGE is outside 100-999999999 or reversed")
        return lo, hi

    def workstation_addr(self) -> str:
        """PVE_WORKSTATION_ADDR as exactly one IP address, in canonical form.

        Refused: empty, a CIDR, a list, a wildcard or unspecified address, quotes, a zone id,
        a host name, an address that cannot be this machine's source address (loopback,
        broadcast and the other reserved IPv4 ranges, "this network" 0.0.0.0/8, multicast,
        link-local, an IPv4-mapped IPv6 address, reserved IPv6 ranges), and an address family
        that differs from an IP-literal PVE_HOST. A subnet-directed broadcast address cannot be
        told from a host address without the interface's netmask; the bind check of the
        owner-path run catches it."""
        raw = self.get("PVE_WORKSTATION_ADDR")
        explain = "PVE_WORKSTATION_ADDR must be exactly one IP address (no name, CIDR, list, wildcard, quote or zone id)"
        if raw != raw.strip() or any(c in raw for c in "/,;*%\"' \t[]"):
            raise ConfigError(explain)
        try:
            addr = ipaddress.ip_address(raw)
        except ValueError:
            raise ConfigError(explain) from None
        self._check_source_address(addr)
        try:
            host = ipaddress.ip_address(self.host())
        except ValueError:
            host = None  # a host name: its family is decided by resolution, not here
        if host is not None and host.version != addr.version:
            raise ConfigError(f"PVE_WORKSTATION_ADDR is IPv{addr.version}, but PVE_HOST is IPv{host.version}")
        return str(addr)

    @staticmethod
    def _check_source_address(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
        kind = None
        if addr.is_unspecified or addr.is_multicast:
            kind = "a wildcard or multicast address"
        elif addr.is_loopback:
            kind = "a loopback address"
        elif addr.is_link_local:
            kind = "a link-local address"
        elif addr.version == 6 and addr.ipv4_mapped is not None:
            kind = "an IPv4-mapped IPv6 address"
        elif addr.is_reserved:
            kind = "a reserved or broadcast address"
        elif addr.version == 4 and addr in ipaddress.ip_network("0.0.0.0/8"):
            kind = "a 'this network' address"
        if kind:
            raise ConfigError(f"PVE_WORKSTATION_ADDR {addr} is {kind}, so it cannot be this machine's "
                              "source address towards the host")

    def token_id(self) -> str:
        value = self.get("PVE_TOKEN_ID")
        if not _TOKEN_ID.fullmatch(value):
            raise ConfigError("PVE_TOKEN_ID must look like user@realm!tokenid")
        return value

    def token_secret(self) -> str:
        """Read the token secret. Never log or print the return value."""
        if self._token_cache is None:
            path = self.path("PVE_TOKEN_FILE")
            check_private_file(path)
            secret = path.read_text(encoding="utf-8").strip()
            if not secret or "\n" in secret:
                raise ConfigError("PVE_TOKEN_FILE must hold exactly one line")
            self._token_cache = secret
        return self._token_cache

    def state_dir(self) -> Path:
        """The private state directory. A missing one is created, with every missing ancestor,
        as mode 700. An existing one must be a real directory of this user with mode 700
        exactly; otherwise this refuses instead of letting later writes go into it."""
        path = self.path("PVE_LAB_STATE")
        os.close(open_private_dir(path))
        return path

    def redacted(self) -> dict[str, str]:
        """The settings as safe to show: file paths and names only, no secret values."""
        return {k: v for k, v in sorted(self.values.items())}

    def sanitize_map(self) -> dict[str, str]:
        """Real lab values mapped to public placeholders, for evidence sanitization."""
        mapping = {}
        for key in ("PVE_HOST", "PVE_NODE", "PVE_WORKSTATION_ADDR", "PVE_LAB_STORAGE_PATH"):
            if self.values.get(key):
                mapping[self.values[key]] = "${" + key + "}"
        if self.values.get("PVE_TOKEN_ID"):
            mapping[self.values["PVE_TOKEN_ID"]] = "${PVE_TOKEN_ID}"
        return mapping


def load(path: str | os.PathLike[str] | None = None) -> Config:
    """Load the settings file named by the argument, $PVE_AGENT_ENV or the default."""
    chosen = Path(path or os.environ.get("PVE_AGENT_ENV") or DEFAULT_ENV).expanduser()
    check_private_file(chosen)
    return Config(parse_env_text(chosen.read_text(encoding="utf-8")), source=chosen)
