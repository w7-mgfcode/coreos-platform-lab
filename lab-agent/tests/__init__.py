"""Test package for the lab agent. Importing it installs the test-isolation guard.

THE RULE: no test may use the network. Every test runs against a fake transport, a fake connection
class, a socketpair, an AF_UNIX socket in a temporary directory, or a child process whose argument
list cannot make it connect. A reserved documentation address (RFC 5737, RFC 3849) is not isolation.

WHAT THIS GUARD DOES, EXACTLY
  * It PREVENTS in-process Python network use. Before a system call it refuses: ``socket.socket``
    ``connect``, ``connect_ex``, ``sendto``, ``sendmsg``, ``send``, ``sendall`` for every address
    family except AF_UNIX; ``socket.create_connection`` (always); ``getaddrinfo``,
    ``gethostbyname``, ``gethostbyname_ex`` for anything that is not an IP literal;
    ``gethostbyaddr`` (always) and ``getnameinfo`` unless numeric; ``urllib.request.urlopen`` and a
    ``ProxyHandler`` built from the environment. A trip raises ``NetworkIsolationViolation``, an
    ``AssertionError`` that is not an ``OSError``.
  * It SCREENS direct child commands started through ``subprocess.Popen`` (``run``, ``call``,
    ``check_*``), ``os.system``, ``os.popen`` and ``os.exec*``. This is a screen that catches the
    ordinary mistake, NOT containment, and it is not complete. What it checks: the executable's base
    name must be on an explicit allow-list (``ALLOWED_DIRECT``, the interpreters, ``ssh -G`` with
    ``-F none`` or an inspected scratch configuration, and allow-listed options only, local ``git`` subcommands) or be a vetted stub; an
    interpreter may run only a script under the repository or the temporary directory or a
    ``-c``/``-e`` text that names no network-capable tool; a shell script (file or standard input)
    that names such a tool in command position, or spells one with quotes or backslashes, is refused
    unless that tool resolves, on the PATH the child gets, to a vetted stub or to nothing; a perl or
    python file in the temporary directory is held to that same rule for every tool a code line
    names. Every one of these is a text match on what the test hands over.
  * KNOWN GAPS of that screen (none of them is closed here): a script that builds a command name at
    run time (variables, ``eval``, ``printf``, here-documents, ``source``), a tool reached through
    another program (``env``-style wrappers written by a test, ``xargs``, ``find -exec``), a perl or
    python script that opens a socket itself, a stub that is not what it looks like, repository code
    that a test runs, ``ctypes``, a C extension, direct ``_socket`` calls, saved references to the
    original methods, an event loop in native code, ``os.posix_spawn``, ``os.spawn*``. Disabling
    the guard on purpose is detected only when it is replaced and not restored (see below), not
    prevented.
  * It therefore does NOT make the suite network-free, and a green run on a machine with a network
    does not show that no child tried to connect. The evidence for "the suite makes no external
    connection" is the network-less container run (``tests/run-netless.sh``: the whole suite inside
    a container whose only interface is loopback), a separate acceptance command, not this module.

NOTHING MAY PASS BECAUSE THE GUARD RAISED. Every trip is recorded. A test that ends with an
unacknowledged trip fails; trips that happen outside any test body (module import, ``setUpModule``,
``setUpClass``, anything swallowed there) fail the run at its end; the guard is checked and repaired
before every test, and a test that finds it replaced fails and names the replacement. A test about the
guard acknowledges its trips explicitly with ``expect_guard_trips()``.
"""

from __future__ import annotations

import contextlib
import http.client  # noqa: F401  (imported so that name-bound copies below are found and replaced)
import ipaddress
import os
import re
import shlex
import shutil
import socket
import ssl  # noqa: F401
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from typing import Any

RULE = ("TEST ISOLATION RULE: tests must not use the network (no connect, send, name lookup, default "
        "urllib opener or network tool). Use a fake transport, a fake connection class, a socketpair, "
        "an AF_UNIX socket in a temporary directory, or a vetted stub first on PATH; a reserved "
        "documentation address is not isolation.")

