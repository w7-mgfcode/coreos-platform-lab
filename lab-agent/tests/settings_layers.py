"""Pure checks of the guard-hook registration across Claude Code settings layers.

Claude Code merges hooks across the user, project and local settings files, and applies deny
rules from every scope. Since 2026-11-16 the guard registration and the lab permission entries
live in the untracked local settings file, not in the tracked `.claude/settings.json`.

`evaluate()` takes a list of already parsed settings layers (dictionaries) and returns a report
of names, counts and booleans only. It never returns a value read from a layer, so a caller may
print the report. It is used by the unit tests with synthetic layers and by the hand-run
checkout script `check_local_settings.py`. No unit test reads the real local settings file.
"""

GUARD_SCRIPT = "pve-guard.py"
GUARD_ARG_SUFFIX = "/.claude/hooks/" + GUARD_SCRIPT
REQUIRED_MATCHER_ALTERNATIVES = ("Bash", "mcp__pve__.*")
ALLOW_ENTRY = "mcp__pve__*"
MCP_DENY_PREFIX = "mcp__pve__"
READ_DENY_PREFIX = "Read(~/"


def _pre_tool_use_entries(layer):
    hooks = layer.get("hooks")
    if not isinstance(hooks, dict):
        return []
    entries = hooks.get("PreToolUse")
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def _mentions_guard(handler):
    """True if any string in the handler (command or args) names the guard script."""
    strings = [handler.get("command")]
    args = handler.get("args")
    if isinstance(args, list):
        strings.extend(args)
    return any(isinstance(s, str) and GUARD_SCRIPT in s for s in strings)


def _matcher_covers(matcher):
    """Structural check: the matcher's `|` alternatives include `Bash` and `mcp__pve__.*`."""
    if not isinstance(matcher, str):
        return False
    alternatives = {part.strip() for part in matcher.split("|")}
    return all(a in alternatives for a in REQUIRED_MATCHER_ALTERNATIVES)


def _form_ok(handler):
    """The `python3` plus `args` form, with exactly one argument naming the guard script."""
    args = handler.get("args")
    return (handler.get("type") == "command"
            and handler.get("command") == "python3"
            and isinstance(args, list) and len(args) == 1
            and isinstance(args[0], str) and args[0].endswith(GUARD_ARG_SUFFIX))


def _handler_unconditional(handler):
    """True if the handler carries none of the keys that could narrow or loosen it: an `if`
    filter (the guard would run for some calls only), `async` (the call would not wait for the
    verdict) or `once` (it would run once). Key names follow the documented hook schema; that the
    installed harness honours them is not checked here (harness behaviour, LA-HARNESS)."""
    return not handler.get("if") and not handler.get("async") and not handler.get("once")


def _hooks_disabled(layer):
    """`disableAllHooks` set in a layer switches every hook off, the guard included."""
    return layer.get("disableAllHooks") is True


def _permission_list(layer, key):
    perms = layer.get("permissions")
    if not isinstance(perms, dict):
        return []
    entries = perms.get(key)
    return [e for e in entries if isinstance(e, str)] if isinstance(entries, list) else []


def evaluate(layers):
    """Report the guard registration and the lab permission entries across `layers`.

    Every handler naming the guard script counts as a registration, also an identical copy
    (stricter than any de-duplication the harness may do). The report is valid (`ok`) only
    when there is exactly one registration, its matcher covers `Bash` and `mcp__pve__.*`, it
    uses the `python3` plus `args` form, its `onFailure` is `block`, the handler has no `if`,
    `async` or `once` key, and no layer sets `disableAllHooks`. The allow and deny
    entries are reported but do not decide `ok`: whether `mcp__pve__*` is allowed for every
    session is an open owner decision (SET-1).
    """
    problems = []
    registrations = []  # (layer index, matcher, handler)
    per_layer = []
    allow_entry = False
    mcp_deny = 0
    read_deny = 0
    disabled_in = []
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            problems.append(f"layer {index} is not a JSON object")
            per_layer.append(0)
            continue
        if _hooks_disabled(layer):
            disabled_in.append(index)
        found = 0
        for entry in _pre_tool_use_entries(layer):
            handlers = entry.get("hooks")
            if not isinstance(handlers, list):
                continue
            for handler in handlers:
                if isinstance(handler, dict) and _mentions_guard(handler):
                    registrations.append((index, entry.get("matcher"), handler))
                    found += 1
        per_layer.append(found)
        allow_entry = allow_entry or ALLOW_ENTRY in _permission_list(layer, "allow")
        deny = _permission_list(layer, "deny")
        mcp_deny += sum(1 for d in deny if d.startswith(MCP_DENY_PREFIX))
        read_deny += sum(1 for d in deny if d.startswith(READ_DENY_PREFIX))

    single = registrations[0] if len(registrations) == 1 else None
    matcher_ok = single is not None and _matcher_covers(single[1])
    form_ok = single is not None and _form_ok(single[2])
    on_failure_present = single is not None and "onFailure" in single[2]
    blocking = single is not None and single[2].get("onFailure") == "block"
    unconditional = single is not None and _handler_unconditional(single[2])

    if disabled_in:
        problems.append("hooks are disabled (disableAllHooks) in a layer")
    if not registrations:
        problems.append("no guard registration in any layer")
    elif len(registrations) > 1:
        problems.append(f"{len(registrations)} guard registrations, exactly 1 expected")
    else:
        if not matcher_ok:
            problems.append("matcher does not cover both Bash and mcp__pve__.*")
        if not form_ok:
            problems.append("registration is not the python3 plus args form naming pve-guard.py")
        if not on_failure_present:
            problems.append("onFailure is missing")
        elif not blocking:
            problems.append("onFailure is not block")
        if not unconditional:
            problems.append("registration is conditional, asynchronous or once-only")

    return {
        "registrations": len(registrations),
        "registrations_per_layer": per_layer,
        "registered_in_layers": [r[0] for r in registrations],
        "matcher_covers_bash_and_mcp_pve": matcher_ok,
        "python3_args_form": form_ok,
        "on_failure_present": on_failure_present,
        "on_failure_block": blocking,
        "registration_unconditional": unconditional,
        "hooks_disabled_in_layers": disabled_in,
        "allow_entry_present": allow_entry,
        "mcp_pve_deny_entries": mcp_deny,
        "read_home_deny_entries": read_deny,
        "problems": problems,
        "ok": not problems,
    }
