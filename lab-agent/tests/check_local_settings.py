#!/usr/bin/env python3
"""Hand-run check of THIS checkout's effective guard-hook registration.

Not a unit test and not part of the offline gate (`run.sh`): it depends on the untracked
`.claude/settings.local.json`, which a fresh clone does not have. Run it by hand from anywhere:

    python3 lab-agent/tests/check_local_settings.py

It reads `.claude/settings.json` and `.claude/settings.local.json` of the repository it lives
in, and prints names, counts and booleans only, never a value from either file.

Exit status: 0 when exactly one guard registration with a covering matcher, the `python3` plus
`args` form, `onFailure: block` and no `if`, `async` or `once` key is present across the two
files and neither sets `disableAllHooks`; 1 otherwise, or when a file that is present is not
valid JSON. It checks the files only: that the harness honours these keys is not shown here.
"""

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # leave no __pycache__ in lab-agent/, as run.sh does
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # also works under `python3 -I`, which does not add the script dir

import settings_layers  # noqa: E402

REPO = HERE.parents[1]
LAYERS = (".claude/settings.json", ".claude/settings.local.json")


def main():
    parsed = []
    names = []
    status = {}
    load_failed = False
    for name in LAYERS:
        path = REPO / name
        if not path.is_file():
            status[name] = "present=False"
            continue
        try:
            layer = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            status[name] = "present=True valid_json=False"
            load_failed = True
            continue
        parsed.append(layer)
        names.append(name)

    report = settings_layers.evaluate(parsed)
    for name, count in zip(names, report["registrations_per_layer"]):
        status[name] = f"present=True valid_json=True guard_registrations={count}"
    for name in LAYERS:
        print(f"layer {name}: {status[name]}")
    where = ", ".join(names[i] for i in report["registered_in_layers"]) or "none"
    print(f"guard registrations, total: {report['registrations']}")
    print(f"guard registered in: {where}")
    print(f"matcher covers Bash and mcp__pve__.*: {report['matcher_covers_bash_and_mcp_pve']}")
    print(f"python3 plus args form naming pve-guard.py: {report['python3_args_form']}")
    print(f"onFailure present: {report['on_failure_present']}")
    print(f"onFailure is block: {report['on_failure_block']}")
    print(f"registration has no if, async or once key: {report['registration_unconditional']}")
    disabled = ", ".join(names[i] for i in report["hooks_disabled_in_layers"]) or "none"
    print(f"disableAllHooks set in: {disabled}")
    print(f"allow entry mcp__pve__* present: {report['allow_entry_present']}")
    print(f"deny entries starting mcp__pve__: {report['mcp_pve_deny_entries']}")
    print(f"deny entries starting Read(~/: {report['read_home_deny_entries']}")
    for problem in report["problems"]:
        print(f"problem: {problem}")
    if load_failed or not report["ok"]:
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