NETWORK_TOOLS = frozenset({"ssh", "scp", "sftp", "ssh-keyscan", "curl", "wget", "git", "uv", "uvx", "docker",
                           "podman", "rsync", "pip", "pip3", "nc", "ncat", "telnet", "ping", "ftp"})

GIT_LOCAL_SUBCOMMANDS = frozenset({"apply", "init", "commit", "rev-parse", "add", "status", "log", "diff",
                                   "hash-object", "config"})
SAFE_SPAWN_FORMS = {
    "ssh": "only the reviewed form: options first, -G before the destination, -F none (or a scratch file under "
           "the temporary directory with allow-listed directives only), flags -G -T and options -F -i -o with "
           "allow-listed -o keys only; or exactly 'ssh -V'",
    "git": "only the local subcommands " + ", ".join(sorted(GIT_LOCAL_SUBCOMMANDS)) + "; never clone, fetch, "
           "pull, push, ls-remote, remote or submodule",
}
# Executables a test may start directly, besides the interpreters and the network-tool forms above:
# local tools that cannot connect. Anything else must be a vetted stub; everything else is refused.
ALLOWED_DIRECT = frozenset({"ssh-keygen", "install", "stat"})
INTERPRETER_FAMILIES = ("bash", "sh", "dash", "perl", "python")
PYTHON_MODULES = ("unittest", "lab_agent", "tests", "json", "py_compile")

SCRIPT_SCREEN_LIMIT = 4_000_000  # a script file of this size or more is refused, not run unscreened

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent.parent
TEMP_ROOT = Path(tempfile.gettempdir()).resolve()
STUB_DIR = TESTS_DIR / "stubs"
SCRIPT_ROOTS = (REPO_ROOT, TEMP_ROOT)


class NetworkIsolationViolation(AssertionError):
    """A test (or the code under test) tried to leave the machine. Not an OSError on purpose."""


TRIPS: list[dict[str, Any]] = []
ORIGINALS: dict[str, Any] = {}
GUARDS: list[tuple[Any, str, Any]] = []  # (owner, attribute, the guard object that must be in place)
REPAIRS: list[str] = []


def _trip(entry: str, detail: str) -> None:
    TRIPS.append({"entry": entry, "detail": detail, "acked": False})
    raise NetworkIsolationViolation(f"{RULE} [{entry}: {detail}]")


class _ExpectTrips:
    """``with expect_guard_trips() as seen:`` acknowledges the guard trips inside the block, so
    the end-of-test check does not report them. Fails if no trip happened."""

    def __enter__(self) -> "_ExpectTrips":
        self._mark = len(TRIPS)
        self.trips: list[dict[str, Any]] = []
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.trips = TRIPS[self._mark:]
        for trip in self.trips:
            trip["acked"] = True
        if exc_type is None and not self.trips:
            raise AssertionError("expected the isolation guard to trip, and it did not")
        return False

    @property
    def entries(self) -> list[str]:
        return [t["entry"] for t in self.trips]

    @property
    def details(self) -> str:
        return " | ".join(t["detail"] for t in self.trips)


def expect_guard_trips() -> _ExpectTrips:
    return _ExpectTrips()


# ------------------------------------------------------------------------------ sockets

def _is_ip_literal(host: Any) -> bool:
    if host is None:
        return True  # no name to resolve (wildcard or loopback by the resolver's own rule)
    if isinstance(host, (bytes, bytearray)):
        try:
            host = bytes(host).decode("ascii")
        except UnicodeDecodeError:
            return False
    if not isinstance(host, str):
        return False
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    return True


def _guard_method(name: str):
    original = getattr(socket.socket, name)
    ORIGINALS["socket." + name] = original

    def guarded(self, *args, **kwargs):
        if self.family != socket.AF_UNIX:
            target = args[-1] if args and name in ("connect", "connect_ex", "sendto") else (
                args[3] if name == "sendmsg" and len(args) > 3 else "")
            _trip(f"socket.{name}", f"family={getattr(self.family, 'name', self.family)} address={target!r}")
        return original(self, *args, **kwargs)

    guarded.__name__ = name
    return guarded


