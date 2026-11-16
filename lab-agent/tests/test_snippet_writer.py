"""Offline tests of the forced-command snippet writer (plan § 9.5, S1–S9 equivalents).

The writer runs here as the current user with a test config. What cannot be tested
without root and sshd (the non-root identity, `restrict`, root-owned directory, S7 and S9)
is covered offline by the container harness `tests/o4/run-o4.sh` (see test_l1b_snippet_writer.py
for its contract tests) and is repeated on the real host in L4. S10 needs the lab.
"""

import json
import os
import subprocess
import unittest
from pathlib import Path

from tests import fixtures

WRITER = Path(__file__).resolve().parent.parent / "host" / "snippet-writer" / "corelab-snippet-put"
IGN = json.dumps({"ignition": {"version": "3.4.0"}, "passwd": {}}).encode()


class SnippetWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        base = Path(self.tmp.name)
        self.dir = base / "snippets"
        self.dir.mkdir(mode=0o2770)
        self.conf = base / "writer.conf"
        self.write_conf()
        self.outside = base / "outside.txt"
        self.outside.write_text("precious\n")

    def tearDown(self):
        self.tmp.cleanup()

    def write_conf(self, **extra):
        lines = [f"dir = {os.path.realpath(self.dir)}", "max_bytes = 1024"]
        lines += [f"{k} = {v}" for k, v in extra.items()]
        self.conf.write_text("\n".join(lines) + "\n")

    def call(self, command, data=b"", args=None):
        env = {"PATH": "/usr/bin:/bin", "SSH_ORIGINAL_COMMAND": command}
        argv = ["perl", str(WRITER)] + (args if args is not None else ["--config", str(self.conf)])
        return subprocess.run(argv, input=data, capture_output=True, env=env)

    def files(self):
        return sorted(p.name for p in self.dir.iterdir())

    def test_s1_valid_put_list_rm(self):
        r = self.call("put demo-1", IGN)
        self.assertEqual(r.returncode, 0, r.stderr)
        target = self.dir / "corelab-demo-1.ign"
        self.assertEqual(target.read_bytes(), IGN)
        self.assertEqual(target.stat().st_mode & 0o777, 0o644)
        self.assertEqual(target.stat().st_uid, os.getuid())
        self.assertIn(b"sha256=", r.stdout)
        self.assertEqual(self.files(), ["corelab-demo-1.ign"])  # no temp file left
        self.assertIn(b"corelab-demo-1.ign", self.call("list").stdout)
        self.assertEqual(self.call("rm demo-1").returncode, 0)
        self.assertEqual(self.files(), [])
        self.assertIn(b"ok absent", self.call("rm demo-1").stdout)  # idempotent

    def test_atomic_replace(self):
        self.assertEqual(self.call("put demo", IGN).returncode, 0)
        before = (self.dir / "corelab-demo.ign").stat().st_ino
        new = json.dumps({"ignition": {"version": "3.4.0"}, "storage": {}}).encode()
        self.assertEqual(self.call("put demo", new).returncode, 0)
        target = self.dir / "corelab-demo.ign"
        self.assertEqual(target.read_bytes(), new)
        self.assertNotEqual(target.stat().st_ino, before)  # replaced by rename, not rewritten in place
        self.assertEqual(self.files(), ["corelab-demo.ign"])

    def test_s2_bad_names_and_traversal(self):
        for cmd in ("put ../x", "put /etc/x", "put a/b", "put A", "put ", "put", "put " + "a" * 49,
                    "put -x", "put x.ign", "get x", "put x y", "rm ../../etc/passwd"):
            r = self.call(cmd, IGN)
            self.assertNotEqual(r.returncode, 0, cmd)
        self.assertEqual(self.files(), [])
        self.assertEqual(self.outside.read_text(), "precious\n")

    def test_s3_invalid_content(self):
        for data in (b"", b"not json", b"[]", json.dumps({"ignition": {}}).encode(),
                     json.dumps({"ignition": {"version": "2.2.0"}}).encode(),
                     json.dumps({"ignition": {"version": ["3.4.0"]}}).encode()):
            r = self.call("put demo", data)
            self.assertEqual(r.returncode, 3, data)
        self.assertEqual(self.files(), [])

    def test_s4_size_limit(self):
        big = json.dumps({"ignition": {"version": "3.4.0"}, "pad": "x" * 2000}).encode()
        self.assertEqual(self.call("put demo", big).returncode, 3)
        self.assertEqual(self.files(), [])

    def test_s5_symlink_target_refused(self):
        link = self.dir / "corelab-x.ign"
        link.symlink_to(self.outside)
        r = self.call("put x", IGN)
        self.assertEqual(r.returncode, 3)
        self.assertIn(b"symlink", r.stderr)
        self.assertEqual(self.outside.read_text(), "precious\n")
        self.assertEqual(self.call("rm x").returncode, 3)
        self.assertTrue(link.is_symlink())

    def test_hard_link_and_non_regular_targets_refused(self):
        os.link(self.outside, self.dir / "corelab-h.ign")
        self.assertEqual(self.call("put h", IGN).returncode, 3)
        self.assertEqual(self.outside.read_text(), "precious\n")
        (self.dir / "corelab-d.ign").mkdir()
        self.assertEqual(self.call("put d", IGN).returncode, 3)

    def test_foreign_owner_refused(self):
        self.assertEqual(self.call("put demo", IGN).returncode, 0)
        self.write_conf(expected_uid=os.getuid() + 12345)
        r = self.call("put demo", IGN)
        self.assertEqual(r.returncode, 3)
        self.assertIn(b"owned by another user", r.stderr)
        self.assertEqual(self.call("rm demo").returncode, 3)

    def test_directory_checks(self):
        real = self.dir
        alias = Path(self.tmp.name) / "alias"
        alias.symlink_to(real)
        self.conf.write_text(f"dir = {alias}\nmax_bytes = 1024\n")
        self.assertEqual(self.call("put demo", IGN).returncode, 3)  # symlinked directory
        self.write_conf()
        os.chmod(real, 0o2777)
        self.assertEqual(self.call("put demo", IGN).returncode, 3)  # world-writable
        os.chmod(real, 0o2770)
        self.assertEqual(self.call("put demo", IGN).returncode, 0)

    def test_s6_command_line_is_parsed_strictly(self):
        for cmd in ("put x; id", "put x && id", "put $(id)", "put x\nid", "list -a", "put x|id", "  put x"):
            r = self.call(cmd, IGN)
            self.assertEqual(r.returncode, 2, cmd)
        self.assertEqual(self.files(), [])

    def test_arguments_other_than_test_config_refused(self):
        r = self.call("list", args=["--evil"])
        self.assertEqual(r.returncode, 2)

    def test_output_is_not_executable(self):
        self.call("put demo", IGN)
        mode = (self.dir / "corelab-demo.ign").stat().st_mode
        self.assertEqual(mode & 0o111, 0)


if __name__ == "__main__":
    unittest.main()
