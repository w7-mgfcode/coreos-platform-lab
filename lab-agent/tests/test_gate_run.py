"""The offline gate itself (tests/run.sh, review finding 2).

Each test copies run.sh into a synthetic tree in a private temporary directory and runs it
with an isolated PATH: a directory of symlinks to the few real tools the gate needs, plus,
where a test says so, a stub `docker` that only logs its arguments. The real Docker daemon,
its images and its configuration are never touched, and the synthetic tree's unit tests
are a tiny module, so the gate does not recurse into this suite.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from tests import fixtures

GATE = Path(__file__).resolve().parent / "run.sh"
TOOLS = ("bash", "perl", "grep", "sed", "cat", "rm", "mktemp", "chmod", "cp", "basename", "dirname",
         "cut", "tail", "mkdir")

# The host actions the gate requires (its explicit inventory, REQUIRED_FILES in run.sh).
ACTIONS = ("backup-config", "bootstrap", "discover-host", "fcos-template", "preflight", "prepare", "sentinel")

DUMMY_TESTS = {
    "pass": "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n",
    "skip": ("import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n\n"
             "    def test_needs_tool(self):\n        self.skipTest('tool not installed')\n"),
    "fail": "import unittest\n\nclass T(unittest.TestCase):\n    def test_bad(self):\n        self.fail('boom')\n",
}

STUB_DOCKER = """#!@BASH@
printf '%s\\n' "$*" >> "$STUB_DOCKER_LOG"
case "$1 ${2:-}" in
  "image inspect"*) exit "${STUB_INSPECT_RC:-0}" ;;
