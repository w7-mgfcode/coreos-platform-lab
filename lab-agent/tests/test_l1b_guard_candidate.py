"""The candidate guard hook, the candidate agent definition and the refreshed patches.

Mission L1B, task LA-GUARD. Offline and synthetic: every hook run feeds a made-up event on
stdin and gives the hook a private temporary state directory, so the real audit log is never
touched. Nothing here installs anything. The active hook under .claude/hooks/ is only read.

A guard hook matches command text. It is a mistake-preventer and an audit layer, not a security
boundary, and a passing test here shows only that this text match does what these tests say.
"""

import hashlib
import io
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from lab_agent import redact
from tests import fixtures, settings_layers
from tests.test_hook_and_repo import HOOK_PATH, HookRunner, bash, mcp_call, syn_commit_layer, syn_guard_layer

REPO = Path(__file__).resolve().parents[2]
ACTIVE_HOOK = REPO / ".claude" / "hooks" / "pve-guard.py"
ACTIVE_AGENT = REPO / ".claude" / "agents" / "pve-lab.md"
PROPOSED = REPO / "lab-agent" / "proposed"
CAND_HOOK = PROPOSED / "hooks" / "pve-guard.py"
CAND_AGENT = PROPOSED / "agents" / "pve-lab.md"
PATCH_DIR = REPO / "lab-agent" / "docs" / "proposed-patches"
HOOK_PATCHES = ("pve-guard-fail-closed.patch", "pve-guard-absolute-path-ssh.patch",
                "pve-guard-ssh-alias-form.patch")
AGENT_PATCH = "l2-source-address-pve-lab-agent.patch"
ACTIVE_HOOK_BASELINE = "ff85e994c8233b00"  # prefix of the sha256 the patches were written against
ACTIVE_AGENT_BASELINE = "17a13b713428f7e4"
LAB = "pve-lab"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# The active hook and the active agent file are local-only: a clean clone has neither. Every test
# here therefore works from the in-tree candidates and the patches. The baseline the patches were
# written against is rebuilt by applying the patches backwards to the candidates, and its hash is
# compared with the patch headers. Where the local file exists, it is compared as well.
_BASELINES = {}


def _git_apply(root, names, reverse=False):
    for name in names:
        args = ["git", "apply"] + (["-R"] if reverse else []) + [str(PATCH_DIR / name)]
        subprocess.run(args, cwd=root, check=True, capture_output=True, text=True)


def _rebuild(source, relative, names):
    tmp = tempfile.mkdtemp(prefix="corelab-l1b-")
    os.chmod(tmp, 0o700)
    root = Path(tmp)
    target = root / relative
    target.parent.mkdir(parents=True)
    shutil.copyfile(source, target)
    _git_apply(root, names, reverse=True)
    return target


def baseline_hook():
    """The hook as it was before the three patches (rebuilt once per process)."""
    if "hook" not in _BASELINES:
        _BASELINES["hook"] = _rebuild(CAND_HOOK, ".claude/hooks/pve-guard.py", HOOK_PATCHES[::-1])
    return _BASELINES["hook"]


def baseline_agent():
    if "agent" not in _BASELINES:
        _BASELINES["agent"] = _rebuild(CAND_AGENT, ".claude/agents/pve-lab.md", [AGENT_PATCH])
    return _BASELINES["agent"]


def tearDownModule():
    for target in _BASELINES.values():
        shutil.rmtree(target.parents[2], ignore_errors=True)
    _BASELINES.clear()


def installed_hooks():
    """The hooks to compare the candidate with: the rebuilt baseline always, the active one if present."""
    return [("rebuilt baseline", baseline_hook())] + ([("active", ACTIVE_HOOK)] if ACTIVE_HOOK.is_file() else [])


class CandidateBase(HookRunner):
    HOOK = CAND_HOOK

    def decision(self, command, agent=None, mode="default"):
        code, decision, proc = self.run_hook(bash(command, agent=agent, mode=mode))
        self.assertEqual(code, 0, f"{command!r}: {proc.stderr}")
        return decision