def _guard_create_connection(address, *args, **kwargs):
    source = kwargs.get("source_address", args[1] if len(args) > 1 else None)
    _trip("socket.create_connection", f"address={address!r} source={source!r}")


def _guard_getaddrinfo(host, *args, **kwargs):
    if not _is_ip_literal(host):
        _trip("socket.getaddrinfo", f"name={host!r}")
    return ORIGINALS["socket.getaddrinfo"](host, *args, **kwargs)


def _guard_gethostbyname(name):
    if not _is_ip_literal(name):
        _trip("socket.gethostbyname", f"name={name!r}")
    return ORIGINALS["socket.gethostbyname"](name)


def _guard_gethostbyname_ex(name):
    if not _is_ip_literal(name):
        _trip("socket.gethostbyname_ex", f"name={name!r}")
    return ORIGINALS["socket.gethostbyname_ex"](name)


def _guard_gethostbyaddr(address):
    _trip("socket.gethostbyaddr", f"address={address!r} (a reverse lookup asks a resolver)")


def _guard_getnameinfo(sockaddr, flags):
    if not flags & socket.NI_NUMERICHOST:
        _trip("socket.getnameinfo", f"address={sockaddr!r} (without NI_NUMERICHOST it asks a resolver)")
    return ORIGINALS["socket.getnameinfo"](sockaddr, flags)


# ------------------------------------------------------------------------------ urllib

def _guard_urlopen(url, *args, **kwargs):
    _trip("urllib.request.urlopen", f"url={getattr(url, 'full_url', url)!r} (the default opener; build an "
                                    "opener with ProxyHandler({}) and a fake handler instead)")


def _guard_proxy_handler_init(original):
    def init(self, proxies=None):
        if proxies is None:
            _trip("urllib.request.ProxyHandler", "built from the environment (the default opener's handler)")
        return original(self, proxies)
    return init


# ------------------------------------------------------------------------------ child processes

def _under(path: Path, roots) -> bool:
    return any(root == path or root in path.parents for root in roots)


# A network tool word in command position inside a script: at the start of a line or after a
# separator, optionally behind assignments, exec/command/sudo/timeout and a path.
_TOOLS_RX = "|".join(sorted(map(re.escape, NETWORK_TOOLS), key=len, reverse=True))
_COMMAND_POSITION = re.compile(
    r"(?:^|[;&|(`]|\$\()\s*(?:\w+=\S*\s+)*(?:exec\s+|command\s+|sudo\s+|timeout\s+\S+\s+)?"
    r"[\"'\\]*((?:[^\s\"']*/)?(?:" + _TOOLS_RX + r"))[\"']*(?=\s|$|;|\)|`)")
# A tool name the shell would assemble from quoted or escaped pieces (c"ur"l, cu\rl, "cu"'rl'): the
# quotes and backslashes are dropped from each word before it is compared.
_SHELL_WORD = re.compile(r"[^\s;&|()`<>]+")
_QUOTING = re.compile(r"[\"'\\]")
_WORDS = re.compile(r"[\w./+-]+")


def script_network_words(text: str) -> list[str]:
    """Network tools named in command position in a script, as spelled (a path stays in front)."""
    found = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        for match in _COMMAND_POSITION.finditer(line):
            found.append(match.group(1))
        # Fail closed on quoting: any word that IS a tool name once its quotes and backslashes are
        # removed, but is not spelled plainly, counts wherever it stands (position is not parsed).
        for word in _SHELL_WORD.findall(line):
            plain = _QUOTING.sub("", word)
            if plain != word and os.path.basename(plain) in NETWORK_TOOLS and plain not in found:
                found.append(plain)
    return found


def _inline_names_a_tool(text: str) -> str | None:
    """A network-capable tool named anywhere in inline command text, by any path."""
    for word in _WORDS.findall(text):
        if os.path.basename(word) in NETWORK_TOOLS:
            return os.path.basename(word)
    return None


