"""The network-less acceptance script (tests/run-netless.sh).

Like test_gate_run.py, each test runs the script with an isolated PATH: a directory of
symlinks to the few real tools it needs, plus, where a test says so, a stub `docker` that only
logs its arguments and prints canned unittest output. The real Docker daemon, its images and
its network are never touched. The proof program that runs inside the container is tested
here separately, with a fake `socket` module.
"""

import errno
import io
import os
import re
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from tests import fixtures

SCRIPT = Path(__file__).resolve().parent / "run-netless.sh"
GATE = Path(__file__).resolve().parent / "run.sh"
TOOLS = ("bash", "grep", "sed", "cat", "rm", "mktemp", "chmod", "id", "cut", "tail", "dirname", "basename")
IMAGE = "python:3.12.14-slim"

STUB_DOCKER = """#!@BASH@
printf '%s\\n' "$*" >> "$STUB_DOCKER_LOG"
case "$1" in
  image) exit "${STUB_INSPECT_RC:-0}" ;;
  ps) if [ "${STUB_LEFTOVER:-0}" = 1 ]; then echo deadbeef0001; fi; exit 0 ;;
  rm) exit 0 ;;
  run) ;;
  *) exit 97 ;;
esac
# the files the script mounts must exist while the container would run
for a in "$@"; do
  case "$a" in
    *:/netless:ro) d=${a%%:*}; [ -f "$d/proof.py" ] || exit 96
                   cat "$d/passwd" >> "$STUB_FILES_LOG"; cat "$d/group" >> "$STUB_FILES_LOG"
                   cp "$d/proof.py" "$STUB_PROOF_COPY" ;;
  esac
done
case "${STUB_MODE:-pass}" in
  daemon_error) echo "docker: Error response from daemon: boom" >&2; exit 125 ;;
esac
case "${STUB_MODE:-pass}" in
  proof_fail) echo "NETLESS-PROOF interfaces: eth0,lo"
              echo "NETLESS-PROOF: FAILED interfaces other than lo: eth0"; exit 1 ;;
  *) echo "NETLESS-PROOF interfaces: lo"
     echo "NETLESS-PROOF connect 192.0.2.1: refused ENETUNREACH in 0.00s"
     [ "${STUB_MODE:-pass}" = no_marker ] || echo "NETLESS-PROOF: HELD" ;;
esac
echo "test_alpha (tests.test_x.T.test_alpha) ... ok"
case "${STUB_MODE:-pass}" in
  skip) echo "test_needs_tool (tests.test_x.T.test_needs_tool) ... skipped 'tool not installed'"
        printf '\\nRan 2 tests in 0.1s\\n\\nOK (skipped=1)\\n' ;;
  test_fail) echo "test_bad (tests.test_x.T.test_bad) ... FAIL"
             printf '\\nRan 2 tests in 0.1s\\n\\nFAILED (failures=1)\\n'; exit 1 ;;
  zero) printf '\\nRan 0 tests in 0.0s\\n\\nOK\\n' ;;
  *) printf '\\nRan 5 tests in 0.1s\\n\\nOK\\n' ;;
esac
exit "${STUB_RUN_RC:-0}"
""".replace("@BASH@", "{bash}")


class NetlessScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        base = Path(self.tmp.name)
        self.bin, self.stub_bin, self.tmpdir = base / "bin", base / "stub-bin", base / "script-tmp"
        self.log, self.files_log, self.proof_copy = base / "docker.log", base / "files.log", base / "proof.copy"
        for d in (self.bin, self.stub_bin, self.tmpdir):
            d.mkdir()
        for tool in TOOLS:
            real = shutil.which(tool)
            if real is None:
                self.fail(f"required tool not found for the test: {tool}")
            (self.bin / tool).symlink_to(real)
        # `cp` is used only by the stub
        (self.stub_bin / "cp").symlink_to(shutil.which("cp"))
        stub = self.stub_bin / "docker"
        stub.write_text(STUB_DOCKER.replace("{bash}", shutil.which("bash")))
        stub.chmod(0o755)
        self.log.write_text("")
        self.files_log.write_text("")

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, docker=True, **env):
        path = str(self.bin) + (os.pathsep + str(self.stub_bin) if docker else "")
        full = {"PATH": path, "HOME": self.tmp.name, "TMPDIR": str(self.tmpdir), "LC_ALL": "C",
                "STUB_DOCKER_LOG": str(self.log), "STUB_FILES_LOG": str(self.files_log),
                "STUB_PROOF_COPY": str(self.proof_copy), **env}
        proc = subprocess.run([str(self.bin / "bash"), str(SCRIPT)], stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, env=full, timeout=60)
        return proc.returncode, proc.stdout.rstrip("\n").splitlines(), proc

    def calls(self):
        return self.log.read_text().splitlines()

    def run_call(self):
        runs = [c for c in self.calls() if c.startswith("run ")]
        self.assertEqual(len(runs), 1, self.calls())
        return runs[0]

    # -- the three result paths ---------------------------------------------------------------
    def test_pass_only_when_proofs_held_and_every_test_ran(self):
        code, lines, proc = self.run_script()
        self.assertEqual(code, 0, proc.stdout + proc.stderr)
        self.assertEqual(lines[-1], "RESULT: PASS (network-less proofs held; Ran 5 tests; OK)")
        self.assertIn("  NETLESS-PROOF interfaces: lo", lines)
        self.assertIn("  NETLESS-PROOF: HELD", lines)
        self.assertIn("  Ran 5 tests / OK", lines)
        self.assertIn("  no container left behind", lines)

    def test_skipped_test_is_incomplete_and_named(self):
        code, lines, proc = self.run_script(STUB_MODE="skip")
        self.assertEqual(code, 2, proc.stdout + proc.stderr)
        self.assertTrue(lines[-1].startswith("RESULT: INCOMPLETE"), lines[-1])
        self.assertTrue(any(l.startswith("  skipped test: test_needs_tool") for l in lines), lines)
        self.assertNotIn("RESULT: PASS", proc.stdout)

    def test_missing_docker_is_incomplete_and_nothing_runs(self):
        code, lines, proc = self.run_script(docker=False)
        self.assertEqual(code, 2, proc.stdout + proc.stderr)
        self.assertEqual(lines[-1], "RESULT: INCOMPLETE (not a pass; docker not found on PATH)")
        self.assertEqual(self.calls(), [])

    def test_absent_image_is_incomplete_and_never_pulled(self):
        code, lines, proc = self.run_script(STUB_INSPECT_RC="1")
        self.assertEqual(code, 2, proc.stdout + proc.stderr)
        self.assertIn(f"image {IMAGE} not present locally or docker daemon unreachable", lines[-1])
        self.assertEqual([c for c in self.calls() if not c.startswith("ps ")], [f"image inspect {IMAGE}"])

    def test_failures_exit_1(self):
        cases = {
            "proof_fail": "network-less proof did not hold",
            "no_marker": "network-less proof did not hold",   # tests ran, but the proof line is absent
            "test_fail": "python unit tests (Ran 2 tests; FAILED (failures=1); exit 1)",
            "zero": "python unit tests (Ran 0 tests; OK; exit 0)",
            "daemon_error": "network-less proof did not hold",
        }
        for mode, reason in cases.items():
            with self.subTest(mode=mode):
                code, lines, proc = self.run_script(STUB_MODE=mode)
                self.assertEqual(code, 1, proc.stdout + proc.stderr)
                self.assertTrue(lines[-1].startswith("RESULT: FAIL"), lines[-1])
                self.assertTrue(any(l.startswith("failed:  ") and reason in l for l in lines), lines)
                self.assertNotIn("RESULT: PASS", proc.stdout)

    def test_failed_proof_shows_why_and_a_failed_test_shows_its_name(self):
        _, lines, _ = self.run_script(STUB_MODE="proof_fail")
        self.assertIn("  NETLESS-PROOF: FAILED interfaces other than lo: eth0", lines)
        _, lines, _ = self.run_script(STUB_MODE="test_fail")
        self.assertIn("  test_bad (tests.test_x.T.test_bad) ... FAIL", lines)
        self.assertFalse(any("test_alpha" in l for l in lines))  # passing tests are not repeated

    def test_failure_outranks_a_skip(self):
        code, lines, _ = self.run_script(STUB_MODE="test_fail", STUB_RUN_RC="0")
        self.assertEqual(code, 1)

    # -- the container invocation --------------------------------------------------------------
    def test_container_arguments(self):
        self.run_script()
        call = self.run_call()
        args = call.split(" ")
        uid, gid = os.getuid(), os.getgid()
        for needle in ("run --rm --pull=never --label corelab-netless=",
                       "--network none", "--read-only", "--cap-drop ALL", "--security-opt no-new-privileges",
                       "--pids-limit 512", "--memory 2g", f"--user {uid}:{gid}", "--tmpfs /tmp:exec,mode=1777",
                       "-e HOME=/tmp/home", "-e PYTHONDONTWRITEBYTECODE=1", "-e TMPDIR=/tmp", "-w /work/lab-agent"):
            self.assertIn(needle, call)
        self.assertIn(f" {IMAGE} /usr/bin/sh -c ", call)
        # every mount is read-only, none is the docker socket, none is a writable host path
        docker_args = args[:args.index(IMAGE)]   # the -v of `unittest -v` after the image is not a mount
        mounts = [docker_args[i + 1] for i, a in enumerate(docker_args) if a == "-v"]
        self.assertEqual(len(mounts), 5, mounts)
        self.assertTrue(all(m.endswith(":ro") for m in mounts), mounts)
        self.assertNotIn("docker.sock", call)
        self.assertIn("/usr:/usr:ro", mounts)
        self.assertTrue(any(m.endswith(":/work:ro") for m in mounts))
        self.assertTrue(any(m.endswith(":/etc/passwd:ro") for m in mounts))
        self.assertTrue(any(m.endswith(":/etc/group:ro") for m in mounts))
        for forbidden in ("--privileged", "--network host", "--cap-add", "--volumes-from", "--device"):
            self.assertNotIn(forbidden, call)
        # the proof runs before the tests, and only if it succeeds
        self.assertRegex(call, r"/netless/proof\.py && /usr/bin/python3 -m unittest discover -v -s tests -t \.'?$")

    def test_only_inspect_run_and_ps_are_used_never_pull_build_or_install(self):
        self.run_script()
        verbs = {c.split(" ")[0] for c in self.calls()}
        self.assertLessEqual(verbs, {"image", "run", "ps"})

    def test_synthetic_user_files_hold_only_root_and_the_callers_ids(self):
        self.run_script()
        text = self.files_log.read_text()
        uid, gid = os.getuid(), os.getgid()
        self.assertIn("root:x:0:0:root:/root:/bin/sh", text)
        self.assertIn(f"tester:x:{uid}:{gid}:synthetic user:/tmp/home:/bin/sh", text)
        self.assertIn("root:x:0:\n", text)
        self.assertIn(f"tester:x:{gid}:\n", text)
        self.assertEqual(len([l for l in text.splitlines() if l.startswith("tester:")]), 2)
        self.assertNotRegex(text, r"/home/|@|\.invalid|real")

    def test_private_scratch_is_removed_on_exit_and_for_every_result(self):
        for mode in ("pass", "skip", "test_fail", "proof_fail"):
            with self.subTest(mode=mode):
                self.run_script(STUB_MODE=mode)
                self.assertEqual(list(self.tmpdir.iterdir()), [])
        self.run_script(docker=False)
        self.assertEqual(list(self.tmpdir.iterdir()), [])

    # -- no container left behind ----------------------------------------------------------------
    def test_a_container_left_behind_is_removed_and_fails_the_run(self):
        code, lines, proc = self.run_script(STUB_LEFTOVER="1")
        self.assertEqual(code, 1, proc.stdout + proc.stderr)
        self.assertTrue(any(l.startswith("failed:  a container with label corelab-netless=") for l in lines), lines)
        self.assertTrue(any(c.startswith("rm -f deadbeef0001") for c in self.calls()), self.calls())
        self.assertNotIn("  no container left behind", lines)

    def test_the_check_looks_by_label_which_the_run_set(self):
        self.run_script()
        label = re.search(r"--label (corelab-netless=\S+)", self.run_call()).group(1)
        ps = [c for c in self.calls() if c.startswith("ps ")]
        self.assertTrue(ps)
        self.assertTrue(all(f"--filter label={label}" in c for c in ps), ps)

    # -- what the script must not become -----------------------------------------------------------
    def test_script_source_never_pulls_builds_or_touches_the_socket(self):
        text = SCRIPT.read_text()
        self.assertIsNone(re.search(r"docker\s+(pull|build|login|commit|cp|exec)\b", text))
        self.assertNotIn("docker.sock", text)
        self.assertIn("--pull=never", text)
        self.assertIn("--network none", text)
        self.assertNotIn("--privileged", text)

    def test_it_is_a_separate_command_not_part_of_the_gate(self):
        self.assertNotIn("run-netless", GATE.read_text())
        self.assertTrue(os.access(SCRIPT, os.X_OK))