# (form, comment). Run in the main session: the owner-only launcher and the root key.
DENY_MAIN = [
    "lab-agent/bin/host-run run prepare", "./host-run x", "python3 x && host-run list",
    "command host-run list", "\\host-run list", 'h"ost"-run list', 'host-r""un list',
    "'host'-run list", "$'host-\\x72un' list", "h${x}ost-run list", "env FOO=1 host-run list",
    "exec host-run list", 'bash -c "host-run list"', "bash -c 'x; host-run list'",
    'sh <<< "host-run list"', "echo list | xargs host-run", "(host-run list)", "$(host-run list)",
    "cat <(host-run list)", "host-run<in.txt", "{ host-run list; }", "lab-agent/bin/host-r* list",
    "lab-agent/bin/h*-run list", "lab-agent/bin/host-ru? list", "lab-agent/bin/[h]ost-run list",
    "lab-agent/bin/host-{run,x} list", "x=host-run; $x list", "host-run${IFS}list",
    "ssh -i ~/.ssh/corelab-pve-root root@192.0.2.10 id", "cat ~/.ssh/corelab-pve-root",
    "cat ~/.ssh/corelab-pve-root.pub", 'cat ~/.ssh/corelab-pve-"root"',
    "cat ~/.ssh/$'corelab-pve-\\x72oot'", "cat ~/.ssh/corelab-pve-r*", "cat ~/.ssh/*-root",
    "cat ~/.ssh/corelab-pve-ro{ot,x}", 'ssh -i "$PVE_ROOT_KEY" root@192.0.2.10 id',
    "ssh-add ~/.ssh/corelab-snip",
    # round 2 (REVIEW-G1): a brace list is inspected completely or the command is denied
    "cat ~/.ssh/corelab-pve-{" + ",".join(["x"] * 64) + ",root}",
    "cat ~/.ssh/corelab-pve-{" + ",".join(["x"] * 5000) + ",root}",
    "cat " + "{a,b}" * 13 + " ~/.ssh/corelab-pve-{x,root}",
    "echo " + "x" * 9000 + "{a,b}",  # a long word that holds a brace list is not inspected: denied
]
# Forms that no text match can reasonably deny. The candidate passes them, and the tests say so,
# so that nobody reads the guard as covering them.
PASS_NOT_CATCHABLE_MAIN = [
    "x=host; y=-run; $x$y list", "$(printf 'host-%s' run) list", "lab-agent/bin/*-run list",
    "cat ~/.ssh/*root", "k=corelab-pve; cat ~/.ssh/${k}-root", "python3 -m lab_agent.hostrun run x",
]
# Controls for the main session: the same tools used for something unrelated.
PASS_MAIN = [
    "ls -la", "ssh -oX host id", "ssh-add -l", "git log --oneline", "ls /srv/*root",
    "echo ghost-running", "echo my-host-run-notes", "python3 -m unittest discover -s tests -t .",
    "cat ~/.ssh/config", "cat ~/.ssh/{config,known_hosts}", "echo " + "{a,b}" * 5,
    "curl -d '{" + ",".join(f'"k{i}":{i}' for i in range(70)) + "}' https://example.test/",
    "cat <<'EOF' > notes.txt\nssh other id\nEOF",  # data, in the main session
]

# Inside pve-lab.
DENY_LAB = [
    "ssh-add -l", "/usr/bin/ssh-add -l", '"ssh-add" -l', "command ssh-add -l", "bash -c 'ssh-add -l'",
    "ssh root@192.0.2.10 id", "ssh pve-root id", "scp x pve-snip:/tmp/", "true; ssh other id",
    "true && ssh other id", "true | ssh other id", "/usr/bin/ssh root@192.0.2.10 id",
    "/usr/bin/scp x pve-snip:/tmp/", "sftp pve-snip", "ssh -oBindAddress=192.0.2.1 pve-snip list",
    "ssh -F/x pve-snip list", "ssh -J jump pve-snip list", "ssh -i k pve-snip list",
    "ssh -b192.0.2.1 pve-snip list", "ssh -l root pve-snip list", "ssh -A pve-snip list",
    "ssh pve-snip -o ProxyCommand=x list", "ssh pve-snip -oX list", "ssh -T -T pve-snip list",
    "command ssh other id", "\\ssh other id", "env X=1 ssh other id", "exec ssh other id",
    'bash -c "ssh other id"', "bash -c 'ssh other id'", 'sh <<< "ssh other id"', "(ssh other id)",
    "echo $(ssh other id)", 'ss""h other id', "ss${x}h other id", "ssh${IFS}other${IFS}id",
    "$'\\x73sh' other id", "s=ssh; $s other id", "ssh $x pve-snip list", "ssh pve-snip $x list",
    "ssh pve-snip rm demo-*", "ssh pve-snip rm demo-{1,2}", "ssh pve-snip put $(cat s) < d.ign",
    "ssh-keygen -y -f k", "rsync -e ssh x pve-snip:/tmp/", "GIT_SSH_COMMAND='ssh -o X' git fetch",
    "nc 192.0.2.10 22", "exec 3<>/dev/tcp/192.0.2.10/22", 'eval "$cmd"', "echo c3No | base64 -d | sh",
    "printf 'ssh other' > x.sh; sh x.sh", "ssh", "ssh pve-snip",  # no command is not a documented form
    # round 2 (REVIEW-G1): a redirect target may name a variable, never run anything
    'ssh pve-snip put demo < "$(ssh other id)"', "ssh pve-snip put demo < <(ssh other id)",
    "ssh pve-snip put demo <<<$(ssh other id)", "ssh pve-snip put demo < `ssh other id`",
    "ssh pve-snip put demo <(ssh other id)", "ssh pve-snip put demo 2>$(ssh other id)",
    "ssh pve-snip list\nssh other id", "bash <<EOF\nssh other id\nEOF",
    "./ssh other id", "../sftp pve-snip", "./ssh-add -l", "nohup ssh other id", "time ssh other id",
    "printf id | xargs ssh other", "ssh -oProxyCommand=evil pve-snip list",
    "ssh pve-snip -oLocalCommand=evil list",
    # A quoted here-document whose text only mentions ssh is data, but the guard reads the text
    # and cannot tell: this false positive is kept, because it fails closed (documented).
    "cat <<'EOF' > notes.txt\nssh other id\nEOF",
]
PASS_NOT_CATCHABLE_LAB = [
    "$(printf 'ss%s' h) other id", "python3 -c \"import subprocess as s; s.run(['ss'+'h','other'])\"",
    "curl https://192.0.2.10:8006/", 'bash -c "$(cat s)"',
]
# The documented allowed forms. Each is the positive control of a denied form above.
PASS_LAB = [
    "ssh pve-snip put demo < d.ign", "ssh -T pve-snip list", "ssh pve-snip rm demo-1",
    "ssh pve-snip list", "cat d.ign | ssh pve-snip put demo", "/usr/bin/ssh -T pve-snip list",
    "command ssh pve-snip list", "env LC_ALL=C ssh pve-snip list", 'ssh pve-snip put demo < "$f"',
    "ssh pve-snip list 2>&1", "ssh pve-snip list; echo -n done", "ssh pve-snip list\necho -n x",
    "bash -c 'ssh pve-snip list'", "lab-agent/bin/lab-agent discover", "ls -la",
    "ssh pve-snip put demo < $f", "ssh pve-snip put demo < ${f}", "ssh pve-snip put demo 2>err.txt",
    "ssh pve-snip other id",  # "other id" is remote-command text for the forced command, not a destination
]