esac
if [ "$1" = run ]; then
  case " $* " in
    *shellcheck*)
      # one checkstyle <file> record per input, as ShellCheck prints them; STUB_SC_MODE degrades it
      files=()
      for a in "$@"; do case "$a" in /mnt/*.sh) files+=("$a") ;; esac; done
      case "${STUB_SC_MODE:-}" in
        drop)  unset 'files[${#files[@]}-1]' ;;
        none)  files=() ;;
        extra) files+=(/mnt/phantom.sh) ;;
        swap)  files[0]=/mnt/other.sh ;;
      esac
      echo "<?xml version='1.0' encoding='UTF-8'?>"
      echo "<checkstyle version='4.3'>"
      # the real formatter writes - and _ as numeric character references
      for f in "${files[@]}"; do enc=$(printf '%s' "$f" | sed -e 's/-/\\&#45;/g' -e 's/_/\\&#95;/g'); echo "<file name='$enc' >"; echo "</file>"; done
      echo "</checkstyle>"
      exit "${STUB_RUN_RC:-0}" ;;
    *butane*)
      # an Ignition document made from stdin; STUB_BUTANE_MODE degrades it
      input=$(cat)
      case "${STUB_BUTANE_MODE:-}" in
        empty) ;;
        garbage) echo "not json" ;;
        nokey) echo '{"ignition": {"version": "3.5.0"}}' ;;
        *) key=$(printf '%s' "$input" | grep -o 'ssh-ed25519 [A-Za-z0-9]*')
           printf '{"ignition": {"version": "3.5.0"}, "passwd": {"users": [{"sshAuthorizedKeys": ["%s"]}]}}\\n' "$key" ;;
      esac
      exit "${STUB_RUN_RC:-0}" ;;
  esac
  cat >/dev/null; exit "${STUB_RUN_RC:-0}"
fi
exit 97
""".replace("@BASH@", "{bash}")


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        base = Path(self.tmp.name)
        self.repo = base / "repo"
        self.bin = base / "bin"
        self.stub_bin = base / "stub-bin"
        self.tmpdir = base / "gate-tmp"
        self.log = base / "docker.log"
        for d in (self.bin, self.stub_bin, self.tmpdir):
            d.mkdir()
        for tool in TOOLS:
            real = shutil.which(tool)
            if real is None:
                self.fail(f"required tool not found for the gate test: {tool}")
            (self.bin / tool).symlink_to(real)
        (self.bin / "python3").symlink_to(sys.executable)
        bash = shutil.which("bash")
        stub = self.stub_bin / "docker"
        stub.write_text(STUB_DOCKER.replace("{bash}", bash))
        stub.chmod(0o755)
        self.log.write_text("")
        self.make_tree("pass")

    def tearDown(self):
        self.tmp.cleanup()

    def make_tree(self, unit):
        la = self.repo / "lab-agent"
        for d in ("tests", "host/actions", "host/snippet-writer", "demo", "../.claude/hooks"):
            (la / d).mkdir(parents=True, exist_ok=True)
        shutil.copy(GATE, la / "tests" / "run.sh")
        (la / "tests" / "__init__.py").write_text("")
        (la / "tests" / "test_dummy.py").write_text(DUMMY_TESTS[unit])
        (la / "host" / "lib.sh").write_text("cl_log() { printf '%s\\n' \"$*\"; }\n")
        # hyphenated names: ShellCheck's checkstyle output escapes them as character references
        for name in ACTIONS:
            (la / "host" / "actions" / f"{name}.sh").write_text(f"cl_log {name}\n")
        (la / "host" / "snippet-writer" / "corelab-snippet-put").write_text("use strict;\nprint 1;\n")
        (la / "demo" / "render.sh").write_text("echo render\n")
        (la / "demo" / "fcos-demo.bu").write_text(
            "variant: fcos\nversion: 1.5.0\npasswd:\n  users:\n    - name: core\n"
            "      ssh_authorized_keys:\n        - \"@DEMO_SSH_PUBKEY@\"\n")
        (la / "proposed" / "hooks").mkdir(parents=True, exist_ok=True)
        (la / "mcp.example.json").write_text(json.dumps({"mcpServers": {}}))
        (la / "proposed" / "hooks" / "pve-guard.py").write_text("x = 1\n")
        (self.repo / ".claude" / "settings.json").write_text(json.dumps({"hooks": {}}))
        # local-only files: present in this tree, removed by the clean-checkout tests
        (self.repo / ".mcp.json").write_text(json.dumps({"mcpServers": {}}))
        (self.repo / ".claude" / "hooks" / "pve-guard.py").write_text("x = 1\n")

    def run_gate(self, docker=False, **stub_env):
        path = str(self.bin) + (os.pathsep + str(self.stub_bin) if docker else "")
        env = {"PATH": path, "HOME": self.tmp.name, "TMPDIR": str(self.tmpdir), "LC_ALL": "C",
               "STUB_DOCKER_LOG": str(self.log), **stub_env}
        proc = subprocess.run([str(self.bin / "bash"), str(self.repo / "lab-agent" / "tests" / "run.sh")],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env, timeout=120)
        lines = proc.stdout.rstrip("\n").splitlines()
        return proc.returncode, lines, proc

    def docker_calls(self):
        return self.log.read_text().splitlines()

    # -- the defect: skipped checks must never yield PASS / 0 ---------------------------
    def test_no_docker_on_path_is_incomplete_not_pass(self):
        code, lines, proc = self.run_gate(docker=False)
        self.assertEqual(code, 2, proc.stdout + proc.stderr)
        self.assertTrue(lines[-1].startswith("RESULT: INCOMPLETE"), lines[-1])
        self.assertNotIn("RESULT: PASS", proc.stdout)
        self.assertIn("SKIP   shellcheck: docker not found on PATH", lines)
        self.assertIn("SKIP   butane: docker not found on PATH", lines)
        self.assertIn("skipped: shellcheck: docker not found on PATH", lines)
        self.assertIn("skipped: butane: docker not found on PATH", lines)
        self.assertEqual(self.docker_calls(), [])

    def test_absent_image_is_skipped_and_never_pulled(self):
        code, lines, proc = self.run_gate(docker=True, STUB_INSPECT_RC="1")
        self.assertEqual(code, 2, proc.stdout + proc.stderr)
        self.assertTrue(lines[-1].startswith("RESULT: INCOMPLETE"), lines[-1])
        self.assertTrue(any(l.startswith("SKIP   shellcheck: image docker.io/koalaman/shellcheck:v0.10.0 "
                                         "not present locally") for l in lines), lines)
        self.assertTrue(any(l.startswith("SKIP   butane: image quay.io/coreos/butane:v0.23.0 "
                                         "not present locally") for l in lines), lines)
        calls = self.docker_calls()
        self.assertEqual(len(calls), 2, calls)
        self.assertTrue(all(c.startswith("image inspect ") for c in calls), calls)

    def test_control_everything_available_passes(self):
        # Proves the two tests above fail for the right reason: with docker and both images
        # "present", the same tree yields PASS / 0 and both containers are started offline.
        code, lines, proc = self.run_gate(docker=True)
        self.assertEqual(code, 0, proc.stdout + proc.stderr)
        self.assertEqual(lines[-1], "RESULT: PASS (all 7 checks ran)")
        self.assertIn("PASS   python unit tests (Ran 1 test; OK)", lines)
        self.assertIn("PASS   shellcheck (actions+lib, render.sh, run.sh; 9 of 9 files processed)", lines)
        self.assertIn("PASS   butane --strict demo/fcos-demo.bu (Ignition output carries the input's key)", lines)
        runs = [c for c in self.docker_calls() if c.startswith("run ")]
        self.assertEqual(len(runs), 2, self.docker_calls())
        self.assertTrue(all("--network none" in c for c in runs), runs)

    def test_skipped_unit_test_is_visible_and_not_pass(self):
        self.make_tree("skip")
        code, lines, proc = self.run_gate(docker=True)
        self.assertEqual(code, 2, proc.stdout + proc.stderr)
        self.assertIn("SKIP   python unit tests (Ran 2 tests; OK (skipped=1)): 1 unit test(s) skipped", lines)
        self.assertTrue(any(l.startswith("  skipped test: test_needs_tool") for l in lines), lines)
        self.assertTrue(lines[-1].startswith("RESULT: INCOMPLETE"), lines[-1])

    def test_failure_outranks_skip(self):
        self.make_tree("fail")
        code, lines, proc = self.run_gate(docker=False)
        self.assertEqual(code, 1, proc.stdout + proc.stderr)
        self.assertEqual(lines[-1], "RESULT: FAIL (1 failed, 2 skipped)")
        self.assertTrue(any(l.startswith("failed:  python unit tests") for l in lines), lines)

    def test_container_failure_is_fail(self):
        code, lines, proc = self.run_gate(docker=True, STUB_RUN_RC="1")
        self.assertEqual(code, 1, proc.stdout + proc.stderr)
        # the shellcheck line now names the exit status (the gate output changed on purpose)
        self.assertIn("FAIL   shellcheck (exit 1)", lines)
        self.assertIn("FAIL   butane --strict demo/fcos-demo.bu", lines)

    # -- the tool must have processed every input, not merely exited 0 --------------------
    def test_shellcheck_exit_zero_with_a_missing_file_record_is_fail(self):
        for mode, count in (("drop", 8), ("none", 0), ("swap", 9), ("extra", 10)):
            with self.subTest(mode=mode):
                code, lines, proc = self.run_gate(docker=True, STUB_SC_MODE=mode)
                self.assertEqual(code, 1, proc.stdout + proc.stderr)
                self.assertIn(f"FAIL   shellcheck processed {count} of 9 input files (exit 0 is not proof)", lines)
                self.assertEqual(lines[-1], "RESULT: FAIL (1 failed, 0 skipped)")
                self.assertNotIn("RESULT: PASS", proc.stdout)

    def test_shellcheck_names_the_inputs_without_a_record(self):
        _, lines, _ = self.run_gate(docker=True, STUB_SC_MODE="drop")
        self.assertIn("  no shellcheck record for: /mnt/sentinel.sh", lines)
        _, lines, _ = self.run_gate(docker=True, STUB_SC_MODE="swap")
        self.assertIn("  no shellcheck record for: /mnt/backup-config.sh", lines)

    def test_shellcheck_records_control_every_input_processed_passes(self):
        # positive control for the four tests above: same tree, complete records
        code, lines, proc = self.run_gate(docker=True, STUB_SC_MODE="")
        self.assertEqual(code, 0, proc.stdout + proc.stderr)
        self.assertTrue(any(l.startswith("PASS   shellcheck (") and "9 of 9 files processed" in l for l in lines))

    def test_butane_exit_zero_without_ignition_from_the_input_is_fail(self):
        for mode in ("empty", "garbage", "nokey"):
            with self.subTest(mode=mode):
                code, lines, proc = self.run_gate(docker=True, STUB_BUTANE_MODE=mode)
                self.assertEqual(code, 1, proc.stdout + proc.stderr)
                self.assertIn("FAIL   butane --strict demo/fcos-demo.bu produced no valid Ignition for this input "
                              "(exit 0 is not proof)", lines)
                self.assertTrue(any(l.startswith("PASS   shellcheck (") for l in lines), lines)  # only butane fails
                self.assertEqual(lines[-1], "RESULT: FAIL (1 failed, 0 skipped)")

    def test_butane_fails_when_the_input_no_longer_carries_the_placeholder(self):
        # the output must come from this input: without the placeholder the key cannot appear
        bu = self.repo / "lab-agent" / "demo" / "fcos-demo.bu"
        bu.write_text("variant: fcos\nversion: 1.5.0\n")
        code, lines, proc = self.run_gate(docker=True)
        self.assertEqual(code, 1, proc.stdout + proc.stderr)
        self.assertTrue(any(l.startswith("FAIL   butane --strict demo/fcos-demo.bu produced no valid Ignition")
                            for l in lines), lines)

    def test_missing_records_do_not_outrank_a_skip_contract(self):
        # without docker nothing is parsed: still INCOMPLETE, never FAIL or PASS
        code, lines, proc = self.run_gate(docker=False, STUB_SC_MODE="drop", STUB_BUTANE_MODE="empty")
        self.assertEqual(code, 2, proc.stdout + proc.stderr)
        self.assertTrue(lines[-1].startswith("RESULT: INCOMPLETE"), lines[-1])

    # -- local-only files: the gate must pass in a clean checkout ----------------------------
    def remove_local_only(self):
        (self.repo / ".mcp.json").unlink()
        (self.repo / ".claude" / "hooks" / "pve-guard.py").unlink()

    def test_local_files_present_are_checked_too(self):
        code, lines, proc = self.run_gate(docker=True)
        self.assertEqual(code, 0, proc.stdout + proc.stderr)
        self.assertIn("PASS   JSON syntax (.claude/settings.json, lab-agent/mcp.example.json, .mcp.json)", lines)
        self.assertIn("PASS   pve-guard.py compiles (lab-agent/proposed/hooks/pve-guard.py, "
                      ".claude/hooks/pve-guard.py)", lines)
        self.assertFalse(any(l.startswith("info ") for l in lines), lines)

    def test_clean_checkout_without_local_only_files_passes_with_info_lines(self):
        self.remove_local_only()
        code, lines, proc = self.run_gate(docker=True)
        self.assertEqual(code, 0, proc.stdout + proc.stderr)
        self.assertEqual(lines[-1], "RESULT: PASS (all 7 checks ran)")
        self.assertIn("info   .mcp.json not present (local-only file, not checked)", lines)
        self.assertIn("info   .claude/hooks/pve-guard.py not present (local-only file, not checked)", lines)
        self.assertIn("PASS   JSON syntax (.claude/settings.json, lab-agent/mcp.example.json)", lines)
        self.assertIn("PASS   pve-guard.py compiles (lab-agent/proposed/hooks/pve-guard.py)", lines)
        self.assertFalse(any(l.startswith("SKIP") for l in lines), lines)

    def test_clean_checkout_without_docker_is_incomplete_only_for_the_skipped_checks(self):
        self.remove_local_only()
        code, lines, proc = self.run_gate(docker=False)
        self.assertEqual(code, 2, proc.stdout + proc.stderr)
        self.assertEqual(lines[-1], "RESULT: INCOMPLETE (2 skipped; not a pass)")

    def test_missing_in_tree_files_are_fail_even_in_a_clean_checkout(self):
        self.remove_local_only()
        for rel in ("lab-agent/mcp.example.json", "lab-agent/proposed/hooks/pve-guard.py", ".claude/settings.json"):
            with self.subTest(missing=rel):
                path = self.repo / rel
                saved = path.read_text()
                path.unlink()
                code, lines, proc = self.run_gate(docker=True)
                path.write_text(saved)
                self.assertEqual(code, 1, proc.stdout + proc.stderr)
                self.assertIn(f"  missing in-tree file: {rel}", lines)
                self.assertTrue(lines[-1].startswith("RESULT: FAIL (1 failed"), lines[-1])

    def test_invalid_in_tree_or_local_files_are_fail(self):
        # control: the same tree passes (test_local_files_present_are_checked_too)
        for rel, text, expect in (("lab-agent/mcp.example.json", "{not json", "  invalid JSON: lab-agent/mcp.example.json"),
                                  (".mcp.json", "{not json", "  invalid JSON: .mcp.json"),
                                  ("lab-agent/proposed/hooks/pve-guard.py", "def (:\n",
                                   "  does not compile: lab-agent/proposed/hooks/pve-guard.py"),
                                  (".claude/hooks/pve-guard.py", "def (:\n",
                                   "  does not compile: .claude/hooks/pve-guard.py")):
            with self.subTest(broken=rel):
                path = self.repo / rel
                saved = path.read_text()
                path.write_text(text)
                code, lines, proc = self.run_gate(docker=True)
                path.write_text(saved)
                self.assertEqual(code, 1, proc.stdout + proc.stderr)
                self.assertTrue(any(l.startswith(expect) for l in lines), lines)

    # -- explicit inventory: deleting an input must not shrink what is checked ----------------
    def test_deleting_a_required_file_fails_even_though_the_glob_shrinks_with_it(self):
        required = [f"host/actions/{n}.sh" for n in ACTIONS] + ["host/lib.sh", "demo/render.sh", "demo/fcos-demo.bu",
                                                               "host/snippet-writer/corelab-snippet-put"]
        for rel in required:
            for docker in (True, False):
                with self.subTest(deleted=rel, docker=docker):
                    path = self.repo / "lab-agent" / rel
                    saved = path.read_text()
                    path.unlink()
                    code, lines, proc = self.run_gate(docker=docker)
                    path.write_text(saved)
                    self.assertEqual(code, 1, proc.stdout + proc.stderr)  # FAIL outranks a skip
                    self.assertIn(f"  missing required file: {rel}", lines)
                    self.assertNotIn("RESULT: PASS", proc.stdout)
        # positive control: the same tree, nothing deleted
        code, lines, proc = self.run_gate(docker=True)
        self.assertEqual(code, 0, proc.stdout + proc.stderr)
        self.assertIn("PASS   bash -n on all shell files (12 required files present, none unlisted)", lines)

    def test_a_deleted_action_is_named_by_both_the_syntax_and_the_shellcheck_check(self):
        (self.repo / "lab-agent" / "host" / "actions" / "sentinel.sh").unlink()
        code, lines, proc = self.run_gate(docker=True)
        self.assertEqual(code, 1, proc.stdout + proc.stderr)
        self.assertIn("FAIL   bash -n / required inventory", lines)
        self.assertIn("FAIL   shellcheck: required inventory differs from the tree (1 missing, 0 unlisted)", lines)

    def test_an_unlisted_entry_in_the_action_directory_fails_the_gate_itself(self):
        # The gate script finds it; no unit test needs to be collected for this. The dummy unit
        # tests of the synthetic tree never look at the inventory.
        actions = self.repo / "lab-agent" / "host" / "actions"
        for name in ("extra.sh", "notes.txt", ".hidden.sh"):
            for docker in (True, False):
                with self.subTest(entry=name, docker=docker):
                    (actions / name).write_text("cl_log extra\n")
                    code, lines, proc = self.run_gate(docker=docker)
                    (actions / name).unlink()
                    self.assertEqual(code, 1, proc.stdout + proc.stderr)
                    self.assertIn(f"  unlisted file (not in REQUIRED_FILES): host/actions/{name}", lines)
                    self.assertIn("FAIL   bash -n / required inventory", lines)
                    self.assertNotIn("RESULT: PASS", proc.stdout)
        sub = actions / "subdir"
        sub.mkdir()  # a directory is an unreviewed entry too
        code, lines, proc = self.run_gate(docker=True)
        sub.rmdir()
        self.assertEqual(code, 1, proc.stdout + proc.stderr)
        self.assertIn("  unlisted file (not in REQUIRED_FILES): host/actions/subdir", lines)
        code, lines, proc = self.run_gate(docker=True)  # control: nothing extra
        self.assertEqual(code, 0, proc.stdout + proc.stderr)

    def test_the_gate_inventory_equals_the_real_host_actions(self):
        text = GATE.read_text()
        listed = set(re.findall(r"^  host/actions/([a-z0-9-]+)\.sh$", text, re.M))
        real = {p.stem for p in (GATE.parent.parent / "host" / "actions").glob("*.sh")}
        self.assertEqual(listed, real, "update REQUIRED_FILES in tests/run.sh when an action is added or removed")
        self.assertEqual(listed, set(ACTIONS), "keep the ACTIONS tuple of this test in step")

    # -- local-only paths: absent is not the same as present but invalid ----------------------
    def test_a_dangling_symlink_at_a_local_only_path_is_fail_not_absent(self):
        for rel, expect in ((".mcp.json", "  present but not a regular file: .mcp.json"),
                            (".claude/hooks/pve-guard.py",
                             "  present but not a regular file: .claude/hooks/pve-guard.py")):
            with self.subTest(path=rel):
                self.remove_local_only()
                (self.repo / rel).symlink_to(self.tmp.name + "/does-not-exist")
                code, lines, proc = self.run_gate(docker=True)
                self.assertEqual(code, 1, proc.stdout + proc.stderr)
                self.assertIn(expect, lines)
                self.assertFalse(any(l.startswith("info") and rel in l for l in lines), lines)
                (self.repo / rel).unlink()
                self.make_tree("pass")  # restore the local-only files for the next case

    def test_a_directory_or_fifo_at_a_local_only_path_is_fail(self):
        self.remove_local_only()
        (self.repo / ".mcp.json").mkdir()
        os.mkfifo(self.repo / ".claude" / "hooks" / "pve-guard.py")
        code, lines, proc = self.run_gate(docker=True)
        self.assertEqual(code, 1, proc.stdout + proc.stderr)
        self.assertIn("  present but not a regular file: .mcp.json", lines)
        self.assertIn("  present but not a regular file: .claude/hooks/pve-guard.py", lines)

    def test_a_symlink_to_a_regular_local_file_is_checked_and_a_truly_absent_path_is_info(self):
        self.remove_local_only()
        real = Path(self.tmp.name) / "real-mcp.json"
        real.write_text(json.dumps({"mcpServers": {}}))
        (self.repo / ".mcp.json").symlink_to(real)
        code, lines, proc = self.run_gate(docker=True)
        self.assertEqual(code, 0, proc.stdout + proc.stderr)
        self.assertIn("PASS   JSON syntax (.claude/settings.json, lab-agent/mcp.example.json, .mcp.json)", lines)
        self.assertIn("info   .claude/hooks/pve-guard.py not present (local-only file, not checked)", lines)

    # -- side effects ------------------------------------------------------------------
    def test_no_predictable_temp_file_and_no_bytecode(self):
        self.run_gate(docker=True)
        self.assertEqual(list(self.tmpdir.iterdir()), [])  # private scratch removed on exit
        self.assertEqual([p for p in self.repo.rglob("__pycache__")], [])

    def test_gate_source_never_pulls_or_uses_fixed_tmp_names(self):
        text = GATE.read_text()
        self.assertIsNone(re.search(r"docker\s+(pull|build|login)", text))
        self.assertIsNone(re.search(r"/tmp/corelab-[a-z]+\.\$\$", text))
        self.assertIn("--network none", text)
        self.assertIn("-f checkstyle", text)  # per-file records, not just an exit status


if __name__ == "__main__":
    unittest.main()
