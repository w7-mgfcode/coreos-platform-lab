"""Mission L1B, task O-4: the snippet writer under a real sshd with a separate identity.

Two parts, both offline and neither starting a container:

* the writer's directory-owner check (`expected_dir_uid`), found missing by the harness: the
  plan (section 7) says the snippet directory is root-owned, and nothing verified it;
* the harness `tests/o4/run-o4.sh`: its result contract (PASS 0, FAIL 1, INCOMPLETE 2, a case
  that did not run is a FAIL), checked with a fake `docker` that prints canned logs, and the
  static facts it depends on (the case list, the markers it cuts out of prepare.sh).

The harness itself (a container with the workstation's sshd) is run by hand or from the
gate owner's decision; see the L1B report. An offline PASS is not live evidence.
"""

import json
import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import fixtures

LA = Path(__file__).resolve().parent.parent
WRITER = LA / "host" / "snippet-writer" / "corelab-snippet-put"
CONF_TEMPLATE = LA / "host" / "snippet-writer" / "snippet-writer.conf"
PREPARE = LA / "host" / "actions" / "prepare.sh"
RUN_O4 = LA / "tests" / "o4" / "run-o4.sh"
INNER = LA / "tests" / "o4" / "inner.sh"
IGN = json.dumps({"ignition": {"version": "3.4.0"}}).encode()