class CandidateFormTests(CandidateBase, unittest.TestCase):
    def test_owner_only_forms_are_denied_in_the_main_session(self):
        for cmd in DENY_MAIN:
            with self.subTest(cmd=cmd[:80]):
                self.assertEqual(self.decision(cmd), "deny")

    def test_positive_controls_in_the_main_session_pass(self):
        for cmd in PASS_MAIN:
            with self.subTest(cmd=cmd[:80]):
                self.assertIsNone(self.decision(cmd))

    def test_main_session_unrelated_command_is_neither_denied_nor_audited(self):
        self.assertIsNone(self.decision("ls -la"))
        self.assertIsNone(self.decision("git status"))
        self.assertEqual(self.audit_lines(), [])

    def test_forms_no_text_match_can_catch_are_recorded_as_passing(self):
        # Not a goal: the honest state. If one of these starts to be denied, move it to the deny
        # list and say what changed; until then nobody may read the guard as covering it.
        for cmd in PASS_NOT_CATCHABLE_MAIN:
            with self.subTest(cmd=cmd[:80]):
                self.assertIsNone(self.decision(cmd))
        for cmd in PASS_NOT_CATCHABLE_LAB:
            with self.subTest(cmd=cmd[:80]):
                self.assertIsNone(self.decision(cmd, agent=LAB))

    def test_lab_agent_forms_are_denied(self):
        for cmd in DENY_LAB:
            with self.subTest(cmd=cmd[:80]):
                self.assertEqual(self.decision(cmd, agent=LAB), "deny")

    def test_lab_agent_documented_forms_pass(self):
        # Positive control for the denials above: the same hook, the same agent, the same run.
        for cmd in PASS_LAB:
            with self.subTest(cmd=cmd[:80]):
                self.assertIsNone(self.decision(cmd, agent=LAB))

    def test_every_form_the_earlier_hook_denies_is_denied_by_the_candidate(self):
        env = {"PATH": HOOK_PATH, "HOME": self.tmp.name, "PVE_LAB_STATE": str(self.state / "earlier")}
        denied_by_earlier = 0
        for label, hook in installed_hooks():
            for cmd, agent in [(c, None) for c in DENY_MAIN] + [(c, LAB) for c in DENY_LAB]:
                proc = subprocess.run([sys.executable, str(hook)], input=json.dumps(bash(cmd, agent=agent)),
                                      text=True, capture_output=True, env=env, timeout=10)
                if proc.returncode == 0 and proc.stdout.strip():
                    denied_by_earlier += 1
                    with self.subTest(hook=label, cmd=cmd[:80]):
                        self.assertEqual(self.decision(cmd, agent=agent), "deny")
        self.assertGreater(denied_by_earlier, 20)  # the comparison really ran: the earlier hook does deny

    def test_the_forms_the_agent_file_prescribes_pass_the_candidate_guard(self):
        # The instruction and the guard must agree: what the candidate agent file tells the agent
        # to run is not denied.
        text = " ".join(CAND_AGENT.read_text(encoding="utf-8").split())
        for prescribed in ("ssh pve-snip put <slug> < file.ign", "ssh pve-snip rm <slug>", "ssh pve-snip list",
                           "ssh -T pve-snip …"):
            self.assertIn(prescribed, text)
        for cmd in ("ssh pve-snip put demo-1 < file.ign", "ssh pve-snip rm demo-1", "ssh pve-snip list",
                    "ssh -T pve-snip list"):
            self.assertIsNone(self.decision(cmd, agent=LAB), cmd)

    def test_ssh_add_is_still_not_policed_outside_the_lab_context(self):
        self.assertIsNone(self.decision("ssh-add -l"))
        self.assertIsNone(self.decision("/usr/bin/ssh-add -l"))

    def test_lab_agent_modes_still_fail_safe(self):
        for mode in ("bypassPermissions", None, "yolo"):
            self.assertEqual(self.decision("ls", agent=LAB, mode=mode), "deny", mode)
        self.assertIsNone(self.decision("ls", agent=LAB, mode="dontAsk"))

    def test_a_denied_call_is_audited_and_redacted(self):
        self.decision("cat ~/.ssh/corelab-pve-root PVEAPIToken=u@pve!x=SECRETVALUE")
        lines = self.audit_lines()
        self.assertEqual([l["decision"] for l in lines], ["deny"])
        self.assertNotIn("SECRETVALUE", json.dumps(lines))

    def test_the_hook_audits_only_below_the_state_directory_it_is_given(self):
        home = Path(self.tmp.name) / "home"
        home.mkdir()
        env = {"PATH": HOOK_PATH, "HOME": str(home), "XDG_STATE_HOME": str(home / "xdg")}
        subprocess.run([sys.executable, str(CAND_HOOK)], input=json.dumps(mcp_call()), text=True,
                       capture_output=True, env=env, timeout=10, check=True)
        self.assertEqual([p.relative_to(home).as_posix() for p in home.rglob("audit.jsonl")],
                         ["xdg/corelab-lab-agent/audit.jsonl"])


