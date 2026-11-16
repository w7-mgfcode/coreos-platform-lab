"""The guard hook (run as a real subprocess, as Claude Code runs it) and repository hygiene."""

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from lab_agent import mcp, redact
from tests import fixtures, settings_layers

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / ".claude" / "hooks" / "pve-guard.py"  # the active hook: a local-only file, absent in a clean clone
ACTIVE_HOOK = HOOK
CANDIDATE_HOOK = REPO / "lab-agent" / "proposed" / "hooks" / "pve-guard.py"  # in the tree: always tested
MCP_EXAMPLE = REPO / "lab-agent" / "mcp.example.json"  # in the tree: always checked
MCP_LOCAL = REPO / ".mcp.json"  # local-only: checked in addition when it exists
# The hook scripts name ssh, scp and sftp in their text. The test-isolation guard (tests/__init__.py)
# lets such a script run only if those tools resolve, on the PATH the child gets, to a vetted stub or
# to nothing. The hook needs no tool from PATH, so the child gets a PATH on which nothing resolves.
HOOK_PATH = "/nonexistent-path-for-hook-tests"
COMMIT_HOOK_COMMAND = 'bash "${CLAUDE_PROJECT_DIR}/.claude/hooks/check-commit-format.sh"'


def bash(cmd, agent=None, mode="default"):
    ev = {"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": "Bash",
          "tool_input": {"command": cmd}}
    if mode is not None:
        ev["permission_mode"] = mode
    if agent:
        ev["agent_type"] = agent
    return ev


def mcp_call(tool="mcp__pve__list_vms", mode="default", agent="pve-lab"):
    ev = {"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": tool,
          "tool_input": {"node": "pve-test"}, "agent_type": agent}
    if mode is not None:
        ev["permission_mode"] = mode
    return ev


class HookRunner:
    """Runs a hook file as Claude Code does: a subprocess, a synthetic event on stdin, a private
    temporary state directory. `HOOK` names the file. Not a TestCase: nothing is collected here."""

    HOOK = None

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.state = Path(self.tmp.name) / "state"

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, event, raw=None, state=None):
        env = {"PATH": HOOK_PATH, "PVE_LAB_STATE": str(state or self.state), "HOME": self.tmp.name}
        proc = subprocess.run([sys.executable, str(self.HOOK)], input=raw if raw is not None else json.dumps(event),
                              text=True, capture_output=True, env=env, timeout=10)
        decision = None
        if proc.stdout.strip():
            decision = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]
        return proc.returncode, decision, proc

    def audit_lines(self):
        path = self.state / "audit.jsonl"
        return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []


class HookContract(HookRunner):
    """The behaviour every guard hook file must keep. Still not a TestCase, so unittest collects
    nothing from it: `CandidateHookTests` runs it against the in-tree candidate hook (always), and
    `HookTests` against the active hook where this checkout has it."""

    def test_routine_mcp_call_passes_and_is_audited(self):
        code, decision, _ = self.run_hook(mcp_call())
        self.assertEqual((code, decision), (0, None))
        self.assertEqual(self.audit_lines()[0]["tool"], "mcp__pve__list_vms")

    def test_privileged_paths_denied_for_everyone(self):
        for cmd in ("lab-agent/bin/host-run run prepare", "./host-run run x", "python3 x && host-run list",
                    "ssh -i ~/.ssh/corelab-pve-root root@h", "cat ~/.ssh/corelab-pve-root"):
            code, decision, _ = self.run_hook(bash(cmd))
            self.assertEqual((code, decision), (0, "deny"), cmd)

    def test_ssh_add_denied_for_lab_context_only(self):
        self.assertEqual(self.run_hook(bash("ssh-add -l", agent="pve-lab"))[1], "deny")
        self.assertEqual(self.run_hook(bash("ssh-add ~/.ssh/corelab-snip"))[1], "deny")
        self.assertIsNone(self.run_hook(bash("ssh-add -l"))[1])  # unrelated session use is not ours to police

    def test_lab_agent_ssh_only_to_pve_snip(self):
        self.assertIsNone(self.run_hook(bash("ssh pve-snip put demo < d.ign", agent="pve-lab"))[1])
        self.assertIsNone(self.run_hook(bash("ssh -T pve-snip list", agent="pve-lab"))[1])
        for cmd in ("ssh root@192.0.2.10 id", "ssh pve-root id", "scp x pve-snip:/tmp/", "true; ssh other id"):
            self.assertEqual(self.run_hook(bash(cmd, agent="pve-lab"))[1], "deny", cmd)

    def test_unsupported_modes_fail_safe(self):
        self.assertEqual(self.run_hook(mcp_call(mode="bypassPermissions"))[1], "deny")
        self.assertEqual(self.run_hook(mcp_call(mode=None))[1], "deny")
        self.assertEqual(self.run_hook(mcp_call(mode="yolo"))[1], "deny")
        self.assertIsNone(self.run_hook(mcp_call(mode="dontAsk"))[1])
        self.assertIsNone(self.run_hook(bash("ls", mode=None))[1])  # unrelated calls untouched

    def test_malformed_input_blocks(self):
        self.assertEqual(self.run_hook(None, raw="not json")[0], 2)
        self.assertEqual(self.run_hook(None, raw="[1,2]")[0], 2)

    def test_audit_failure_blocks_lab_calls(self):
        blocker = Path(self.tmp.name) / "file-not-dir"
        blocker.write_text("x")
        code, _, proc = self.run_hook(mcp_call(), state=blocker / "sub")
        self.assertEqual(code, 2, proc.stderr)
        code, _, _ = self.run_hook(bash("ls"), state=blocker / "sub")
        self.assertEqual(code, 0)  # not lab-relevant, not audited, not blocked

    def test_audit_redacts_and_ignores_unrelated(self):
        self.run_hook(bash("curl -H 'Authorization: PVEAPIToken=u@pve!lab=SECRETVALUE' https://x/proxmox"))
        self.run_hook(bash("ls -la"))
        lines = self.audit_lines()
        self.assertEqual(len(lines), 1)
        self.assertNotIn("SECRETVALUE", json.dumps(lines))
        self.assertEqual((self.state / "audit.jsonl").stat().st_mode & 0o777, 0o600)


class CandidateHookTests(HookContract, unittest.TestCase):
    """The in-tree candidate hook: always present, so always tested, in a clean clone too."""

    HOOK = CANDIDATE_HOOK

    def test_the_hook_under_test_exists(self):
        # A contract run against a missing file would fail in every test anyway; this names the
        # reason once, so that nothing can pass without having run a hook.
        self.assertTrue(self.HOOK.is_file(), "the in-tree candidate hook is missing")


if ACTIVE_HOOK.is_file():
    # Defined only where the local-only active hook exists, so that a clean clone neither fails
    # nor skips: there the candidate class above is the one that runs the contract.
    class HookTests(HookContract, unittest.TestCase):
        """The active hook, unchanged by this mission: the gate tests exactly this file."""

        HOOK = ACTIVE_HOOK