class DirOwnerCheckTests(unittest.TestCase):
    """The writer refuses a snippet directory that is not owned by `expected_dir_uid`."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        base = Path(self.tmp.name)
        self.dir = base / "snippets"
        self.dir.mkdir(mode=0o2770)
        self.conf = base / "w.conf"

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, command, *extra, data=IGN):
        self.conf.write_text("\n".join([f"dir = {os.path.realpath(self.dir)}", "max_bytes = 1024", *extra]) + "\n")
        env = {"PATH": "/usr/bin:/bin", "SSH_ORIGINAL_COMMAND": command}
        return subprocess.run(["perl", str(WRITER), "--config", str(self.conf)],
                              input=data, capture_output=True, env=env)

    def test_matching_owner_is_accepted_for_every_command(self):
        uid = f"expected_dir_uid = {os.getuid()}"
        self.assertEqual(self.call("put a", uid).returncode, 0)
        self.assertIn(b"corelab-a.ign", self.call("list", uid).stdout)
        self.assertEqual(self.call("rm a", uid).returncode, 0)

    def test_other_owner_is_refused_for_put_rm_and_list_with_nothing_written(self):
        other = f"expected_dir_uid = {os.getuid() + 4242}"
        for cmd in ("put a", "rm a", "list"):
            r = self.call(cmd, other)
            self.assertEqual(r.returncode, 3, cmd)
            self.assertIn(b"not owned by the expected user", r.stderr, cmd)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_the_refusal_is_the_owner_check_and_not_something_else(self):
        # same directory, same request, only the expected owner differs (the positive control)
        self.assertEqual(self.call("put a", f"expected_dir_uid = {os.getuid()}").returncode, 0)
        self.assertEqual(self.call("put a", f"expected_dir_uid = {os.getuid() + 1}").returncode, 3)

    def test_without_the_key_the_owner_is_not_checked(self):
        # existing behaviour, kept for configs that do not set the key
        self.assertEqual(self.call("put a").returncode, 0)

    def test_bad_value_is_a_config_error(self):
        for bad in ("expected_dir_uid = root", "expected_dir_uid = -1", "expected_dir_uid = 1.5"):
            self.assertEqual(self.call("list", bad).returncode, 4, bad)

    def test_installed_template_sets_root_as_the_expected_owner(self):
        text = CONF_TEMPLATE.read_text()
        self.assertRegex(text, r"(?m)^expected_dir_uid = 0$")
        self.assertIn("@SNIPPET_DIR@", text)
        # and the template is accepted by the writer once the placeholder is filled in
        conf = Path(self.tmp.name) / "installed.conf"
        conf.write_text(text.replace("@SNIPPET_DIR@", os.path.realpath(self.dir)))
        env = {"PATH": "/usr/bin:/bin", "SSH_ORIGINAL_COMMAND": "list"}
        r = subprocess.run(["perl", str(WRITER), "--config", str(conf)], capture_output=True, env=env)
        want = 0 if os.getuid() == 0 else 3  # a directory owned by a non-root test user is refused
        self.assertEqual(r.returncode, want, r.stderr)

    def test_writer_still_compiles(self):
        self.assertEqual(subprocess.run(["perl", "-c", str(WRITER)], capture_output=True).returncode, 0)


HOOK = r"""
# Test wrapper: runs the writer in-process and, right after the writer closes its temporary
# file, plays the part of another process that can write in the snippet directory.
BEGIN {
    *CORE::GLOBAL::sysopen = sub (*$$;$) {      # SIGTERM right after the temporary file was created
        my $r = @_ > 3 ? CORE::sysopen($_[0], $_[1], $_[2], $_[3]) : CORE::sysopen($_[0], $_[1], $_[2]);
        kill 'TERM', $$ if $r && ($ENV{O4_HOOK} // '') eq 'term-after-create' && $_[1] =~ /\.corelab-tmp-/;
        return $r;
    };
    *CORE::GLOBAL::close = sub (;*) {
        my $r = CORE::close($_[0]);
        my $mode = $ENV{O4_HOOK} // '';
        if ($mode eq 'swap-tmp') {            # temp name -> symlink to a file outside the directory
            my ($t) = glob("$ENV{O4_DIR}/.corelab-tmp-*");
            if (defined $t) { unlink $t; symlink($ENV{O4_VICTIM}, $t); }
        } elsif ($mode eq 'swap-target') {    # target name -> symlink, after the first target check
            if (glob("$ENV{O4_DIR}/.corelab-tmp-*")) { symlink($ENV{O4_VICTIM}, "$ENV{O4_DIR}/corelab-x.ign"); }
        }
        return $r;
    };
}
do $ENV{O4_WRITER} or die "cannot run writer: $@ $!";
"""


class TempFileRaceTests(unittest.TestCase):
    """Review findings: pathname chmod after close, and a temp file left by a late refusal."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        base = Path(self.tmp.name)
        self.dir = base / "snippets"
        self.dir.mkdir(mode=0o2770)
        self.conf = base / "w.conf"
        self.conf.write_text(f"dir = {os.path.realpath(self.dir)}\nmax_bytes = 1024\n")
        self.victim = base / "victim.txt"          # owned by the writer's user, outside the directory
        self.victim.write_text("outside\n")
        os.chmod(self.victim, 0o600)
        self.hook = base / "hook.pl"
        self.hook.write_text(HOOK)

    def tearDown(self):
        self.tmp.cleanup()

    def run_writer(self, writer, hook, command="put x", data=IGN):
        env = {"PATH": "/usr/bin:/bin", "SSH_ORIGINAL_COMMAND": command, "O4_HOOK": hook,
               "O4_DIR": os.path.realpath(self.dir), "O4_VICTIM": str(self.victim), "O4_WRITER": str(writer)}
        return subprocess.run(["perl", str(self.hook), "--config", str(self.conf)],
                              input=data, capture_output=True, env=env)

    def mutated(self, name, *pairs):
        text = WRITER.read_text()
        for old, new in pairs:
            self.assertIn(old, text, old)
            text = text.replace(old, new, 1)
        out = Path(self.tmp.name) / name
        out.write_text(text)
        return out

    def temp_files(self):
        return [p.name for p in self.dir.iterdir() if p.name.startswith(".corelab-tmp-")]

    def test_control_the_old_pathname_chmod_is_exploitable_by_the_hook(self):
        old = self.mutated("old.pl", ('chmod(0644, $fh) or die "chmod\\n";', ""),
                           ('close $fh or die "close\\n";', 'close $fh or die "close\\n";\n        chmod 0644, $tmp or die "chmod\\n";'))
        r = self.run_writer(old, "swap-tmp")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.victim.stat().st_mode & 0o777, 0o644)   # the outside file was chmod-ed

    def test_chmod_goes_through_the_open_handle_so_the_swapped_name_is_not_followed(self):
        r = self.run_writer(WRITER, "swap-tmp")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.victim.stat().st_mode & 0o777, 0o600)   # untouched
        self.assertEqual(self.victim.read_text(), "outside\n")

    def test_normal_put_still_ends_with_mode_0644(self):
        r = self.run_writer(WRITER, "")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.dir / "corelab-x.ign").stat().st_mode & 0o777, 0o644)

    def test_control_without_cleanup_a_late_refusal_leaves_the_temp_file(self):
        old = self.mutated("leak.pl", ("    $PENDING_TMP = $tmp if $fh;\n", ""))
        r = self.run_writer(old, "swap-target")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn(b"symlink", r.stderr)
        self.assertEqual(len(self.temp_files()), 1)                   # the hook reaches the late check

    def test_a_late_refusal_removes_the_temp_file(self):
        r = self.run_writer(WRITER, "swap-target")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn(b"symlink", r.stderr)
        self.assertEqual(self.temp_files(), [])
        self.assertEqual(self.victim.read_text(), "outside\n")

    def test_control_a_signal_between_create_and_registration_leaks_without_the_deferral(self):
        old = self.mutated("nodefer.pl", ("$DEFER = 1;", "$DEFER = 0;"))
        r = self.run_writer(old, "term-after-create")
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertEqual(len(self.temp_files()), 1)                   # the hook reaches the window

    def test_a_signal_between_create_and_registration_leaves_no_temp_file(self):
        r = self.run_writer(WRITER, "term-after-create")
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertEqual(self.temp_files(), [])
        self.assertFalse((self.dir / "corelab-x.ign").exists())

    def test_a_second_signal_during_the_cleanup_does_not_leave_the_temp_file(self):
        # A handled signal that arrives while the END block removes the file must not end the cleanup
        # early. Each copy sends itself a signal inside the END block, just before the unlink.
        for sig in ("TERM", "HUP", "INT", "PIPE"):
            with self.subTest(signal=sig):
                late = self.mutated(f"late-{sig}.pl", ("unlink $PENDING_TMP;", f"kill '{sig}', $$; unlink $PENDING_TMP;"))
                r = self.run_writer(late, "term-after-create")
                self.assertEqual(r.returncode, 4, r.stderr)
                self.assertEqual(self.temp_files(), [])
        # The ignore is the first statement of the END block: nothing of the cleanup runs before it.
        end = next(line for line in WRITER.read_text().splitlines() if line.startswith("END {"))
        self.assertTrue(end.startswith("END { $SIG{$_} = 'IGNORE' for qw(HUP INT TERM PIPE); if (defined $PENDING_TMP)"))
        # control: without the ignore, that same second signal leaves the temporary file behind
        old = self.mutated("old-end.pl", ("END { $SIG{$_} = 'IGNORE' for qw(HUP INT TERM PIPE); ", "END { "),
                           ("unlink $PENDING_TMP;", "kill 'TERM', $$; unlink $PENDING_TMP;"))
        self.run_writer(old, "term-after-create")
        self.assertNotEqual(self.temp_files(), [])

    def test_termination_signal_removes_the_temp_file(self):
        # SIGTERM between the creation and the rename: the END block still runs
        script = Path(self.tmp.name) / "term.pl"
        script.write_text(HOOK.replace("my $mode = $ENV{O4_HOOK} // '';", "my $mode = ''; if (glob(\"$ENV{O4_DIR}/.corelab-tmp-*\")) { kill 'TERM', $$; }"))
        env = {"PATH": "/usr/bin:/bin", "SSH_ORIGINAL_COMMAND": "put x", "O4_WRITER": str(WRITER),
               "O4_DIR": os.path.realpath(self.dir), "O4_VICTIM": str(self.victim)}
        r = subprocess.run(["perl", str(script), "--config", str(self.conf)], input=IGN, capture_output=True, env=env)
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertEqual(self.temp_files(), [])
        self.assertFalse((self.dir / "corelab-x.ign").exists())


class ListLinkCountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        base = Path(self.tmp.name)
        self.dir = base / "snippets"
        self.dir.mkdir(mode=0o2770)
        self.conf = base / "w.conf"
        self.conf.write_text(f"dir = {os.path.realpath(self.dir)}\nmax_bytes = 1024\n")

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, command, data=b""):
        env = {"PATH": "/usr/bin:/bin", "SSH_ORIGINAL_COMMAND": command}
        return subprocess.run(["perl", str(WRITER), "--config", str(self.conf)], input=data, capture_output=True, env=env)

    def test_list_hides_an_own_file_with_a_second_link_and_shows_it_again_without(self):
        self.assertEqual(self.call("put a", IGN).returncode, 0)
        self.assertEqual(self.call("put b", IGN).returncode, 0)
        extra = Path(self.tmp.name) / "extra-link"
        os.link(self.dir / "corelab-a.ign", extra)
        out = self.call("list").stdout
        self.assertNotIn(b"corelab-a.ign", out)
        self.assertIn(b"corelab-b.ign", out)                          # control: the single-link file is listed
        extra.unlink()
        self.assertIn(b"corelab-a.ign", self.call("list").stdout)


def expected_cases():
    text = RUN_O4.read_text()
    m = re.search(r'EXPECTED_CASES="((?:[^"\\]|\\\n)*)"', text)
    assert m, "EXPECTED_CASES not found in run-o4.sh"
    return m.group(1).replace("\\\n", " ").split()