FAIL_CLOSED_INPUTS = {
    "empty": "",
    "not json": "not json",
    "truncated": "{",
    "null": "null",
    "list": "[1,2]",
    "string": '"x"',
    "no tool name": "{}",
    "tool name not a string": '{"tool_name": 5}',
    "empty tool name": '{"tool_name": ""}',
    "tool_input a list": '{"tool_name": "Bash", "tool_input": []}',
    "tool_input a string": '{"tool_name": "Bash", "tool_input": "ls"}',
    "Bash without a command": '{"tool_name": "Bash", "tool_input": {}}',
    "Bash command a list": '{"tool_name": "Bash", "tool_input": {"command": ["ls"]}}',
    "Bash command a number": '{"tool_name": "Bash", "tool_input": {"command": 1}}',
    "agent_type a number": '{"tool_name": "Bash", "tool_input": {"command": "ls"}, "agent_type": 5}',
    "permission_mode a list": '{"tool_name": "Bash", "tool_input": {"command": "ls"}, "permission_mode": ["x"]}',
    "mcp tool, tool_input a list": '{"tool_name": "mcp__pve__list_vms", "tool_input": [], "agent_type": "pve-lab"}',
    "nested too deep": "[" * 200000 + "]" * 200000,
    # an explicit null is a present value of the wrong type, not an absence (REVIEW-G1)
    "agent_type null": '{"tool_name": "Bash", "tool_input": {"command": "ssh other id"}, "agent_type": null}',
    "tool_input null, MCP event": '{"tool_name": "mcp__pve__list_vms", "tool_input": null, "agent_type": "pve-lab"}',
    "tool_input null, Bash": '{"tool_name": "Bash", "tool_input": null}',
    "permission_mode null": '{"tool_name": "mcp__pve__list_vms", "agent_type": "pve-lab", "permission_mode": null}',
    "tool_name null": '{"tool_name": null}',
}


