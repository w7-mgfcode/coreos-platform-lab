"""Destructive execution is disabled in this version, and it fails closed at every entry point.

What is checked here, offline and against the stub tools only:

  * the shipped host library: each destructive function exits 7 before any tool is called, whatever
    the environment says;
  * the destructive commands are not in the shipped text at all: a shell in which ``exit`` has been
    replaced (an exported function, a start-up file) runs past every refusal and still calls no stop,
    backup, destroy or free (the bypass an independent review found in the gate alone);
  * a rendered manifest script: its first command is the gate, and run as rendered it exits 7 without
    one tool call, for guests, stop-mode backups and volumes alike;
  * the owner-path ``run``: a valid request is validated and listed and then refused, with nothing
    rendered, prompted for or started (``test_closeout_apply`` holds the main case);
  * nothing else in the tree reaches a destructive command.

Each refusal has a control: the same script in the test-only copy (``fixtures.for_stub_run``) does
reach the tools, so the gate is what stopped the shipped text, not a broken fixture. That copy shows
that the test is meaningful; it shows nothing about whether real execution would be safe.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from lab_agent import cli, hostrun, manifest
from tests import fixtures
from tests.test_closeout_apply import ApplyHarness
from tests.test_closeout_round3 import MUTATING, STUBS, override, stub_state
from tests.test_inventory_manifest import EVIDENCE, classes

AGENT_DIR = Path(__file__).resolve().parent.parent
LIB = AGENT_DIR / "host" / "lib.sh"
GATED = ("cl_backup_guest", "cl_stop_guest", "cl_destroy_guest", "cl_free_volume")
GATE_LINE = ('cl_destructive_gate() { cl_die 7 "destructive execution is disabled in this version of the tooling '
             '($1); nothing was read or changed"; }')
DIGEST_105 = fixtures.CONFIGS[105]["digest"]
DIGEST_106 = fixtures.CONFIGS[106]["digest"]
ISO = "corelab:iso/corelab-dummy.iso"
ISO_SIZE = next(v["size"] for v in fixtures.CONTENT["corelab"] if v["volid"] == ISO)
COMMANDS = {
    "cl_backup_guest": f"cl_backup_guest qemu 105 {fixtures.NODE} old-k8s-node stopped {DIGEST_105} 0 local",
    "cl_stop_guest": f"cl_stop_guest qemu 106 {fixtures.NODE} old-web running {DIGEST_106} 0",
    "cl_destroy_guest": f"cl_destroy_guest qemu 105 {fixtures.NODE} old-k8s-node stopped {DIGEST_105} 0",
    "cl_free_volume": f"cl_free_volume corelab {ISO} {ISO_SIZE}",
}
# The synthetic operation each command performs in the test-only copy (the stub tools record it).
OPERATIONS = {
    "cl_backup_guest": ["vzdump", "105", "--storage", "local", "--mode", "stop", "--compress", "zstd"],
    "cl_stop_guest": ["qm", "stop", "106"],
    "cl_destroy_guest": ["qm", "destroy", "105", "--purge", "1"],
    "cl_free_volume": ["pvesm", "free", ISO],
}


class StubRun(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def bash(self, script, state=None, extra_env=None):
        """Run ``script`` exactly as given under the stub tools; return (process, every tool call)."""
        (self.dir / "state.json").write_text(json.dumps(state or stub_state()))
        (self.dir / "calls.log").write_text("")
        env = {"PATH": f"{STUBS}:/usr/bin:/bin", "STUB_STATE": str(self.dir / "state.json"),
               "STUB_LOG": str(self.dir / "calls.log")}
        env.update(extra_env or {})
        proc = subprocess.run(["bash", "-s"], input=script, text=True, capture_output=True, env=env)
        calls = [json.loads(line) for line in (self.dir / "calls.log").read_text().splitlines()]
        return proc, calls

    def library_plus(self, command):
        exports = {"CL_SENTINEL_VMID": str(fixtures.SENTINEL), "CL_POOL": fixtures.POOL, "CL_NODE": fixtures.NODE}
        lines = ["set -euo pipefail"] + [f"export {k}={v}" for k, v in exports.items()]
        return "\n".join(lines) + "\n" + LIB.read_text(encoding="utf-8") + "\n" + command + "\n"

    def assert_disabled(self, proc, calls, name):
        self.assertEqual(proc.returncode, 7, proc.stderr)
        self.assertEqual(calls, [], "no tool may be called, not even to read")
        self.assertIn(f"destructive execution is disabled in this version of the tooling ({name})", proc.stderr)
        self.assertIn("nothing was read or changed", proc.stderr)


class ShippedLibraryTests(StubRun):
    def test_each_destructive_function_exits_7_before_any_tool_call(self):
        for name, command in COMMANDS.items():
            with self.subTest(function=name):
                proc, calls = self.bash(self.library_plus(command))
                self.assert_disabled(proc, calls, name)

    def test_the_refusal_comes_before_the_argument_checks(self):
        for name in GATED:  # no arguments, too many, unsafe ones: still the gate, still nothing called
            for args in ("", "a b c d e f g h i j", "'$(id)' ';' x"):
                with self.subTest(function=name, args=args):
                    proc, calls = self.bash(self.library_plus(f"{name} {args}"))
                    self.assert_disabled(proc, calls, name)

    def test_control_the_same_commands_reach_the_tools_in_the_test_only_copy(self):
        # Without this, "exit 7 and no call" could be a fixture that never worked: in the test-only
        # copy each command passes its guards and performs exactly its synthetic operation.
        for name, command in COMMANDS.items():
            with self.subTest(function=name):
                proc, calls = self.bash(fixtures.for_stub_run(self.library_plus(command)))
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual([c for c in calls if c[0] in MUTATING], [OPERATIONS[name]])
                self.assertNotIn("destructive execution is disabled", proc.stderr)

    def test_nothing_in_the_environment_turns_it_on(self):
        rc = self.dir / "rc.sh"
        rc.write_text("cl_destructive_gate() { :; }\nCL_DESTRUCTIVE_EXECUTION=enabled\n")
        environments = (
            {"CL_DESTRUCTIVE_EXECUTION": "enabled", "CL_DESTRUCTIVE_GATE": "off", "CL_ALLOW_DESTRUCTIVE": "1"},
            {"BASH_FUNC_cl_destructive_gate%%": "() { :; }"},  # an exported shell function
            {"BASH_FUNC_cl_die%%": "() { :; }"},                # the helper the gate calls
            {"BASH_ENV": str(rc), "ENV": str(rc)},
        )
        for extra in environments:
            for name, command in COMMANDS.items():
                with self.subTest(env=sorted(extra), function=name):
                    proc, calls = self.bash(self.library_plus(command), extra_env=extra)
                    self.assert_disabled(proc, calls, name)

    # -- the gate alone is not enough: `exit` can be replaced from outside ------------------------
    SHADOWED_EXIT = ({"BASH_FUNC_exit%%": "() { return 0; }"},
                     {"BASH_FUNC_exit%%": "() { return 0; }", "BASH_FUNC_builtin%%": "() { return 0; }",
                      "BASH_FUNC_command%%": "() { return 0; }", "BASH_FUNC_return%%": "() { :; }"})

    def test_with_exit_replaced_the_gate_is_passed_and_still_nothing_destructive_runs(self):
        rc = self.dir / "rc.sh"
        rc.write_text("exit() { return 0; }\n")
        for extra in (*self.SHADOWED_EXIT, {"BASH_ENV": str(rc)}):
            for name, command in COMMANDS.items():
                with self.subTest(env=sorted(extra), function=name):
                    proc, calls = self.bash(self.library_plus(command), extra_env=extra)
                    self.assertEqual([c for c in calls if c[0] in MUTATING], [], proc.stderr)
        # The bypass is real (this is what makes the check above mean something): with `exit` replaced
        # the shipped gate does not stop the function, and the guards behind it are reached.
        proc, calls = self.bash(self.library_plus(COMMANDS["cl_destroy_guest"]), extra_env=self.SHADOWED_EXIT[0])
        self.assertNotEqual(proc.returncode, 7)
        self.assertTrue(calls, "the function ran past the gate and read the host state")
        # Control: in each of those environments the test-only copy, which has the commands, performs
        # every one of the four synthetic operations, so their absence above is the shipped text's doing.
        for extra in (*self.SHADOWED_EXIT, {"BASH_ENV": str(rc)}):
            for name, command in COMMANDS.items():
                with self.subTest(control=sorted(extra), function=name):
                    proc, calls = self.bash(fixtures.for_stub_run(self.library_plus(command)), extra_env=extra)
                    self.assertIn(OPERATIONS[name], calls, proc.stderr)

    def test_a_definition_placed_before_the_library_does_not_survive_it(self):
        # What a rendered preamble could carry: the library text comes later and defines the gate again.
        script = "cl_destructive_gate() { :; }\ncl_die() { :; }\n" + self.library_plus(COMMANDS["cl_destroy_guest"])
        proc, calls = self.bash(script)
        self.assert_disabled(proc, calls, "cl_destroy_guest")


class RenderedScriptTests(ApplyHarness, StubRun):
    def setUp(self):
        ApplyHarness.setUp(self)

    def tearDown(self):
        ApplyHarness.tearDown(self)

    def rendered(self, overrides, backup_storage=None):
        m = manifest.build(self.inv, classes(self.inv, overrides), backup_storage)
        return m, hostrun.render("apply-manifest", self.cfg, m, inventory=self.inv, overrides=overrides)

    def variants(self):
        with_volume = dict(EVIDENCE, **override(f"volume/{ISO}"))
        return {"guests, config-only backup": (EVIDENCE, None),
                "guests, stop-mode backup": (EVIDENCE, "local"),
                "guests and a volume": (with_volume, None)}

    def test_the_gate_is_the_first_command_of_every_manifest_body(self):
        for label, (overrides, backup) in self.variants().items():
            with self.subTest(variant=label):
                m, _script = self.rendered(overrides, backup)
                body = manifest.render_host_script(m, self.inv, classes(self.inv, overrides))
                commands = [line for line in body.splitlines() if line.strip() and not line.startswith("#")]
                self.assertEqual(commands[0], "cl_destructive_gate apply-manifest")
                self.assertEqual(body.count("cl_destructive_gate"), 1)
                self.assertTrue(body.startswith("# DISABLED:"))

    def test_the_rendered_script_exits_7_without_one_tool_call(self):
        for label, (overrides, backup) in self.variants().items():
            with self.subTest(variant=label):
                _m, script = self.rendered(overrides, backup)
                proc, calls = self.bash(script)
                self.assert_disabled(proc, calls, "apply-manifest")
                self.assertNotIn("live safety checks", proc.stderr)
                self.assertNotIn("manifest complete", proc.stderr)

    def test_control_the_test_only_copy_of_the_same_script_runs_to_the_end(self):
        _m, script = self.rendered(EVIDENCE)
        proc, calls = self.bash(fixtures.for_stub_run(script))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("manifest complete", proc.stderr)
        self.assertTrue([c for c in calls if c[0] in MUTATING])

    def test_nothing_in_the_environment_turns_the_rendered_script_on(self):
        _m, script = self.rendered(EVIDENCE)
        for extra in ({"BASH_FUNC_cl_destructive_gate%%": "() { :; }"}, {"CL_DESTRUCTIVE_EXECUTION": "enabled"}):
            with self.subTest(env=sorted(extra)):
                proc, calls = self.bash(script, extra_env=extra)
                self.assert_disabled(proc, calls, "apply-manifest")

    def test_with_exit_replaced_no_rendered_script_runs_a_destructive_command(self):
        for label, (overrides, backup) in self.variants().items():
            _m, script = self.rendered(overrides, backup)
            for extra in ShippedLibraryTests.SHADOWED_EXIT:
                with self.subTest(variant=label, env=sorted(extra)):
                    proc, calls = self.bash(script, extra_env=extra)
                    self.assertEqual([c for c in calls if c[0] in MUTATING], [], proc.stderr)
        _m, script = self.rendered(EVIDENCE)  # control: the test-only copy does, in the same environment
        proc, calls = self.bash(fixtures.for_stub_run(script), extra_env=ShippedLibraryTests.SHADOWED_EXIT[0])
        self.assertTrue([c for c in calls if c[0] in MUTATING])

    def test_preview_still_validates(self):
        # show apply-manifest prints the (refusing) script for a valid request and refuses a request
        # whose overrides are not the ones the manifest was classified with: validation is unchanged.
        paths = ["--manifest", self.write("m.json", self.m), "--inventory", self.write("inv.json", self.inv)]
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = hostrun.main(["show", "apply-manifest", *paths, "--overrides", self.write("ov.json", EVIDENCE)])
            self.assertEqual(code, 0)
            self.assertIn("\ncl_destructive_gate apply-manifest\n", out.getvalue())
            out, err = io.StringIO(), io.StringIO()
            forged = dict(EVIDENCE, **override("vm/9101"))
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = hostrun.main(["show", "apply-manifest", *paths, "--overrides", self.write("forged.json", forged)])
            self.assertEqual((code, out.getvalue()), (2, ""))
            self.assertTrue(err.getvalue().strip())

    def test_run_through_the_command_line_starts_nothing(self):
        argv = ["run", "apply-manifest", "--manifest", self.write("m.json", self.m),
                "--sha256", manifest.manifest_hash(self.m), "--inventory", self.write("inv.json", self.inv),
                "--overrides", self.write("ov.json", EVIDENCE)]
        real_run, out, err = hostrun.run, io.StringIO(), io.StringIO()

        def as_the_owner(*args, **kwargs):
            # The command line as the owner would reach it: not an agent session, on a terminal. Without
            # this the agent or terminal check would refuse first and the test would not see the
            # disablement at all.
            kwargs.update(env={"PATH": "/usr/bin:/bin"}, ancestors=(), is_tty=lambda: True, stdout=out,
                          stdin=io.StringIO(manifest.manifest_hash(self.m)[:8] + "\n"))
            return real_run(*args, **kwargs)

        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}), \
                mock.patch.object(hostrun, "run", side_effect=as_the_owner), \
                mock.patch.object(hostrun.subprocess, "Popen") as popen, \
                mock.patch.object(hostrun.subprocess, "run") as runner, \
                mock.patch.object(manifest, "render_host_script") as rendered, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = hostrun.main(argv)
        self.assertEqual(code, 2)
        self.assertIn("apply-manifest is disabled in this version of the tooling", err.getvalue())
        self.assertIn("Manifest for node", out.getvalue())  # validated and listed, then refused
        self.assertNotIn("Type the first 8 characters", out.getvalue())
        self.assertEqual((popen.call_count, runner.call_count, rendered.call_count), (0, 0, 0))

    def test_the_action_list_says_so(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(hostrun.main(["list"]), 0)
        line = next(l for l in out.getvalue().splitlines() if l.startswith("apply-manifest"))
        self.assertIn("DISABLED", line)


class BlockedActionTests(ApplyHarness, unittest.TestCase):
    """An action with an open blocking review finding is refused by ``run``; ``show`` still prints it."""

    def test_run_refuses_the_sentinel_action_before_anything_is_rendered_or_started(self):
        self.assertEqual(sorted(hostrun.BLOCKED_ACTIONS), ["sentinel"])
        popen, runner, out = mock.Mock(), mock.Mock(), io.StringIO()
        with mock.patch.object(hostrun, "render", wraps=hostrun.render) as rendered:
            with self.assertRaisesRegex(hostrun.HostRunError,
                                        "sentinel is blocked in this version.*open blocking review finding, not fixed"):
                hostrun.run("sentinel", self.cfg, stdin=io.StringIO("x\n"), stdout=out, env={"PATH": "/usr/bin:/bin"},
                            ancestors=(), is_tty=lambda: True, runner=runner, popen=popen,
                            addr_check=lambda _addr: None)
        self.assertEqual((popen.call_count, runner.call_count, rendered.call_count), (0, 0, 0))
        self.assertEqual(out.getvalue(), "")
        self.assertFalse((self.dir / "state" / "approvals.jsonl").exists())

    def test_control_an_action_that_is_not_blocked_reaches_the_prompt(self):
        popen, runner, out = mock.Mock(), mock.Mock(), io.StringIO()
        code = hostrun.run("preflight", self.cfg, stdin=io.StringIO("x\n"), stdout=out, env={"PATH": "/usr/bin:/bin"},
                           ancestors=(), is_tty=lambda: True, runner=runner, popen=popen,
                           addr_check=lambda _addr: None)
        self.assertEqual(code, 1)  # a wrong answer at the prompt: aborted, nothing sent
        self.assertIn("Type the first 8 characters", out.getvalue())
        self.assertEqual(popen.call_count, 0)

    def test_the_blocked_action_can_still_be_shown_and_is_labelled(self):
        self.assertIn("cl_log", hostrun.render("sentinel", self.cfg))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(hostrun.main(["list"]), 0)
        line = next(l for l in out.getvalue().splitlines() if l.startswith("sentinel"))
        self.assertIn("BLOCKED", line)


class StaticTests(unittest.TestCase):
    """What the text of the tree says, so that a later edit cannot quietly open a path."""

    @staticmethod
    def functions(text):
        """{name: body lines} for every ``name() {`` ... ``}`` block that starts in column 0."""
        found, name, body = {}, None, []
        for line in text.splitlines():
            head = re.match(r"^([a-z_]+)\(\) \{(.*)$", line)
            if name is None and head:
                if head.group(2).rstrip().endswith("}"):
                    found[head.group(1)] = [head.group(2)]
                    continue
                name, body = head.group(1), []
            elif name is not None and line == "}":
                found[name], name = body, None
            elif name is not None:
                body.append(line)
        return found

    DESTRUCTIVE = re.compile(r'"\$cmd" (stop|destroy|shutdown)\b|\b(qm|pct) (stop|destroy|shutdown)\b'
                             r"|\bpvesm free\b|\bvzdump \"|\bzfs destroy\b|\blvremove\b")

    def test_the_gate_has_one_definition_and_no_branch(self):
        text = LIB.read_text(encoding="utf-8")
        definitions = [line for line in text.splitlines() if line.startswith("cl_destructive_gate()")]
        self.assertEqual(definitions, [GATE_LINE])
        self.assertNotRegex(GATE_LINE, r"\bif\b|\[|\|\||&&|\$\{|\$CL_|return")

    def test_the_library_holds_no_destructive_command_only_four_comments_between_two_gates(self):
        text = LIB.read_text(encoding="utf-8")
        code = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
        self.assertEqual([line for line in code if self.DESTRUCTIVE.search(line)], [],
                         "a destructive command stands in the shipped library as executable text")
        funcs = self.functions(text)
        disabled = {name: [n for n, line in enumerate(body) if line.strip().startswith("# DISABLED-COMMAND: ")]
                    for name, body in funcs.items()}
        self.assertEqual(sorted(name for name, hits in disabled.items() if hits), sorted(GATED))
        self.assertEqual(text.count("# DISABLED-COMMAND: "), len(GATED))
        for name in GATED:
            body, (n,) = funcs[name], disabled[name]
            self.assertEqual(body[0].strip(), f"cl_destructive_gate {name}", name)   # first statement
            self.assertRegex(body[n], self.DESTRUCTIVE)                              # the comment is the command
            self.assertEqual(body[n + 1].strip(), f"cl_destructive_gate {name}", name)  # and a gate follows it
            self.assertEqual(n + 2, len(body), f"{name}: nothing may follow the second gate")

    def test_the_test_only_copy_is_the_shipped_text_plus_exactly_those_five_lines(self):
        shipped = LIB.read_text(encoding="utf-8").split("\n")
        copy = fixtures.for_stub_run("\n".join(shipped)).split("\n")
        self.assertEqual(len(copy), len(shipped))
        changed = [(a, b) for a, b in zip(shipped, copy) if a != b]
        self.assertEqual(len(changed), 1 + len(GATED))
        self.assertEqual(changed[0], (GATE_LINE, fixtures.GATE_NEUTRALIZED))
        for before, after in changed[1:]:
            self.assertEqual(before.replace("# DISABLED-COMMAND: ", "", 1), after)
            self.assertRegex(after, self.DESTRUCTIVE)

    def test_no_host_action_calls_a_gated_function_or_removes_anything(self):
        for path in sorted((AGENT_DIR / "host" / "actions").glob("*.sh")):
            code = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")]
            with self.subTest(action=path.name):
                for line in code:
                    self.assertNotRegex(line, r"\b(" + "|".join(GATED) + r"|cl_destructive_gate)\b")
                    self.assertNotRegex(line, r"\b(qm|pct) (destroy|stop|shutdown)\b|\bpvesm free\b|\bzfs destroy\b")
                backups = [line for line in code if re.search(r"\bvzdump \"", line)]
                # the one stop-mode backup in an action is the sentinel fixture's own guest
                self.assertEqual(bool(backups), path.name == "sentinel.sh")
                for line in backups:
                    self.assertIn('vzdump "$CL_SENTINEL_VMID"', line)

    def test_the_only_destructive_action_is_the_manifest_and_only_it_renders_the_manifest_body(self):
        self.assertEqual(hostrun.DESTRUCTIVE_ACTIONS, frozenset({"apply-manifest"}))
        source = (AGENT_DIR / "lab_agent" / "hostrun.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("mf.render_host_script("), 1)
        self.assertEqual(source.count("raise HostRunError(DESTRUCTIVE_DISABLED.format(action=action_name))"), 2)
        for name in sorted(set(hostrun.ACTIONS) - hostrun.DESTRUCTIVE_ACTIONS):
            self.assertTrue((AGENT_DIR / "host" / "actions" / f"{name}.sh").is_file(), name)

    def test_the_routine_command_line_and_the_mcp_module_cannot_reach_it(self):
        for argv in (["apply-manifest"], ["run", "apply-manifest"], ["manifest", "apply", "x"]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as stop:  # argparse: no such command
                    cli.main(argv)
                self.assertEqual(stop.exception.code, 2)
        for name in ("cli.py", "mcp.py"):
            source = (AGENT_DIR / "lab_agent" / name).read_text(encoding="utf-8")
            self.assertNotIn("hostrun.run", source)
            self.assertNotIn("render_host_script", source)
            self.assertNotIn("apply-manifest", source)

    def test_the_test_only_copy_is_used_by_tests_only(self):
        shipped = [p for sub in ("lab_agent", "host", "bin", "demo", "proposed", "docs")
                   for p in (AGENT_DIR / sub).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        self.assertTrue(shipped)
        for path in shipped:
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("for_stub_run", text, path)
            self.assertNotIn("TEST-ONLY COPY: gate neutralized", text, path)
        with self.assertRaises(AssertionError):  # a script without the library is refused, not passed on
            fixtures.for_stub_run("echo nothing here\n")
        with self.assertRaises(AssertionError):  # so is a gate that is not the shipped one
            fixtures.for_stub_run('cl_destructive_gate() { [ "$X" = 1 ] || exit 7; }\n')


if __name__ == "__main__":
    unittest.main()