class ProofProgramTests(unittest.TestCase):
    """The program the container runs before the tests, executed against a fake socket module."""

    @classmethod
    def setUpClass(cls):
        m = re.search(r"<<'PY'\n(.*?)\nPY\n", SCRIPT.read_text(), re.S)
        assert m, "proof program not found in run-netless.sh"
        cls.code = m.group(1)

    def run_proof(self, ifaces, connect, clock=None):
        class FakeSocket:
            def __init__(self, *_):
                pass

            def settimeout(self, _):
                pass

            def connect(self, addr):
                connect(addr)

            def close(self):
                pass

        fake = mock.MagicMock()
        fake.AF_INET, fake.AF_INET6, fake.SOCK_STREAM = 2, 10, 1
        fake.if_nameindex.return_value = [(i + 1, n) for i, n in enumerate(ifaces)]
        fake.socket = FakeSocket
        out = io.StringIO()
        patches = [mock.patch.dict(sys.modules, {"socket": fake})]
        if clock is not None:
            patches.append(mock.patch("time.monotonic", side_effect=clock))
        for p in patches:
            p.start()
        try:
            with redirect_stdout(out):
                try:
                    exec(compile(self.code, "proof.py", "exec"), {"__name__": "__main__"})
                    code = 0
                except SystemExit as exc:
                    code = exc.code
        finally:
            for p in patches:
                p.stop()
        return code, out.getvalue()

    @staticmethod
    def refuse(_addr):
        raise OSError(errno.ENETUNREACH, "Network is unreachable")

    def test_loopback_only_and_immediate_failure_hold(self):
        code, out = self.run_proof(["lo"], self.refuse)
        self.assertEqual(code, 0, out)
        self.assertIn("NETLESS-PROOF interfaces: lo", out)
        self.assertIn("connect 192.0.2.1: refused ENETUNREACH", out)
        self.assertIn("connect 2001:db8::1: refused ENETUNREACH", out)
        self.assertTrue(out.rstrip().endswith("NETLESS-PROOF: HELD"))

    def test_another_interface_fails_the_proof(self):
        for ifaces in (["lo", "eth0"], ["eth0"], ["lo", "docker0"], []):
            with self.subTest(ifaces=ifaces):
                code, out = self.run_proof(ifaces, self.refuse)
                self.assertEqual(code, 1, out)
                self.assertIn("NETLESS-PROOF: FAILED interfaces other than lo", out)
                self.assertNotIn("NETLESS-PROOF: HELD", out)

    def test_a_connect_that_succeeds_fails_the_proof(self):
        code, out = self.run_proof(["lo"], lambda _a: None)
        self.assertEqual(code, 1, out)
        self.assertIn("connect to 192.0.2.1 succeeded", out)

    def test_a_connect_that_times_out_fails_the_proof(self):
        def timeout(_a):
            raise TimeoutError()
        code, out = self.run_proof(["lo"], timeout)
        self.assertEqual(code, 1, out)
        self.assertIn("timed out instead of failing at once", out)

    def test_a_slow_refusal_fails_the_proof(self):
        ticks = iter([0.0, 2.5, 10.0, 12.5])  # two connects, each taking 2.5 s
        code, out = self.run_proof(["lo"], self.refuse, clock=lambda: next(ticks))
        self.assertEqual(code, 1, out)
        self.assertIn("took 2.50s to fail", out)


if __name__ == "__main__":
    unittest.main()