def inner_case_ids():
    ids = set(re.findall(r"(?m)^check (\S+) ", INNER.read_text()))
    ids |= set(re.findall(r"c_ok (I0)\b", INNER.read_text()))
    return ids


class HarnessStaticTests(unittest.TestCase):
    def test_files_exist_and_are_executable_with_valid_syntax(self):
        for f in (RUN_O4, INNER):
            self.assertTrue(f.is_file(), f)
            self.assertTrue(f.stat().st_mode & stat.S_IXUSR, f)
            self.assertEqual(subprocess.run(["bash", "-n", str(f)], capture_output=True).returncode, 0, f)

    def test_the_case_list_of_the_runner_matches_the_cases_of_the_inner_script(self):
        want = expected_cases()
        self.assertEqual(len(want), len(set(want)), "duplicate case id in EXPECTED_CASES")
        self.assertEqual(set(want), inner_case_ids())

    def test_every_plan_case_s1_to_s9_has_a_case(self):
        have = set(expected_cases())
        for n in range(1, 10):
            self.assertTrue(any(c == f"S{n}" or c.startswith(f"S{n}.") for c in have), f"S{n}")

    def test_s10_is_not_claimed_by_the_harness(self):
        # S10 is the RBAC refusal of hookscript by the API token: it needs the lab.
        self.assertNotIn("S10", expected_cases())
        self.assertNotRegex(INNER.read_text(), r"(?m)^check S10(\s|\.)")

    def test_the_markers_the_inner_script_cuts_out_of_prepare_sh_exist(self):
        prepare = PREPARE.read_text()
        inner = INNER.read_text()
        for marker in (r"(?m)^la_sbin=", r"(?m)^la_cfgdir=", r"(?m)^la_home=", r"(?m)^la_root_dir\(\) \{",
                       r"(?m)^# snippet writer:", r"(?m)^# 4\. routine ACLs",
                       r'command="/usr/local/sbin/corelab-snippet-put"'):
            self.assertRegex(prepare, marker)
        # and the inner script looks for exactly these
        for needle in ("^la_sbin=", "^la_cfgdir=", "^la_home=", "^# snippet writer:", "^# 4\\. routine ACLs"):
            self.assertIn(needle, inner)

    def test_a_missing_extraction_marker_is_incomplete_not_a_result(self):
        inner = INNER.read_text()
        self.assertRegex(inner, r"grep -q '\^# snippet writer:'[^\n]*\|\| incomplete")
        self.assertRegex(inner, r"grep -q '\^# 4\\\. routine ACLs'[^\n]*\|\| incomplete")
        self.assertIn("--pull=never", RUN_O4.read_text())

    def test_the_harness_never_pulls_builds_or_installs(self):
        for f in (RUN_O4, INNER):
            code = "\n".join(l for l in f.read_text().splitlines() if not l.lstrip().startswith("#"))
            for bad in ("docker pull", "docker build", "docker load", "apt ", "apt-get", "pip install", "curl ", "wget "):
                self.assertNotIn(bad, code, f"{f.name}: {bad}")

    def test_the_container_has_no_network_and_no_host_write_access(self):
        code = RUN_O4.read_text()
        self.assertIn("--network none", code)
        self.assertIn("--read-only", code)
        self.assertIn("--cap-drop ALL", code)
        self.assertNotIn("--privileged", code)
        self.assertNotIn("docker.sock", code)
        self.assertNotIn("--network host", code)
        # every host path is mounted read-only
        mounts = re.findall(r'(?m)(?<=\s)-v ("[^"]+"|/\S+)', code)
        self.assertGreaterEqual(len(mounts), 8)
        for spec in mounts:
            self.assertTrue(spec.rstrip('"').endswith(":ro"), spec)

    def test_no_real_addresses_names_or_home_paths(self):
        for f in (RUN_O4, INNER):
            text = f.read_text()
            self.assertNotRegex(text, r"/home/", f.name)
            for ip in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text):
                self.assertTrue(ip.startswith("127.") or ip.startswith("192.0.2."), f"{f.name}: {ip}")