def _is_stub(path: str | None) -> bool:
    """A vetted stub: a file whose real path (symlinks followed) is under ``tests/stubs``; or a small
    script in the temporary directory (shebang, not a binary) that names no network tool in command
    position. A symlink out of those places, a binary, or a script that runs a real tool is not."""
    if not path:
        return False
    try:
        real = Path(path).resolve(strict=True)
    except OSError:
        return False
    if _under(real, (STUB_DIR.resolve(),)):
        return True
    if not _under(real, (TEMP_ROOT,)):
        return False
    try:
        if not real.is_file() or real.stat().st_size > 131072:
            return False
        head = real.read_bytes()
    except OSError:
        return False
    return head.startswith(b"#!") and not script_network_words(head.decode("utf-8", "replace"))


def _which(name: str, env: Any) -> str | None:
    search = env["PATH"] if env is not None and "PATH" in env else None
    return shutil.which(name, path=search)


def _git_subcommand(argv: list[str]) -> str | None:
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
        elif a.startswith("-"):
            i += 1
        else:
            return a
    return None


_SSH_ARG_OPTIONS = set("BbcDEeFIiJLlmOoPpQRSWw")
# What the reviewed ``ssh -G`` form may carry, and nothing else: the flags -G and -T, the options
# -F, -i and -o, and for -o only the keys the owner-path command line sets (``hostrun.ssh_command``).
# -F is ``none``, or a scratch file under the temporary directory whose every directive is on the
# short allow-list below. ssh evaluates ``Match exec`` (and reads ``Include``) while it resolves a
# configuration for -G, so a file is read here first and any other keyword refuses it.
_SSH_FLAGS = set("GT")
_SSH_VALUE_OPTIONS = set("Fio")
_SSH_O_KEYS = frozenset(k.lower() for k in (
    "IdentitiesOnly", "IdentityAgent", "ControlMaster", "ControlPath", "ForwardAgent", "ForwardX11",
    "ClearAllForwardings", "StrictHostKeyChecking", "UserKnownHostsFile", "GlobalKnownHostsFile",
    "UpdateHostKeys", "VerifyHostKeyDNS", "BatchMode", "PreferredAuthentications", "PasswordAuthentication",
    "KbdInteractiveAuthentication", "HostbasedAuthentication", "GSSAPIAuthentication", "Port", "BindAddress"))
# Directives a scratch configuration file may contain (none of them starts a program or reads a file
# when the configuration is only resolved): what the inherited-configuration control test writes.
_SSH_CONFIG_KEYS = _SSH_O_KEYS | {"host", "proxyjump", "bindinterface", "identityfile", "user", "hostname"}


def _ssh_config_ok(path: str) -> bool:
    """A scratch ssh configuration that -G may resolve: a small regular file under the temporary
    directory in which every directive's keyword is allow-listed. Unreadable means refused."""
    try:
        real = Path(path).resolve(strict=True)
        if not _under(real, (TEMP_ROOT,)) or not real.is_file() or real.stat().st_size > 65536:
            return False
        text = real.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if re.split(r"[=\s]", line, maxsplit=1)[0].lower() not in _SSH_CONFIG_KEYS:
            return False
    return True


def _ssh_form_ok(args: list[str]) -> bool:
    """The reviewed ssh form that opens no connection: ``ssh -V``, or ``ssh [options] -G ... -F CONFIG
    [options] destination [command]`` with -G and -F among the options, i.e. BEFORE the destination
    (after it, -G belongs to the remote command: ``ssh host echo -G`` connects). CONFIG is ``none``
    or an inspected scratch file (``_ssh_config_ok``). Any flag, option or ``-o`` key outside the
    short allow-lists above is refused."""
    if args == ["-V"]:
        return True
    seen_g, config, i = False, None, 0
    while i < len(args):
        a = args[i]
        if not a.startswith("-") or a in ("-", "--"):
            break  # the destination (or "--"): everything after it is not an option
        j = 1
        while j < len(a):
            ch = a[j]
            if ch in _SSH_ARG_OPTIONS:
                if ch not in _SSH_VALUE_OPTIONS:
                    return False
                value = a[j + 1:]
                if not value:
                    i += 1
                    value = args[i] if i < len(args) else None
                if value is None:
                    return False
                if ch == "F":
                    if config is not None:
                        return False  # one -F only
                    config = value
                elif ch == "o":
                    key = re.split(r"[=\s]", value.strip(), maxsplit=1)[0].lower()
                    if key not in _SSH_O_KEYS:
                        return False
                break
            if ch not in _SSH_FLAGS:
                return False
            if ch == "G":
                seen_g = True
            j += 1
        i += 1
    return seen_g and config is not None and (config == "none" or _ssh_config_ok(config))