class RepoHygieneTests(unittest.TestCase):
    """Files that would be published must hold no secret and no lab-private value."""

    TRACKED = [REPO / ".mcp.json", REPO / ".claude" / "settings.json", REPO / ".claude" / "agents" / "pve-lab.md",
               HOOK, REPO / ".agents" / "plans" / "proxmox-admin-agent-plan.md"]

    def candidate_files(self):
        files = [p for p in self.TRACKED if p.exists()]
        for p in (REPO / "lab-agent").rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts and not p.is_symlink():
                files.append(p)
        return files

    def test_no_secrets_or_private_addresses(self):
        allowed_uuid_files = {"test_config_redact_api.py", "test_hostrun.py", "pvestub.py"}
        for path in self.candidate_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            findings = [f for f in redact.scan(text) if not f.startswith("mail")]
            if path.name in allowed_uuid_files or path.parent.name == "tests":
                # Tests carry deliberate fake secrets and IPs to prove redaction works.
                findings = [f for f in findings if "UUID" not in f and "IPv4" not in f and "MAC" not in f
                            and "token" not in f and "private key" not in f]
            self.assertEqual(findings, [], str(path.relative_to(REPO)))

    def test_no_home_paths_or_old_working_name(self):
        for path in self.candidate_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertIsNone(re.search(r"/home/[a-z]", text), str(path.relative_to(REPO)))

    def test_no_tls_bypass(self):
        pattern = re.compile(r"curl\s[^\n]*\s(-k|--insecure)\b|verify\s*=\s*False|VERIFY_SSL\s*=\s*(\"|')?false",
                             re.I)
        for path in self.candidate_files():
            if path.name.startswith("test_"):
                continue
            self.assertIsNone(pattern.search(path.read_text(errors="replace")), str(path.relative_to(REPO)))

    def test_mcp_entry_holds_no_credentials(self):
        # The in-tree example is always checked; the local .mcp.json too, when this checkout has it.
        paths = [p for p in (MCP_EXAMPLE, MCP_LOCAL) if p.is_file()]
        self.assertIn(MCP_EXAMPLE, paths, "the in-tree MCP example is missing: nothing would be checked")
        for path in paths:
            cfg = json.loads(path.read_text(encoding="utf-8"))
            server = cfg["mcpServers"]["pve"]
            self.assertNotIn("env", server, path.name)
            self.assertNotIn("TOKEN", json.dumps(cfg), path.name)

    def test_settings_json_is_valid_keeps_commit_hook_and_holds_no_lab_tooling(self):
        # Only the tracked file. Since 2026-11-16 the guard registration and the lab permission
        # entries live in the untracked local settings file, which no unit test reads; the
        # layering itself is tested with synthetic layers in SettingsLayerTests, and this
        # checkout's effective registration is checked by hand with check_local_settings.py.
        text = (REPO / ".claude" / "settings.json").read_text(encoding="utf-8")
        cfg = json.loads(text)
        commands = [h.get("command") for entry in cfg["hooks"]["PreToolUse"] for h in entry["hooks"]]
        self.assertIn(COMMIT_HOOK_COMMAND, commands)
        for marker in ("pve-guard", "mcp__pve__", "Read(~/"):
            self.assertNotIn(marker, text)
        self.assertEqual(settings_layers.evaluate([cfg])["registrations"], 0)

    def test_mcp_pin_is_a_full_commit(self):
        self.assertRegex(mcp.PIN["commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(mcp.protected_vmids(9100, 9199), "100-9099,9200-109199")
        self.assertEqual(mcp.protected_vmids(100, 199), "200-100199")


# Synthetic settings layers. None of these is read from disk.
SYN_GUARD_ARG = "${CLAUDE_PROJECT_DIR}/.claude/hooks/pve-guard.py"
SYN_SECRET_LOOKING_VALUE = "SYNTHETIC-VALUE-NEVER-REPORTED"


def syn_guard_handler(**changes):
    handler = {"type": "command", "command": "python3", "args": [SYN_GUARD_ARG], "timeout": 5,
               "onFailure": "block"}
    for key, value in changes.items():
        if value is None:
            handler.pop(key, None)
        else:
            handler[key] = value
    return handler


def syn_guard_layer(matcher="Bash|mcp__pve__.*", **changes):
    return {
        "permissions": {"allow": ["mcp__pve__*"],
                        "deny": ["mcp__pve__node_shutdown", "mcp__pve__delete_pool", "Read(~/.config/x/**)"]},
        "hooks": {"PreToolUse": [{"matcher": matcher, "hooks": [syn_guard_handler(**changes)]}]},
    }


def syn_commit_layer():
    return {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": COMMIT_HOOK_COMMAND, "timeout": 5}]}]}}


class SettingsLayerTests(unittest.TestCase):
    """The guard registration across settings layers, on synthetic layers only."""

    def test_registration_in_second_layer_only_passes(self):
        report = settings_layers.evaluate([syn_commit_layer(), syn_guard_layer()])
        self.assertEqual(report["problems"], [])
        self.assertTrue(report["ok"])
        self.assertEqual(report["registrations_per_layer"], [0, 1])
        self.assertEqual(report["registered_in_layers"], [1])
        self.assertTrue(report["on_failure_block"])
        self.assertTrue(report["allow_entry_present"])
        self.assertEqual((report["mcp_pve_deny_entries"], report["read_home_deny_entries"]), (2, 1))

    def test_registration_in_first_layer_only_passes(self):
        report = settings_layers.evaluate([syn_guard_layer(), {}])
        self.assertTrue(report["ok"], report["problems"])
        self.assertEqual(report["registered_in_layers"], [0])

    def test_no_registration_fails(self):
        layer = syn_guard_layer()
        del layer["hooks"]
        report = settings_layers.evaluate([syn_commit_layer(), layer])
        self.assertFalse(report["ok"])
        self.assertEqual(report["problems"], ["no guard registration in any layer"])
        self.assertTrue(report["allow_entry_present"])  # the permission entries alone are not enough

    def test_missing_on_failure_fails(self):
        report = settings_layers.evaluate([syn_commit_layer(), syn_guard_layer(onFailure=None)])
        self.assertFalse(report["ok"])
        self.assertEqual(report["problems"], ["onFailure is missing"])
        self.assertTrue(report["matcher_covers_bash_and_mcp_pve"] and report["python3_args_form"])

    def test_on_failure_other_than_block_fails(self):
        report = settings_layers.evaluate([syn_guard_layer(onFailure="continue")])
        self.assertEqual(report["problems"], ["onFailure is not block"])

    def test_wrong_matcher_fails(self):
        for matcher in ("Bash", "mcp__pve__.*", "Bash|mcp__pve__list_vms", None):
            report = settings_layers.evaluate([syn_commit_layer(), syn_guard_layer(matcher=matcher)])
            self.assertFalse(report["ok"], matcher)
            self.assertEqual(report["problems"], ["matcher does not cover both Bash and mcp__pve__.*"], matcher)
            self.assertTrue(report["on_failure_block"] and report["python3_args_form"], matcher)

    def test_wrong_form_fails(self):
        for changes in ({"command": "python3 " + SYN_GUARD_ARG, "args": None},
                        {"command": "bash"},
                        {"args": [SYN_GUARD_ARG, "--extra"]}):
            report = settings_layers.evaluate([syn_guard_layer(**changes)])
            self.assertEqual(report["problems"],
                             ["registration is not the python3 plus args form naming pve-guard.py"], changes)

    def test_registered_twice_with_different_text_fails(self):
        first, second = syn_guard_layer(), syn_guard_layer(timeout=10)
        # Control: each layer alone is a valid registration, so the failure below is the count.
        self.assertTrue(settings_layers.evaluate([first])["ok"])
        self.assertTrue(settings_layers.evaluate([second])["ok"])
        report = settings_layers.evaluate([first, second])
        self.assertFalse(report["ok"])
        self.assertEqual(report["problems"], ["2 guard registrations, exactly 1 expected"])
        self.assertEqual(report["registered_in_layers"], [0, 1])

    def test_non_object_layer_is_a_problem(self):
        report = settings_layers.evaluate([[], syn_guard_layer()])
        self.assertEqual(report["problems"], ["layer 0 is not a JSON object"])

    def test_report_carries_no_value_from_a_layer(self):
        matcher_marker = "SyntheticMatcherMarker"
        layer = syn_guard_layer(matcher="Bash|mcp__pve__.*|" + matcher_marker)
        layer["permissions"]["allow"].append(SYN_SECRET_LOOKING_VALUE)
        layer["permissions"]["deny"].append("mcp__pve__" + SYN_SECRET_LOOKING_VALUE)
        report = settings_layers.evaluate([layer])
        self.assertTrue(report["ok"], report["problems"])  # control: the marker matcher still covers
        text = json.dumps(report)
        self.assertNotIn(SYN_SECRET_LOOKING_VALUE, text)
        self.assertNotIn(SYN_GUARD_ARG, text)
        self.assertNotIn(matcher_marker, text)
        # A failing matcher is reported as a boolean and a fixed problem text, never its value.
        bad = json.dumps(settings_layers.evaluate([syn_guard_layer(matcher=matcher_marker)]))
        self.assertNotIn(matcher_marker, bad)


if __name__ == "__main__":
    unittest.main()