class HarnessContractTests(unittest.TestCase):
    """Run the real runner with a fake docker that prints a canned container log."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="o4-contract-")
        base = Path(self.tmp.name)
        self.bin = base / "bin"
        self.bin.mkdir()
        fake = self.bin / "docker"
        # fake docker: "run" records its arguments and prints the canned log; "ps" prints FAKE_PS_ID
        # (a container id that would be left behind) or fails; "rm" can be made to fail.
        fake.write_text(
            '#!/bin/sh\ncase "$1" in\n'
            '  run) printf "%s\\n" "$@" > "$FAKE_ARGS"; cat "$FAKE_LOG"; exit "${FAKE_RC:-0}";;\n'
            '  ps) [ -z "$FAKE_PS_FAIL" ] || exit 1; printf "%s" "$FAKE_PS_ID"; exit 0;;\n'
            '  rm) exit "${FAKE_RM_RC:-0}";;\n'
            '  *) exit 0;;\nesac\n')
        fake.chmod(0o755)
        self.args = base / "docker-run.args"
        self.log = base / "container.log"

    def tearDown(self):
        self.tmp.cleanup()

    def canned(self, skip=(), fail=(), extra=(), done=True, counts=None, after_done=()):
        lines = []
        cases = [c for c in expected_cases() if c not in skip]
        for c in cases:
            lines.append(f"CASE {c} {'FAIL' if c in fail else 'PASS'} text")
        lines += list(extra)
        if done:
            p, f = counts if counts else (len(cases) - len(fail) + sum(1 for e in extra if e.startswith("CASE") and "PASS" in e),
                                          len(fail) + sum(1 for e in extra if e.startswith("CASE") and "FAIL" in e))
            lines.append(f"INNER-DONE pass={p} fail={f} failed=x")
        lines += list(after_done)
        self.log.write_text("\n".join(lines) + "\n")

    def run_o4(self, **env_extra):
        env = {"PATH": f"{self.bin}:/usr/bin:/bin", "FAKE_LOG": str(self.log), "FAKE_ARGS": str(self.args),
               "TMPDIR": self.tmp.name, **env_extra}
        r = subprocess.run(["bash", str(RUN_O4)], capture_output=True, text=True, env=env, timeout=60)
        return r.returncode, r.stdout + r.stderr

    def prerequisites_present(self, out):
        # the runner's own prerequisite check (before any container) says "no case ran"; a MISSING line
        # that comes from the container's log is part of what the test feeds in
        return "no case ran" not in out

    def test_all_cases_pass_is_exit_0_when_the_workstation_has_what_it_needs(self):
        self.canned()
        rc, out = self.run_o4()
        if self.prerequisites_present(out):
            self.assertEqual(rc, 0, out)
            self.assertIn("RESULT: PASS", out)
        else:  # a workstation without sshd or perl: INCOMPLETE, never a pass
            self.assertEqual(rc, 2, out)
            self.assertNotIn("RESULT: PASS", out)

    def test_a_failed_case_is_exit_1(self):
        self.canned(fail=["S5.1"])
        rc, out = self.run_o4()
        if self.prerequisites_present(out):
            self.assertEqual(rc, 1, out)
            self.assertIn("RESULT: FAIL", out)
            self.assertNotIn("RESULT: PASS", out)

    def test_a_case_that_did_not_run_is_exit_1_not_a_pass(self):
        self.canned(skip=["S7.4"])
        rc, out = self.run_o4()
        if self.prerequisites_present(out):
            self.assertEqual(rc, 1, out)
            self.assertIn("case did not run: S7.4", out)

    def test_a_log_without_the_inner_done_line_is_exit_1(self):
        self.canned(done=False)
        rc, out = self.run_o4()
        if self.prerequisites_present(out):
            self.assertEqual(rc, 1, out)

    def test_an_incomplete_line_from_the_container_is_exit_2(self):
        self.canned(skip=expected_cases(), extra=["INCOMPLETE tool missing inside the harness container: ssh"], done=False)
        rc, out = self.run_o4()
        if self.prerequisites_present(out):
            self.assertEqual(rc, 2, out)
            self.assertIn("RESULT: INCOMPLETE", out)
            self.assertIn("tool missing inside the harness container: ssh", out)

    def verdict(self, **env):
        rc, out = self.run_o4(**env)
        return (rc, out) if self.prerequisites_present(out) else (None, out)

    def test_nonzero_container_exit_status_is_a_fail_even_if_every_case_passed(self):
        self.canned()
        rc, out = self.verdict(FAKE_RC="1")
        if rc is not None:
            self.assertEqual(rc, 1, out)
            self.assertIn("container exit 1", out)

    def test_a_later_pass_does_not_overwrite_an_earlier_fail_of_the_same_case(self):
        first = expected_cases()[0]
        self.canned(extra=[f"CASE {first} PASS again"], fail=[first], counts=None)
        rc, out = self.verdict()
        if rc is not None:
            self.assertEqual(rc, 1, out)
            self.assertIn(f"duplicate verdicts for: {first}", out)

    def test_a_duplicate_pass_and_an_unexpected_case_are_fails(self):
        first = expected_cases()[0]
        self.canned(extra=[f"CASE {first} PASS twice"])
        rc, out = self.verdict()
        if rc is not None:
            self.assertEqual(rc, 1, out)
        self.canned(extra=["CASE Z9 PASS not in the list"])
        rc, out = self.verdict()
        if rc is not None:
            self.assertEqual(rc, 1, out)
            self.assertIn("unexpected cases reported: Z9", out)

    def test_completion_counts_must_match_the_case_lines(self):
        self.canned(counts=(len(expected_cases()) + 3, 0))
        rc, out = self.verdict()
        if rc is not None:
            self.assertEqual(rc, 1, out)
            self.assertIn("do not match the case lines", out)

    def test_the_completion_line_must_be_last(self):
        self.canned(after_done=["CASE I0 PASS trailing"])
        rc, out = self.verdict()
        if rc is not None:
            self.assertEqual(rc, 1, out)

    def test_run_never_pulls_and_has_no_privileges(self):
        self.canned()
        rc, out = self.verdict()
        if rc is not None:
            args = self.args.read_text().split("\n")
            self.assertIn("--pull=never", args)
            self.assertIn("--network", args)
            self.assertEqual(args[args.index("--network") + 1], "none")
            self.assertIn("--read-only", args)
            self.assertNotIn("--privileged", args)
            self.assertFalse([a for a in args if "docker.sock" in a])

    def test_a_container_that_cannot_be_removed_is_a_fail(self):
        self.canned()
        rc, out = self.verdict(FAKE_PS_ID="deadbeef", FAKE_RM_RC="1")
        if rc is not None:
            self.assertEqual(rc, 1, out)
            self.assertIn("docker rm -f", out)

    def test_a_failing_cleanup_query_is_a_fail_not_a_pass(self):
        self.canned()
        rc, out = self.verdict(FAKE_PS_FAIL="1")
        if rc is not None:
            self.assertEqual(rc, 1, out)
            self.assertIn("cannot query docker", out)

    def test_an_explicit_case_failure_outranks_a_later_incomplete_line(self):
        first = expected_cases()[0]
        self.canned(skip=expected_cases()[1:], fail=[first], extra=["INCOMPLETE tool missing inside the harness container: od"], done=False)
        rc, out = self.verdict()
        if rc is not None:
            self.assertEqual(rc, 1, out)
            self.assertIn("RESULT: FAIL", out)
            self.assertIn("MISSING tool missing inside the harness container: od", out)
            self.assertNotIn("RESULT: INCOMPLETE", out)

    def test_missing_docker_is_incomplete_and_named(self):
        env = {"PATH": "/nonexistent", "TMPDIR": self.tmp.name}
        r = subprocess.run(["/usr/bin/bash", str(RUN_O4)], capture_output=True, text=True, env=env, timeout=60)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 2, out)
        self.assertIn("MISSING docker not found on PATH", out)
        self.assertIn("RESULT: INCOMPLETE", out)
        self.assertNotIn("RESULT: PASS", out)

    def test_a_missing_local_image_is_incomplete_and_the_harness_does_not_pull(self):
        # fake docker: daemon reachable, but "image inspect" fails
        fake = self.bin / "docker"
        fake.write_text('#!/bin/sh\ncase "$1" in\n  image) exit 1;;\n  pull|run|build) echo "UNEXPECTED $1" >&2; exit 99;;\n  *) exit 0;;\nesac\n')
        rc, out = self.run_o4(O4_IMAGE="local-image-that-does-not-exist:0")
        self.assertEqual(rc, 2, out)
        self.assertIn("not present locally", out)
        self.assertNotIn("UNEXPECTED", out)


if __name__ == "__main__":
    unittest.main()