def _check_script_text(text: str, env: Any, what: str) -> None:
    """A script (file or standard input) that names a network tool in command position runs only if
    that tool resolves, on the PATH the child gets, to nothing or to a vetted stub."""
    for spelled in script_network_words(text):
        resolved = spelled if "/" in spelled else _which(spelled, env if env is not None else os.environ)
        if resolved is None:
            continue
        if not _is_stub(resolved):
            _trip("spawn", f"{what} names {spelled!r}, which resolves to {resolved!r}, not to a vetted stub")


def _check_inline(text: str, what: str) -> None:
    tool = _inline_names_a_tool(text)
    if tool:
        _trip("spawn", f"{what} text names the network-capable tool {tool!r}")


def _interpreter_family(name: str) -> str | None:
    for family in INTERPRETER_FAMILIES:
        if name == family or (family == "python" and re.fullmatch(r"python(\d+(\.\d+)?)?", name)):
            return family
    return None


_VALUE_OPTIONS = {"bash": {"-o", "+o", "--rcfile", "--init-file"}, "sh": {"-o", "+o"}, "dash": {"-o", "+o"},
                  "perl": {"-I"}, "python": {"-W", "-X"}}


def _check_interpreter(family: str, args: list[str], env: Any, cwd: Any) -> dict | None:
    """Fail closed for an interpreter child. Returns a spec when its script arrives on stdin."""
    inline = {"bash": ("c",), "sh": ("c",), "dash": ("c",), "perl": ("e", "E"), "python": ("c",)}[family]
    # ``bash -n FILE`` (FILE under the repository or the temporary directory) and ``bash -n`` on standard
    # input only parse: nothing of the script runs, so the script's text is not screened. ``perl -c FILE``
    # is NOT parse-only (perl runs BEGIN blocks and ``use`` while it compiles): it gets no exemption and
    # takes the ordinary path below, like running the file. Any other argument (bash -c, extra flags)
    # takes the ordinary path too.
    syntax_only = {"bash": "-n", "sh": "-n", "dash": "-n"}.get(family)
    if syntax_only and args and args[0] == syntax_only:
        if len(args) == 1:
            return None  # bash -n reading standard input: parse only
        if len(args) == 2 and not args[1].startswith("-"):
            script = Path(args[1]) if os.path.isabs(args[1]) else Path(cwd or os.getcwd()) / args[1]
            if _under(script.resolve(), SCRIPT_ROOTS):
                return None
    i = 0
    while i < len(args):
        a = args[i]
        if family == "python" and a == "-m":
            module = args[i + 1] if i + 1 < len(args) else ""
            if not (module in PYTHON_MODULES or module.split(".")[0] in PYTHON_MODULES):
                _trip("spawn", f"python -m {module!r} is not an allow-listed module")
            return None
        if a.startswith("-") and not a.startswith("--") and len(a) > 1 and any(c in a[1:] for c in inline) and (
                family != "perl" or a[1:] in ("e", "E")):
            text = args[i + 1] if i + 1 < len(args) else ""
            _check_inline(text, f"{family} -{a[1:]}")
            return None
        if a == "-s" and family in ("bash", "sh", "dash"):
            return {"stdin": True, "env": env}
        if not a.startswith("-") and a != "-":
            script = Path(a) if os.path.isabs(a) else Path(cwd or os.getcwd()) / a
            try:
                real = script.resolve()
            except OSError:
                real = script
            if not _under(real, SCRIPT_ROOTS):
                _trip("spawn", f"{family} runs {a!r}, which is outside the repository and the temporary directory")
            try:
                size = real.stat().st_size
            except OSError:
                size = 0  # missing: the interpreter fails by itself
            if size >= SCRIPT_SCREEN_LIMIT:
                _trip("spawn", f"{family} script {real.name} is {size} bytes: too large to screen, so it is refused")
            try:
                text = real.read_text(encoding="utf-8", errors="replace") if size else ""
            except OSError:
                text = ""
            if family in ("bash", "sh", "dash"):  # a shell script is read for the tools it names
                _check_script_text(text, env, f"{family} script {real.name}")
            elif _under(real, (TEMP_ROOT,)) and not _under(real, (REPO_ROOT,)):
                # A perl or python file in the repository is reviewed code (the hook names ssh in order to
                # deny it). One in the temporary directory was written by a test: it is refused when a
                # code line names a network-capable tool that resolves, on the PATH the child gets, to
                # anything but a vetted stub (the rule for shell scripts; this includes BEGIN blocks under
                # ``perl -c``). A copy of the hook run with an empty PATH names tools that resolve to nothing.
                code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
                for word in _WORDS.findall(code):
                    if os.path.basename(word) not in NETWORK_TOOLS:
                        continue
                    resolved = word if "/" in word else _which(word, env)
                    if resolved is not None and not _is_stub(resolved):
                        _trip("spawn", f"{family} script {real.name} in the temporary directory names {word!r}, "
                                       f"which resolves to {resolved!r}, not to a vetted stub")
            return None
        if a in _VALUE_OPTIONS[family]:
            i += 1  # the option's value is not the script
        i += 1
    if family == "perl":
        # No program file and no -e: perl would read its PROGRAM from standard input (and ``perl -c``
        # still runs BEGIN blocks). No test needs that form and the text screen below is written for
        # shell scripts, so it is refused instead of screened.
        _trip("spawn", "perl without a program file or -e reads its program from standard input, which is "
                       "not a reviewed form")
    return {"stdin": True, "env": env}


