#!/usr/bin/env python3
"""PreToolUse guard for the Proxmox lab agent: audit plus best-effort mistake prevention.

THIS IS NOT A SECURITY BOUNDARY. Bash rules and hooks match command text, which other
text can evade. The boundaries are Proxmox RBAC (routine token), the forced-command
snippet writer, and the root key never being usable inside an agent session. See
.agents/plans/proxmox-admin-agent-plan.md § 4.

What it does:
  * denies, for every agent: running host-run, touching the root key file or naming the
    variable that holds its path, and (inside the pve-lab agent or for lab commands) ssh-add,
    so a mistaken call fails fast instead of hanging on a passphrase prompt. The names are
    also read through shell quoting, a backslash, $'...', ${IFS}, an empty ${name}, a brace
    list and a glob with enough literal characters, and after any wrapper (command, env,
    exec, bash -c, a here-string): the text is searched for the name, not parsed. A brace list that expands beyond 1024
    words, or a word over 8 KiB that holds one, is denied as too complex to inspect;
  * inside the pve-lab agent: allows ssh only as `ssh [-T] pve-snip WORD...` (no option, no
    scp or sftp, no word the shell expands first), denies the other connection tools, and
    refuses to work in bypassPermissions or with an unknown/missing permission mode;
  * blocks (exit 2) an input it cannot read or decode strictly as UTF-8, an input over 4 MiB,
    an event with a wrong field type (an explicit null included), a decision it cannot
    deliver, and any internal error, instead of passing the call;
  * appends one redacted JSON line per lab-relevant call to the audit log.
Not catchable by a text match: a name built by a command substitution or by concatenating
variables, a payload decoded at run time, a script file written first and run later, and any
program that opens a connection by another name. See lab-agent/proposed/README.md.
Registered with "onFailure": "block": if this script crashes or times out, the call is blocked.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

KNOWN_MODES = {"default", "plan", "acceptEdits", "auto", "dontAsk", "bypassPermissions"}
LAB_AGENT = "pve-lab"

# Names are matched at a word edge: not inside a longer name, but after any other character,
# so /usr/bin/ssh, "ssh, =ssh, {ssh and the like are all seen. Still a text match.
_HOST_RUN = re.compile(r"(?<![\w-])host-run(?![\w-])")
_ROOT_KEY_NAME = "corelab-pve-root"
# PVE_ROOT_KEY is the variable that names the key file: naming it is naming the key.
_ROOT_KEY = re.compile(r"corelab-pve-root|PVE_ROOT_KEY")
_SSH_ADD = re.compile(r"(?<![\w.-])ssh-add(?![\w-])")
_SSH = re.compile(r"(?<![\w.-])(?P<tool>ssh|scp|sftp)(?![\w.-])(?P<args>[^;&|\n]*)")
_LAB_HINT = re.compile(r"lab[-_]agent|pve-snip|corelab|proxmox|PVE_LAB|PVE_ROOT", re.I)

# Rewrites that undo shell quoting and empty expansions, so that h"ost"-run, \ssh, $'\x73sh',
# ss${x}h and ssh${IFS}other are read the way the shell reads them. An unset or empty
# variable is assumed for ${name}; a command substitution that builds a name is not undone.
_ANSI_C = re.compile(r"\$'((?:[^'\\]|\\.)*)'", re.S)
_ANSI_ESC = re.compile(r"\\(x[0-9a-fA-F]{1,2}|[0-7]{1,3}|u[0-9a-fA-F]{1,4}|U[0-9a-fA-F]{1,8}|.)", re.S)
_IFS = re.compile(r"\$\{IFS[^}]*\}|\$IFS(?![A-Za-z0-9_])")
_EMPTY_EXPANSION = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}|\$[@*]|``|\$\(\)")
_WORD = re.compile(r"[^\s;&|<>()`]+")
_GLOB_CHARS = "*?[]!^"
_OWNER_ONLY = (("host-run", _HOST_RUN, ("host-run",)),
               ("root-key", _ROOT_KEY, (_ROOT_KEY_NAME, _ROOT_KEY_NAME + ".pub")))
_MIN_GLOB_LITERALS = 5  # a pattern needs this many literal characters to count as naming a file
_REDACT = [
    (re.compile(r"PVEAPIToken=[^\s'\"]+"), "PVEAPIToken=<redacted>"),
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.S),
     "<redacted-private-key>"),
    (re.compile(r"(?i)((?:password|secret|token_value)\"?\s*[:=]\s*)\S+"), r"\1<redacted>"),
    (re.compile(r"CORELAB_TOKEN_SECRET=\S+"), "CORELAB_TOKEN_SECRET=<redacted>"),
]


def redact(text: str) -> str:
    for pattern, repl in _REDACT:
        text = pattern.sub(repl, text)
    return text


def _ansi_c_text(body: str) -> str:
    """The text of a $'...' string with its escapes decoded."""
    def one(m: re.Match) -> str:
        esc = m.group(1)
        try:
            if esc[0] == "x" or esc[0] in "uU" and len(esc) > 1:
                return chr(int(esc[1:], 16))
            if all(c in "01234567" for c in esc):
                return chr(int(esc, 8))
        except (ValueError, OverflowError):
            return ""
        return {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}.get(esc, esc)
    return _ANSI_ESC.sub(one, body)


def _unquote(command: str) -> str:
    """The command with shell quoting undone. Variables and substitutions are left in place."""
    text = command.replace("\\\n", "")
    text = _ANSI_C.sub(lambda m: _ansi_c_text(m.group(1)), text)
    text = _IFS.sub(" ", text)
    return text.replace("\\", "").replace("'", "").replace('"', "")


def _forms(command: str) -> list[str]:
    """The command as written, unquoted, and unquoted with empty expansions removed."""
    plain = _unquote(command)
    return list(dict.fromkeys([command, plain, _EMPTY_EXPANSION.sub("", plain)]))


class _Uninspectable(Exception):
    """The command is too complex to be inspected completely. The guard denies it: it does not
    inspect part of it and pass the rest."""


_BRACE_GROUP = re.compile(r"\{([^{}]*,[^{}]*)\}")
_MAX_BRACE_WORD = 8192  # characters in one word that holds a brace list
_MAX_BRACE_RESULTS = 1024  # words one brace list may expand to


def _brace_expand(word: str) -> list[str]:
    """Comma brace expansion, as bash does it. Raises _Uninspectable beyond the two limits."""
    if not _BRACE_GROUP.search(word):
        return [word]
    if len(word) > _MAX_BRACE_WORD:
        raise _Uninspectable("a word with a brace list is over the inspection limit")
    words = [word]
    while True:
        expanded, changed = [], False
        for w in words:
            m = _BRACE_GROUP.search(w)
            if m is None:
                expanded.append(w)
                continue
            changed = True
            expanded.extend(w[:m.start()] + alt + w[m.end():] for alt in m.group(1).split(","))
            if len(expanded) > _MAX_BRACE_RESULTS:
                raise _Uninspectable("a brace list expands beyond the inspection limit")
        words = expanded
        if not changed:
            return words


def _owner_only_name(text: str) -> str | None:
    """'host-run' or 'root-key' when a word of `text` spells the name, or 'uninspectable' when
    a brace list is too large to expand, after brace expansion,
    as a path component, or as a glob with enough literal characters to be that file."""
    for label, spelled, _names in _OWNER_ONLY:
        if spelled.search(text):
            return label
    for word in _WORD.findall(text):
        if not any(c in word for c in "*?[{"):
            continue  # only a brace list or a glob can spell the name without writing it
        try:
            expansions = _brace_expand(word)
        except _Uninspectable:
            return "uninspectable"
        for expanded in expansions:
            for part in (expanded, *re.split(r"[/=:,]", expanded)):
                if not part:
                    continue
                globbed = any(c in part for c in "*?[")
                literals = sum(1 for c in part if c not in _GLOB_CHARS)
                for label, spelled, names in _OWNER_ONLY:
                    if spelled.search(part):
                        return label
                    if globbed and literals >= _MIN_GLOB_LITERALS and any(
                            fnmatch.fnmatchcase(n, part) for n in names):
                        return label
    return None


def _owner_only(forms: list[str]) -> str | None:
    for text in forms:
        label = _owner_only_name(text)
        if label:
            return label
    return None


def state_dir(env: dict[str, str]) -> Path:
    if env.get("PVE_LAB_STATE"):
        return Path(env["PVE_LAB_STATE"]).expanduser()
    base = env.get("XDG_STATE_HOME") or os.path.join(env.get("HOME", "~"), ".local", "state")
    return Path(base).expanduser() / "corelab-lab-agent"


# Inside the lab agent only: other ways to open a connection or to run text that was built
# elsewhere. None of them is part of the agent's routine work.
_SSH_OTHER = re.compile(
    r"(?<![\w.-])(?:ssh-agent|ssh-keyscan|ssh-keygen|ssh-copy-id|sshpass|autossh|mosh|sshfs|rsync"
    r"|socat|ncat|netcat|nc|telnet|eval)(?![\w.-])"
    r"|/dev/(?:tcp|udp)/|GIT_SSH|sshCommand|base64\s+(?:-d|--decode)|xxd\s+-r")
_EXPANDS = ("$", "`", "*", "?", "[", "{")  # a word that the shell rewrites before ssh sees it


def _redirect_target_ok(target: str) -> bool:
    """A redirect target may name a variable, but it may not run anything: a command or process
    substitution would hide a command from the checks that read the rest of the line."""
    return not any(s in target for s in ("(", ")", "`"))


def _ssh_form_ok(text: str) -> bool:
    """One reading of the command. Inside the lab agent, ssh is allowed only as
    `ssh [-T] pve-snip WORD...`: no option anywhere (ssh also parses options written without a
    space, -oX or -F/x, and options after the destination), no scp or sftp, and no WORD that the
    shell expands first, because an expansion can produce an option. A redirect target may
    name a variable, but no command or process substitution. Still a text match and not a boundary: the host's from=
    restriction and forced command are."""
    if _SSH_OTHER.search(text):
        return False
    for m in _SSH.finditer(text):
        if m.group("tool") != "ssh":
            return False
        words = m.group("args").split()
        if words[:1] == ["-T"]:
            words = words[1:]
        if words[:1] != ["pve-snip"] or len(words) < 2:  # the alias alone would open a session
            return False
        redirect = False
        for word in words[1:]:
            if word.startswith("-"):
                return False
            if redirect:
                redirect = False
                if not _redirect_target_ok(word):
                    return False
                continue
            op = re.match(r"\d*[<>]+", word)
            if op:
                rest = word[op.end():]
                redirect = not rest
                if rest and not _redirect_target_ok(rest):
                    return False
                continue
            if any(c in word for c in _EXPANDS):
                return False
    return True


def _ssh_targets_ok(command: str) -> bool:
    """Inside the lab agent, every reading of the command (as written, unquoted, and with empty
    expansions removed) must pass _ssh_form_ok."""
    return all(_ssh_form_ok(form) for form in _forms(command))


def decide(event: dict) -> tuple[str | None, str, bool]:
    """Return (decision or None, reason, relevant-for-audit)."""
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    agent = event.get("agent_type") or ""
    mode = event.get("permission_mode")
    in_lab_agent = agent == LAB_AGENT
    is_pve_mcp = tool.startswith("mcp__pve__")
    command = tool_input.get("command", "") if tool == "Bash" else ""
    forms = _forms(command) if command else []
    owner_only = _owner_only(forms)
    lab_hint = any(_LAB_HINT.search(f) for f in forms)
    relevant = is_pve_mcp or in_lab_agent or lab_hint or owner_only is not None

    if tool == "Bash":
        if owner_only == "host-run":
            return "deny", "host-run is owner-only: run it yourself in a terminal no agent controls", True
        if owner_only == "uninspectable":
            return "deny", "the command holds a brace list too large for the guard to inspect", True
        if owner_only == "root-key":
            return "deny", "the root key is never used from an agent session", True
        if any(_SSH_ADD.search(f) for f in forms) and (in_lab_agent or lab_hint):
            return "deny", "keys for the lab are never loaded into an ssh-agent", True

    if in_lab_agent or is_pve_mcp:
        if mode not in KNOWN_MODES:
            return "deny", f"unknown or missing permission_mode {mode!r}; refusing lab operations", True
        if mode == "bypassPermissions":
            return "deny", "the lab agent does not run in bypassPermissions", True
        if tool == "Bash" and in_lab_agent and not _ssh_targets_ok(command):
            return "deny", "the lab agent may only ssh to pve-snip (snippet writer)", True

    return None, "", relevant


def audit(event: dict, decision: str | None, reason: str, env: dict[str, str]) -> None:
    tool_input = json.dumps(event.get("tool_input") or {}, sort_keys=True)
    entry = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session": event.get("session_id"),
        "agent_type": event.get("agent_type"),
        "permission_mode": event.get("permission_mode"),
        "tool": event.get("tool_name"),
        "input": redact(tool_input)[:4000],
        "decision": decision or "pass",
        "reason": reason,
    }
    directory = state_dir(env)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(directory / "audit.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


MAX_INPUT = 4 * 1024 * 1024  # bytes. No hook event is near this; anything larger is not inspected.


def _say(message: str) -> None:
    """Write to stderr; a closed or broken stderr must not turn a block into a crash, and its
    unflushed text must not fail a second time at interpreter exit."""
    try:
        print(message, file=sys.stderr)
        sys.stderr.flush()
    except Exception:
        _abandon_stdout(sys.stderr)


def _read_event_text(stdin) -> str:
    """The event as text: read as bytes, bounded, and decoded strictly (no surrogateescape)."""
    source = getattr(stdin, "buffer", stdin)  # a real stdin has a binary layer; a test stream may not
    data = source.read(MAX_INPUT + 1)
    if len(data) > MAX_INPUT:
        raise ValueError("hook input is larger than the inspection limit")
    return data.decode("utf-8") if isinstance(data, bytes) else data


def _abandon_stdout(stdout) -> None:
    """After a failed write, point the descriptor at the null device, so that whatever is still
    buffered cannot fail a second time when the interpreter exits (that exit was status 120)."""
    try:
        null = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(null, stdout.fileno())
        finally:
            os.close(null)
    except Exception:
        pass


def validate_event(event: dict) -> None:
    """Raise ValueError for an event the guard cannot reason about; main() then blocks.

    A hook payload that is not what the harness documents is not trusted to be harmless:
    the call is blocked instead of being passed on a guess. An optional field may be absent,
    but if it is present it must have its type: an explicit null is a wrong type, not an absence.
    """
    tool = event.get("tool_name")
    if not isinstance(tool, str) or not tool:
        raise ValueError("tool_name is missing or not a string")
    for key, kind in (("tool_input", dict), ("agent_type", str), ("permission_mode", str)):
        if key in event and not isinstance(event[key], kind):
            raise ValueError(f"{key} is present but not {kind.__name__}")
    if tool == "Bash" and not isinstance(event.get("tool_input", {}).get("command"), str):
        raise ValueError("the Bash command is missing or not a string")


def main(stdin=sys.stdin, stdout=sys.stdout, env=None) -> int:
    env = dict(os.environ if env is None else env)
    try:
        event = json.loads(_read_event_text(stdin))
        if not isinstance(event, dict):
            raise ValueError("event is not an object")
        validate_event(event)
    except Exception as exc:  # also RecursionError and UnicodeDecodeError: fail closed
        _say(f"pve-guard: unreadable or malformed hook input ({type(exc).__name__}): {exc}")
        return 2  # block: fail closed
    try:
        decision, reason, relevant = decide(event)
    except Exception as exc:  # fail closed here too; do not rely only on the harness's onFailure
        _say(f"pve-guard: internal error, blocking ({type(exc).__name__})")
        return 2
    if relevant:
        try:
            audit(event, decision, reason, env)
        except Exception as exc:  # a lab call that cannot be audited does not run
            _say(f"pve-guard: cannot write the audit log ({type(exc).__name__}): {exc}")
            return 2
    if decision:
        try:
            stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                           "permissionDecision": decision,
                                                           "permissionDecisionReason": reason}}))
            stdout.flush()
        except Exception as exc:  # the decision could not be delivered: block, and never flush again
            _say(f"pve-guard: cannot write the decision, blocking ({type(exc).__name__})")
            _abandon_stdout(stdout)
            return 2
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except BaseException as exc:  # last resort: still exit 2, never 1
        _say(f"pve-guard: unexpected failure, blocking ({type(exc).__name__})")
        _abandon_stdout(sys.stdout)
        code = 2
    sys.exit(code)