class CandidateFailClosedTests(CandidateBase, unittest.TestCase):
    def test_unreadable_or_malformed_input_exits_two(self):
        for name, raw in FAIL_CLOSED_INPUTS.items():
            with self.subTest(name=name):
                code, decision, proc = self.run_hook(None, raw=raw)
                self.assertEqual(code, 2, proc.stderr[-300:])
                self.assertIsNone(decision)

    def run_bytes(self, data, stdout=subprocess.PIPE):
        env = {"PATH": HOOK_PATH, "HOME": self.tmp.name, "PVE_LAB_STATE": str(self.state)}
        return subprocess.run([sys.executable, str(CAND_HOOK)], input=data, stdout=stdout,
                              stderr=subprocess.PIPE, env=env, timeout=30)

    def test_invalid_utf8_in_an_otherwise_valid_event_exits_two_at_the_decoder(self):
        # The event is complete and valid apart from byte FF in the command: it must be rejected
        # by the strict decoder (stderr names it), not by field validation and not passed on
        # through surrogateescape (that was the finding).
        valid = b'{"tool_name":"Bash","tool_input":{"command":"ls %s"},"permission_mode":"default"}'
        control = self.run_bytes(valid % b"x")
        self.assertEqual((control.returncode, control.stdout), (0, b""), control.stderr)
        for bad in (b"\xff", b"\xfe\xff", b"caf\xc3", b"\xed\xa0\x80"):  # lone byte, BOM-like, truncated, surrogate
            with self.subTest(bad=bad):
                proc = self.run_bytes(valid % bad)
                self.assertEqual(proc.returncode, 2, proc.stderr[-300:])
                self.assertIn(b"UnicodeDecodeError", proc.stderr)
                self.assertEqual(proc.stdout, b"")
        # The same bytes would have named the key to a pass-through hook: it must not matter where.
        proc = self.run_bytes(b'{"tool_name":"Bash","tool_input":{"command":"cat corelab-pve-root \xff"}}')
        self.assertEqual((proc.returncode, proc.stdout), (2, b""))

    def test_a_denied_event_with_stdout_on_a_closed_pipe_exits_two_not_120(self):
        event = json.dumps(bash("cat ~/.ssh/corelab-pve-root")).encode()
        control = self.run_bytes(event)  # stdout open: the decision is delivered
        self.assertEqual(control.returncode, 0)
        self.assertEqual(json.loads(control.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        read_end, write_end = os.pipe()
        os.close(read_end)  # nobody will ever read: a real closed pipe
        try:
            proc = self.run_bytes(event, stdout=write_end)
        finally:
            os.close(write_end)
        self.assertEqual(proc.returncode, 2, proc.stderr[-300:])
        self.assertIn(b"cannot write the decision", proc.stderr)
        self.assertNotIn(b"Exception ignored", proc.stderr)  # no second failure at interpreter shutdown
        self.assertNotIn(b"Traceback", proc.stderr)

    def test_a_closed_stdout_and_a_closed_stderr_still_exit_two(self):
        event = json.dumps(bash("cat ~/.ssh/corelab-pve-root")).encode()
        read_end, write_end = os.pipe()
        os.close(read_end)
        env = {"PATH": HOOK_PATH, "HOME": self.tmp.name, "PVE_LAB_STATE": str(self.state)}
        try:
            proc = subprocess.run([sys.executable, str(CAND_HOOK)], input=event, stdout=write_end,
                                  stderr=write_end, env=env, timeout=30)
        finally:
            os.close(write_end)
        self.assertEqual(proc.returncode, 2)

    def test_input_over_the_size_bound_exits_two_and_a_large_one_below_it_is_inspected(self):
        limit = 4 * 1024 * 1024
        below = json.dumps(bash("a " * (3 * 512 * 1024) + "; cat ~/.ssh/corelab-pve-root")).encode()
        above = json.dumps(bash("a " * (5 * 512 * 1024))).encode()
        self.assertLess(len(below), limit)
        self.assertGreater(len(above), limit)
        proc = self.run_bytes(below)  # control: below the bound the command is read and denied
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        proc = self.run_bytes(above)
        self.assertEqual((proc.returncode, proc.stdout), (2, b""), proc.stderr[-200:])
        self.assertIn(b"inspection limit", proc.stderr)
        self.assertEqual(self.run_bytes(b" " * (64 * 1024 * 1024)).returncode, 2)  # also when it is all blanks

    def test_positive_control_a_well_formed_event_in_the_same_setup_is_not_blocked(self):
        for event in (bash("ls"), mcp_call(), {"tool_name": "mcp__pve__list_vms", "agent_type": "pve-lab",
                                              "permission_mode": "default"}):
            code, decision, proc = self.run_hook(event)
            self.assertEqual((code, decision), (0, None), proc.stderr)

    def test_the_earlier_hook_exits_one_on_a_wrong_field_type_and_the_candidate_exits_two(self):
        # Observed defect G-1, kept as a test so that it is clear what the candidate changes. The
        # hook before the patches is rebuilt from the candidate and the patches; the active hook is
        # run as well when this checkout has it (and may be the candidate, once installed).
        env = {"PATH": HOOK_PATH, "HOME": self.tmp.name, "PVE_LAB_STATE": str(self.state / "a")}
        for label, hook in installed_hooks():
            proc = subprocess.run([sys.executable, str(hook)], input='{"tool_name": 5}', text=True,
                                  capture_output=True, env=env, timeout=10)
            installed = label == "active" and sha256(hook) == sha256(CAND_HOOK)
            self.assertEqual(proc.returncode, 2 if installed else 1, label)
        self.assertEqual(self.run_hook({"tool_name": 5})[0], 2)  # the candidate, same input

    def test_an_internal_error_in_decide_exits_two(self):
        ns = runpy.run_path(str(CAND_HOOK), run_name="candidate")

        def broken(event):
            raise RuntimeError("synthetic")
        ns["main"].__globals__["decide"] = broken  # run_path returns a copy; main reads its own globals
        err = io.StringIO()
        with mock.patch.object(sys, "stderr", err):
            code = ns["main"](stdin=io.StringIO(json.dumps(bash("echo SYNTHETIC-COMMAND"))), stdout=io.StringIO(),
                              env={"PVE_LAB_STATE": str(self.state)})
        self.assertEqual(code, 2)
        self.assertIn("internal error", err.getvalue())
        self.assertNotIn("SYNTHETIC-COMMAND", err.getvalue())  # the command is not echoed

    def test_an_error_while_auditing_exits_two_for_every_error_type(self):
        for exc in (OSError("synthetic"), TypeError("synthetic"), ValueError("synthetic"), KeyError("synthetic")):
            with self.subTest(exc=type(exc).__name__):
                ns = runpy.run_path(str(CAND_HOOK), run_name="candidate")

                def broken(*args, _exc=exc, **kwargs):
                    raise _exc
                ns["main"].__globals__["audit"] = broken
                with mock.patch.object(sys, "stderr", io.StringIO()):
                    code = ns["main"](stdin=io.StringIO(json.dumps(mcp_call())), stdout=io.StringIO(), env={})
                self.assertEqual(code, 2)
        # Control: the same event, with a working audit, is not blocked.
        ns = runpy.run_path(str(CAND_HOOK), run_name="candidate")
        self.assertEqual(ns["main"](stdin=io.StringIO(json.dumps(mcp_call())), stdout=io.StringIO(),
                                    env={"PVE_LAB_STATE": str(self.state)}), 0)

    def test_a_failure_to_write_the_answer_still_exits_two(self):
        class Broken:
            def write(self, _):
                raise OSError("synthetic")

            def flush(self):
                raise OSError("synthetic")
        event = json.dumps(bash("cat ~/.ssh/corelab-pve-root"))
        with mock.patch.object(sys, "stdin", io.StringIO(event)), mock.patch.object(sys, "stdout", Broken()), \
                mock.patch.object(sys, "stderr", io.StringIO()), \
                mock.patch.dict(os.environ, {"PVE_LAB_STATE": str(self.state)}):
            with self.assertRaises(SystemExit) as cm:
                runpy.run_path(str(CAND_HOOK), run_name="__main__")
        self.assertEqual(cm.exception.code, 2)

    def test_the_hook_stays_inside_its_timeout_on_hostile_input(self):
        cases = {"1 MB of words": "a " * 500000, "1 MB of glob words": "x* " * 330000,
                 "100000 brace groups": "{a,b}" * 100000, "2000 brace groups in a word": "x" + "{a,b}" * 2000,
                 "1 MB in one word": "a" * 1000000, "500000 quotes": "'" * 500000}
        for agent in (None, LAB):
            for name, cmd in cases.items():
                with self.subTest(name=name, agent=agent):
                    started = time.monotonic()
                    code, _, proc = self.run_hook(bash(cmd, agent=agent))
                    self.assertEqual(code, 0, proc.stderr[-200:])
                    self.assertLess(time.monotonic() - started, 4.0)  # the registered timeout is 5 s


def parse_frontmatter(text):
    """The small YAML subset the agent files use: `key: scalar`, and `key:` with `  - item` lines."""
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not match:
        raise ValueError("no frontmatter")
    data, key = {}, None
    for line in match.group(1).splitlines():
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item and key:
            data[key].append(item.group(1))
            continue
        pair = re.match(r"^([A-Za-z][A-Za-z0-9_]*):\s*(.*)$", line)
        if not pair:
            raise ValueError(f"line not in the supported subset: {line!r}")
        key, value = pair.group(1), pair.group(2)
        if value and (": " in value or " #" in value or value[0] in "&*!|>'\"%@`{[") and \
                not (value[0] in "'\"" and value[-1] == value[0]):
            raise ValueError(f"not a valid plain YAML scalar: {key}")  # what a strict YAML parser refuses
        data[key] = [] if value == "" else value
    return data


class CandidateAgentTests(unittest.TestCase):
    def test_frontmatter_parses_and_keeps_every_field_of_the_active_file(self):
        active = parse_frontmatter(baseline_agent().read_text(encoding="utf-8"))
        candidate = parse_frontmatter(CAND_AGENT.read_text(encoding="utf-8"))
        self.assertEqual(candidate, active)
        self.assertEqual(sorted(candidate), ["color", "description", "mcpServers", "name", "permissionMode", "tools"])
        self.assertEqual((candidate["name"], candidate["permissionMode"], candidate["mcpServers"]),
                         ("pve-lab", "default", ["pve"]))
        self.assertEqual(candidate["tools"], "mcp__pve__*, Bash, Read, Write, Grep, Glob")
        try:
            import yaml  # optional cross-check; not a dependency, and no skip when it is missing
        except ImportError:
            return
        block = re.match(r"---\n(.*?)\n---\n", CAND_AGENT.read_text(encoding="utf-8"), re.S).group(1)
        self.assertEqual(yaml.safe_load(block)["mcpServers"], ["pve"])

    def test_body_differs_from_the_active_file_only_by_the_snippet_writer_bullet(self):
        active = baseline_agent().read_text(encoding="utf-8").splitlines()
        candidate = CAND_AGENT.read_text(encoding="utf-8").splitlines()
        self.assertGreater(len(candidate), len(active))
        head = next(i for i, l in enumerate(candidate) if l.startswith("- **Snippet writer.**"))
        tail = len(candidate) - len(active)
        self.assertEqual(candidate[:head], active[:head])
        self.assertEqual(candidate[head + 1 + tail + 1:], active[head + 2:])

    def test_source_address_instruction_is_there_and_names_no_lab_value(self):
        text = CAND_AGENT.read_text(encoding="utf-8")
        for phrase in ("alias the owner defines", "ssh -T pve-snip", "never try another address, option or route",
                       "words after", "stop and report"):
            self.assertIn(phrase, " ".join(text.split()), phrase)
        self.assertEqual(redact.scan(text), [])
        self.assertIsNone(re.search(r"/home/[a-z]", text))


class CandidateSettingsLayerTests(unittest.TestCase):
    """Added checks of the guard registration, on synthetic layers only."""

    def test_control_the_plain_registration_still_passes(self):
        report = settings_layers.evaluate([syn_commit_layer(), syn_guard_layer()])
        self.assertTrue(report["ok"], report["problems"])
        self.assertTrue(report["registration_unconditional"])
        self.assertEqual(report["hooks_disabled_in_layers"], [])

    def test_disable_all_hooks_in_any_layer_fails(self):
        for position in (0, 1):
            layers = [syn_guard_layer(), {}]
            layers[position]["disableAllHooks"] = True
            report = settings_layers.evaluate(layers)
            self.assertFalse(report["ok"], position)
            self.assertEqual(report["problems"], ["hooks are disabled (disableAllHooks) in a layer"])
            self.assertEqual(report["hooks_disabled_in_layers"], [position])
        layer = syn_guard_layer()
        layer["disableAllHooks"] = False
        self.assertTrue(settings_layers.evaluate([layer])["ok"])

    def test_a_conditional_asynchronous_or_once_only_registration_fails(self):
        for changes in ({"if": "Bash(ls*)"}, {"async": True}, {"once": True}):
            report = settings_layers.evaluate([syn_guard_layer(**changes)])
            self.assertEqual(report["problems"], ["registration is conditional, asynchronous or once-only"], changes)
            self.assertFalse(report["registration_unconditional"], changes)
            self.assertTrue(report["on_failure_block"] and report["python3_args_form"], changes)
        for changes in ({"async": False}, {"once": False}):  # control: explicit false is not a narrowing
            self.assertTrue(settings_layers.evaluate([syn_guard_layer(**changes)])["ok"], changes)

    def test_new_report_fields_carry_no_value_from_a_layer(self):
        marker = "SyntheticFilterMarker"
        text = json.dumps(settings_layers.evaluate([syn_guard_layer(**{"if": marker})]))
        self.assertNotIn(marker, text)


class CandidateProposalTests(unittest.TestCase):
    """The proposed/ copies and the refreshed patches agree with the active files."""

    @staticmethod
    def baseline(name):
        match = re.search(r"^# Target baseline sha256: ([0-9a-f]{64})", (PATCH_DIR / name).read_text(), re.M)
        return match.group(1) if match else None

    def apply(self, names, root):
        for name in names:
            subprocess.run(["git", "apply", str(PATCH_DIR / name)], cwd=root, check=True,
                           capture_output=True, text=True)

    def scratch(self, source, relative):
        tmp = fixtures.private_tmpdir()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / relative
        target.parent.mkdir(parents=True)
        shutil.copyfile(source, target)
        return Path(tmp.name), target

    def test_git_is_available_for_the_patch_checks(self):
        self.assertIsNotNone(shutil.which("git"))

    def test_the_hooks_compile_in_memory(self):
        for _label, path in [("candidate", CAND_HOOK)] + installed_hooks():
            compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_patch_headers_record_the_baseline_the_patches_reverse_to(self):
        # Works in a clean clone: the baseline is rebuilt from the candidates and the patches. A
        # header hash that does not match means a patch and its candidate have drifted apart.
        self.assertTrue(sha256(baseline_hook()).startswith(ACTIVE_HOOK_BASELINE))
        self.assertTrue(sha256(baseline_agent()).startswith(ACTIVE_AGENT_BASELINE))
        for name in HOOK_PATCHES:
            self.assertEqual(self.baseline(name), sha256(baseline_hook()), name)
        self.assertEqual(self.baseline(AGENT_PATCH), sha256(baseline_agent()))

    def test_a_local_active_file_is_either_the_baseline_or_the_installed_candidate(self):
        # Only where this checkout has the local-only active files (otherwise nothing to compare, and
        # the test above has already covered the baseline). If the owner changed a file, or installed
        # a candidate, this fails on purpose: the patches must be reconciled again.
        self.assertNotEqual(sha256(baseline_hook()), sha256(CAND_HOOK))  # always: the patches change something
        self.assertNotEqual(sha256(baseline_agent()), sha256(CAND_AGENT))
        for active, baseline, candidate in ((ACTIVE_HOOK, baseline_hook(), CAND_HOOK),
                                            (ACTIVE_AGENT, baseline_agent(), CAND_AGENT)):
            if active.is_file():
                self.assertIn(sha256(active), (sha256(baseline), sha256(candidate)), active.name)

    def test_the_three_guard_patches_in_order_turn_the_baseline_hook_into_the_candidate(self):
        root, target = self.scratch(baseline_hook(), ".claude/hooks/pve-guard.py")
        self.apply(HOOK_PATCHES, root)
        self.assertEqual(target.read_bytes(), CAND_HOOK.read_bytes())

    def test_the_first_two_patches_apply_in_either_order_to_the_same_file(self):
        first, a = self.scratch(baseline_hook(), ".claude/hooks/pve-guard.py")
        second, b = self.scratch(baseline_hook(), ".claude/hooks/pve-guard.py")
        self.apply(HOOK_PATCHES[:2], first)
        self.apply((HOOK_PATCHES[1], HOOK_PATCHES[0]), second)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.apply(HOOK_PATCHES[2:], first)
        self.apply(HOOK_PATCHES[2:], second)
        self.assertEqual(a.read_bytes(), CAND_HOOK.read_bytes())

    def test_each_of_the_first_two_applies_to_the_active_file_alone_and_the_third_does_not(self):
        for name in HOOK_PATCHES[:2]:
            root, _ = self.scratch(baseline_hook(), ".claude/hooks/pve-guard.py")
            self.apply([name], root)
        root, _ = self.scratch(baseline_hook(), ".claude/hooks/pve-guard.py")
        failed = subprocess.run(["git", "apply", "--check", str(PATCH_DIR / HOOK_PATCHES[2])], cwd=root,
                                capture_output=True, text=True)
        self.assertNotEqual(failed.returncode, 0)  # S-1g is ordered after G-2 now; the header says so
        self.assertIn("Needs the second patch", (PATCH_DIR / HOOK_PATCHES[2]).read_text())

    def test_the_agent_patch_turns_the_active_agent_file_into_the_candidate(self):
        root, target = self.scratch(baseline_agent(), ".claude/agents/pve-lab.md")
        self.apply([AGENT_PATCH], root)
        self.assertEqual(target.read_bytes(), CAND_AGENT.read_bytes())

    def test_patches_name_no_private_path_and_no_decision_id(self):
        for name in HOOK_PATCHES + (AGENT_PATCH,):
            text = (PATCH_DIR / name).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"/home/[a-z]|\.handoffs|D-\d\d", text), name)
            self.assertEqual([f for f in redact.scan(text) if "mail" not in f], [], name)

    def test_proposed_directory_is_publication_safe_and_says_it_installs_nothing(self):
        # Other workers may add their own candidates beside these (for example under settings/);
        # this test owns only these three files.
        files = [PROPOSED / "README.md", CAND_AGENT, CAND_HOOK]
        for path in files:
            self.assertTrue(path.is_file(), path.name)
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"/home/[a-z]|\.handoffs", text), path.name)
            self.assertEqual([f for f in redact.scan(text) if "mail" not in f], [], path.name)
        readme = " ".join((PROPOSED / "README.md").read_text(encoding="utf-8").split())
        for phrase in ("not installed", "not a security boundary", "owner"):
            self.assertIn(phrase, readme)


if __name__ == "__main__":
    unittest.main()