def check_spawn(argv: Any, env: Any = None, executable: Any = None, shell: bool = False, cwd: Any = None):
    """The fail-closed policy for a direct child command. Raises on a refusal; returns a spec when the
    child is an interpreter whose script arrives on stdin (checked again when the input is sent)."""
    if isinstance(argv, (str, bytes, os.PathLike)):
        text = os.fsdecode(argv)
        if shell:  # /bin/sh -c TEXT
            _check_inline(text, "shell command")
            return None
        argv_list = [text]
    else:
        argv_list = [os.fsdecode(a) for a in argv]
    if not argv_list and executable is None:
        return None
    path = os.fsdecode(executable) if executable is not None else argv_list[0]
    name = os.path.basename(path)
    resolved = path if "/" in path else _which(path, env if env is not None else os.environ)
    if name in NETWORK_TOOLS:
        if _is_stub(resolved):
            return None  # a vetted stub is not the tool
        if name == "ssh" and _ssh_form_ok(argv_list[1:]):
            return None
        if name == "git" and _git_subcommand(argv_list) in GIT_LOCAL_SUBCOMMANDS:
            return None
        _trip("spawn", f"{name} {' '.join(argv_list[1:4])} ... is a network tool outside the safe forms "
                       f"({SAFE_SPAWN_FORMS.get(name, 'no safe form: use a vetted stub')})")
    family = _interpreter_family(name)
    if family is not None:
        return _check_interpreter(family, argv_list[1:], env if env is not None else os.environ, cwd)
    if name in ALLOWED_DIRECT or _is_stub(resolved):
        return None
    _trip("spawn", f"{name!r} is not on the allow-list of executables a test may start "
                   f"({', '.join(sorted(ALLOWED_DIRECT))}, interpreters, vetted stubs)")


def _guard_popen_init(original):
    def init(self, args, *a, **kw):
        spec = check_spawn(args, kw.get("env"), kw.get("executable"), bool(kw.get("shell")), kw.get("cwd"))
        self._guard_stdin_spec = spec
        return original(self, args, *a, **kw)
    return init


def _guard_popen_communicate(original):
    def communicate(self, input=None, timeout=None):
        spec = getattr(self, "_guard_stdin_spec", None)
        if spec and input is not None:
            try:
                _check_script_text(os.fsdecode(input), spec["env"], "script on standard input")
            except NetworkIsolationViolation:
                self.kill()
                raise
        return original(self, input, timeout)
    return communicate


def _guard_os_system(original):
    def system(command):
        _check_inline(os.fsdecode(command), "os.system")
        return original(command)
    return system


def _guard_os_popen(original):
    def popen(cmd, *a, **kw):
        _check_inline(os.fsdecode(cmd), "os.popen")
        return original(cmd, *a, **kw)
    return popen


def _guard_exec(original):
    def execer(path, args, *rest):
        env = rest[0] if rest and isinstance(rest[0], dict) else None
        check_spawn(list(args) or [path], env, path)
        return original(path, args, *rest)
    return execer


# ------------------------------------------------------------------------------ install, repair, accounting

def _put(owner: Any, attr: str, guard: Any) -> None:
    setattr(owner, attr, guard)
    GUARDS.append((owner, attr, guard))


def guard_status() -> list[str]:
    """What is not in place: names of replaced guard objects (empty when the guard is intact)."""
    if not ORIGINALS.get("installed"):
        return ["not installed"]
    return [f"{getattr(owner, '__name__', owner)}.{attr}" for owner, attr, guard in GUARDS
            if getattr(owner, attr, None) is not guard]


def guard_active() -> bool:
    """True when every replacement the guard made is still the object in place."""
    return not guard_status()


def ensure_installed() -> list[str]:
    """Put back every guard object that was replaced and not restored; return what was repaired."""
    repaired = []
    for owner, attr, guard in GUARDS:
        if getattr(owner, attr, None) is not guard:
            setattr(owner, attr, guard)
            repaired.append(f"{getattr(owner, '__name__', owner)}.{attr}")
    REPAIRS.extend(repaired)
    return repaired


def _sweep(originals: dict[int, Any]) -> None:
    """Replace name-bound copies (``from socket import create_connection``) in imported modules."""
    for module in list(sys.modules.values()):
        namespace = getattr(module, "__dict__", None)
        if not isinstance(namespace, dict) or module is sys.modules[__name__]:
            continue
        for key, value in list(namespace.items()):
            replacement = originals.get(id(value)) if not isinstance(value, (list, dict, set)) else None
            if replacement is not None and value is not replacement:
                try:
                    _put(module, key, replacement)
                except (TypeError, AttributeError):
                    pass


def _accounting_case():
    """An object for ``addFailure`` to name. A FunctionTestCase instance, not a TestCase subclass in
    this package, so that test discovery does not collect it as a test."""
    return unittest.FunctionTestCase(lambda: None, description="isolation guard accounting")


def _violation(message: str):
    try:
        raise NetworkIsolationViolation(f"{RULE} {message}")
    except NetworkIsolationViolation:
        return sys.exc_info()


def install() -> list[str]:
    """Install the guard; if it is already installed, repair what was replaced and refuse (raise) if
    that does not make it whole. Returns the names repaired."""
    if ORIGINALS.get("installed"):
        repaired = ensure_installed()
        if not guard_active():
            raise RuntimeError(f"the isolation guard cannot be restored: {', '.join(guard_status())}")
        return repaired
    ORIGINALS["installed"] = True
    swaps: dict[int, Any] = {}

    for name in ("connect", "connect_ex", "sendto", "sendmsg", "send", "sendall"):
        _put(socket.socket, name, _guard_method(name))
    GUARDS.append((socket, "socket", socket.socket))  # the class itself must not be swapped away
    for name, guard in (("getaddrinfo", _guard_getaddrinfo), ("gethostbyname", _guard_gethostbyname),
                        ("gethostbyname_ex", _guard_gethostbyname_ex), ("gethostbyaddr", _guard_gethostbyaddr),
                        ("getnameinfo", _guard_getnameinfo), ("create_connection", _guard_create_connection)):
        original = getattr(socket, name)
        ORIGINALS["socket." + name] = original
        swaps[id(original)] = guard
        _put(socket, name, guard)
    original = urllib.request.urlopen
    ORIGINALS["urllib.request.urlopen"] = original
    swaps[id(original)] = _guard_urlopen
    _put(urllib.request, "urlopen", _guard_urlopen)
    ORIGINALS["urllib.request.ProxyHandler.__init__"] = urllib.request.ProxyHandler.__init__
    _put(urllib.request.ProxyHandler, "__init__", _guard_proxy_handler_init(urllib.request.ProxyHandler.__init__))

    ORIGINALS["subprocess.Popen.__init__"] = subprocess.Popen.__init__
    _put(subprocess.Popen, "__init__", _guard_popen_init(subprocess.Popen.__init__))
    ORIGINALS["subprocess.Popen.communicate"] = subprocess.Popen.communicate
    _put(subprocess.Popen, "communicate", _guard_popen_communicate(subprocess.Popen.communicate))
    for name, factory in (("system", _guard_os_system), ("popen", _guard_os_popen)):
        original = getattr(os, name)
        ORIGINALS["os." + name] = original
        _put(os, name, factory(original))
    for name in ("execv", "execve", "execvp", "execvpe"):
        original = getattr(os, name)
        ORIGINALS["os." + name] = original
        _put(os, name, _guard_exec(original))
    _sweep(swaps)

    original_run = unittest.case.TestCase.run
    ORIGINALS["unittest.TestCase.run"] = original_run

    def run(self, result=None):
        if result is None:
            result = self.defaultTestResult()
        # The guard is checked, and put back, before EVERY test. A test that finds it replaced
        # fails and names what was replaced; if it cannot be made whole the test does not run.
        repaired = ensure_installed()
        if repaired:
            result.addFailure(self, _violation(
                f"The isolation guard was found replaced before this test and was put back: "
                f"{', '.join(repaired)}. Whatever replaced it did not restore it."))
        if not guard_active():
            result.addFailure(self, _violation(f"The isolation guard is not active ({', '.join(guard_status())}); "
                                               "the test was not run."))
            return result
        mark = len(TRIPS)
        outcome = original_run(self, result)
        unacked = [t for t in TRIPS[mark:] if not t["acked"]]
        if unacked:
            for trip in unacked:
                trip["acked"] = True  # reported once, here
            result.addFailure(self, _violation(
                f"This test reached the guard {len(unacked)} time(s) "
                f"({', '.join(sorted({t['entry'] for t in unacked}))}); a test that passes only because "
                "the guard raised is a failing test: fix the test (fake the transport) or, if it proves "
                "the guard, acknowledge the trip with tests.expect_guard_trips()."))
        return outcome

    _put(unittest.case.TestCase, "run", run)

    # Trips outside any test body (module import, setUpModule, setUpClass, a fixture that swallowed
    # the error) are not seen by ``run``: account for them when the whole run ends.
    original_stop = unittest.TestResult.stopTestRun
    ORIGINALS["unittest.TestResult.stopTestRun"] = original_stop

    def stopTestRun(self):
        left = [t for t in TRIPS if not t["acked"]]
        if left:
            for trip in left:
                trip["acked"] = True
            self.addFailure(_accounting_case(), _violation(
                f"{len(left)} guard trip(s) happened outside any test body (module import, setUpModule or "
                f"setUpClass) and were not acknowledged ({', '.join(sorted({t['entry'] for t in left}))}); "
                "something caught the guard's error there, so whatever it protected passed unobserved."))
        broken = guard_status()
        if broken:
            self.addFailure(_accounting_case(), _violation(f"The isolation guard is not intact at the end of the run "
                                                      f"({', '.join(broken)})."))
        return original_stop(self)

    _put(unittest.TestResult, "stopTestRun", stopTestRun)
    return []


install()
