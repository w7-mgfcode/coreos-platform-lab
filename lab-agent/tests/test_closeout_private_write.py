"""Finding 5: write_private refuses unsafe directories and destinations and never leaves a
temporary file behind. Temporary directories only."""

import io
import os
import unittest
from pathlib import Path
from unittest import mock

from lab_agent import hostrun
from tests import fixtures
from tests.test_hostrun import NO_AGENT_ENV, Recorder, encrypted


class WritePrivateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.out = self.dir / "out"
        self.out.mkdir(mode=0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def leftovers(self, d=None):
        return sorted(p.name for p in (d or self.out).iterdir() if p.name.endswith(".tmp"))

    # -- the parent directory ------------------------------------------------------------
    def test_missing_parent_is_created_private(self):
        target = self.dir / "new" / "f"
        hostrun.write_private(target, b"data")
        self.assertEqual((self.dir / "new").stat().st_mode & 0o777, 0o700)
        self.assertEqual(target.read_bytes(), b"data")
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_symlinked_parent_refused(self):
        link = self.dir / "link"
        link.symlink_to(self.out)
        with self.assertRaisesRegex(hostrun.HostRunError, "symlink"):
            hostrun.write_private(link / "f", b"data")
        self.assertEqual(list(self.out.iterdir()), [])

    def test_group_or_world_accessible_parent_refused(self):
        for mode in (0o750, 0o705, 0o777):
            with self.subTest(mode=oct(mode)):
                os.chmod(self.out, mode)
                with self.assertRaisesRegex(hostrun.HostRunError, "expected 700"):
                    hostrun.write_private(self.out / "f", b"data")
                self.assertEqual(list(self.out.iterdir()), [])
        os.chmod(self.out, 0o700)

    def test_parent_owned_by_another_user_refused(self):
        real = os.getuid()
        with mock.patch.object(hostrun.os, "getuid", return_value=real + 1):
            with self.assertRaisesRegex(hostrun.HostRunError, "owned by another user"):
                hostrun.write_private(self.out / "f", b"data")
        self.assertEqual(list(self.out.iterdir()), [])

    def test_parent_that_is_a_file_refused(self):
        (self.dir / "plain").write_text("x")
        with self.assertRaisesRegex(hostrun.HostRunError, "not a directory"):
            hostrun.write_private(self.dir / "plain" / "f", b"data")

    # -- the temporary file --------------------------------------------------------------
    def test_temporary_file_is_unpredictable_exclusive_and_nofollow(self):
        # L1B (F-G): the writes go through a directory descriptor, so the temporary file is
        # opened by name relative to that descriptor. The spy records which directory the
        # descriptor is (same inode as ``out``: same directory, so the rename is atomic) and
        # ignores the opens of the directory itself.
        real_open, seen = os.open, []
        out_ino = os.stat(self.out).st_ino

        def spy(path, flags, mode=0o777, *a, dir_fd=None, **kw):
            if not flags & os.O_DIRECTORY:
                self.assertIsNotNone(dir_fd)
                seen.append((Path(path), flags, mode, os.fstat(dir_fd).st_ino))
            return real_open(path, flags, mode, *a, dir_fd=dir_fd, **kw)

        with mock.patch.object(hostrun.os, "open", side_effect=spy):
            hostrun.write_private(self.out / "f", b"one")
            hostrun.write_private(self.out / "f", b"two")
        self.assertEqual(len(seen), 2)
        for path, flags, mode, ino in seen:
            self.assertEqual(ino, out_ino)  # same directory, so the rename is atomic
            self.assertEqual(path.parent, Path("."))  # a bare name, never a path that could be redirected
            self.assertNotEqual(path.name, "f.tmp")
            self.assertRegex(path.name, r"^\.f\.[0-9a-f]{16}\.tmp$")
            for flag in (os.O_CREAT, os.O_EXCL, os.O_NOFOLLOW, os.O_WRONLY):
                self.assertTrue(flags & flag, hex(flag))
            self.assertFalse(flags & os.O_TRUNC)
            self.assertEqual(mode, 0o600)
        self.assertNotEqual(seen[0][0], seen[1][0])
        self.assertEqual((self.out / "f").read_bytes(), b"two")
        self.assertEqual(self.leftovers(), [])

    def test_mode_is_600_whatever_the_umask(self):
        old = os.umask(0)
        try:
            hostrun.write_private(self.out / "f", b"data")
        finally:
            os.umask(old)
        self.assertEqual((self.out / "f").stat().st_mode & 0o777, 0o600)

    def test_planted_old_style_tmp_symlink_is_ignored(self):
        victim = self.dir / "victim"
        victim.write_bytes(b"keep")
        (self.out / "f.tmp").symlink_to(victim)
        hostrun.write_private(self.out / "f", b"data")
        self.assertEqual(victim.read_bytes(), b"keep")
        self.assertEqual((self.out / "f").read_bytes(), b"data")

    def test_temporary_file_removed_on_failure(self):
        with mock.patch.object(hostrun.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                hostrun.write_private(self.out / "f", b"data")
        self.assertEqual(list(self.out.iterdir()), [])
        with mock.patch.object(hostrun.os, "fsync", side_effect=OSError("io error")):
            with self.assertRaises(OSError):
                hostrun.write_private(self.out / "g", b"data", exclusive=True)
        self.assertEqual(list(self.out.iterdir()), [])
        # No hard links: the fallback create at the destination fails while writing. L1B (F-G),
        # deliberate change: the data is no longer dropped. The half-written destination is
        # removed, the complete temporary file stays (mode 600) and the error names it.
        with mock.patch.object(hostrun.os, "link", side_effect=OSError("no hard links")), \
                mock.patch.object(hostrun.os, "fsync", side_effect=[None, OSError("io error")]):
            with self.assertRaisesRegex(hostrun.HostRunError, "is kept in"):
                hostrun.write_private(self.out / "h", b"data", exclusive=True)
        kept = [p for p in self.out.iterdir()]
        self.assertEqual(len(kept), 1)
        self.assertRegex(kept[0].name, r"^\.h\.[0-9a-f]{16}\.tmp$")
        self.assertEqual(kept[0].read_bytes(), b"data")
        self.assertEqual(kept[0].stat().st_mode & 0o777, 0o600)

    # -- the destination -----------------------------------------------------------------
    def test_symlink_at_destination_is_not_followed(self):
        victim = self.dir / "victim"
        victim.write_bytes(b"keep")
        (self.out / "f").symlink_to(victim)
        with self.assertRaisesRegex(hostrun.HostRunError, "not a regular file"):
            hostrun.write_private(self.out / "f", b"data")
        self.assertEqual(victim.read_bytes(), b"keep")
        self.assertTrue((self.out / "f").is_symlink())
        self.assertEqual(self.leftovers(), [])

    def test_regular_file_is_replaced_unless_exclusive(self):
        (self.out / "f").write_bytes(b"old")
        hostrun.write_private(self.out / "f", b"new")
        self.assertEqual((self.out / "f").read_bytes(), b"new")
        with self.assertRaisesRegex(hostrun.HostRunError, "already exists"):
            hostrun.write_private(self.out / "f", b"newer", exclusive=True)
        self.assertEqual((self.out / "f").read_bytes(), b"new")

    def test_exclusive_refuses_dangling_symlink(self):
        (self.out / "t").symlink_to(self.dir / "nowhere")
        with self.assertRaisesRegex(hostrun.HostRunError, "already exists"):
            hostrun.write_private(self.out / "t", b"secret", exclusive=True)
        self.assertFalse((self.dir / "nowhere").exists())

    def test_exclusive_loses_a_race_without_overwriting(self):
        # Something appears at the destination between the check and the link.
        target = self.out / "t"
        real_link = os.link

        def racing_link(src, dst, *, src_dir_fd=None, dst_dir_fd=None, **kw):
            # L1B: link takes directory descriptors; the rival appears in the same directory.
            rival = os.open(dst, os.O_WRONLY | os.O_CREAT, 0o644, dir_fd=dst_dir_fd)
            os.write(rival, b"theirs")
            os.close(rival)
            return real_link(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd, **kw)

        with mock.patch.object(hostrun.os, "link", side_effect=racing_link):
            with self.assertRaisesRegex(hostrun.HostRunError, "already exists"):
                hostrun.write_private(target, b"secret", exclusive=True)
        self.assertEqual(target.read_bytes(), b"theirs")
        self.assertEqual(self.leftovers(), [])


class CallerTests(unittest.TestCase):
    """The two callers: the token secret and the file output of host-run."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)
        (self.dir / "root_key").write_text("placeholder")
        os.chmod(self.dir / "root_key", 0o600)

    def tearDown(self):
        self.tmp.cleanup()

    def run_action(self, action, answer, popen):
        return hostrun.run(action, self.cfg, stdin=io.StringIO(answer), stdout=io.StringIO(), env=NO_AGENT_ENV,
                           ancestors=(), is_tty=lambda: True, runner=encrypted, popen=popen)

    def test_token_path_dangling_symlink_refused_as_already_exists(self):
        token = self.dir / "token"
        token.unlink()
        token.symlink_to(self.dir / "elsewhere")
        popen = Recorder()
        with self.assertRaisesRegex(hostrun.HostRunError, "already exists"):
            self.run_action("bootstrap", "x\n", popen)
        self.assertEqual(popen.calls, [])
        self.assertFalse((self.dir / "elsewhere").exists())

    def test_token_written_exclusively(self):
        token = self.dir / "t2"
        token.write_text("existing\n")
        stream = io.BytesIO(b"CORELAB_TOKEN_SECRET=11111111-2222-3333-4444-555555555555\n")
        with self.assertRaisesRegex(hostrun.HostRunError, "already exists"):
            hostrun.handle_output(stream, "token", io.StringIO(), io.StringIO(), token_file=token)
        self.assertEqual(token.read_text(), "existing\n")

    def test_file_output_refuses_non_private_directory(self):
        # L1B (W-4): a state directory that is not mode 700 is refused now, so it is created
        # private here and only the host-backup directory is the loose one.
        (self.dir / "state").mkdir(mode=0o700)
        backup = self.dir / "state" / "host-backup"
        backup.mkdir(mode=0o700)
        os.chmod(backup, 0o755)
        sha = hostrun.script_hash(hostrun.render("backup-config", self.cfg))
        popen = Recorder(b"\x1f\x8bdata")
        with self.assertRaisesRegex(hostrun.HostRunError, "expected 700"):
            self.run_action("backup-config", sha[:8] + "\n", popen)
        self.assertEqual(popen.calls, [])  # refused before the host was contacted
        self.assertEqual(list(backup.iterdir()), [])

    def test_token_directory_checked_before_the_host_is_contacted(self):
        tokdir = self.dir / "cfgdir"
        tokdir.mkdir(mode=0o700)
        os.chmod(tokdir, 0o755)  # what a plain mkdir under umask 022 gives
        cfg = fixtures.make_lab(self.dir, PVE_TOKEN_FILE=str(tokdir / "token"))
        popen = Recorder(b"CORELAB_TOKEN_SECRET=11111111-2222-3333-4444-555555555555\n")
        sha = hostrun.script_hash(hostrun.render("bootstrap", cfg))
        with self.assertRaisesRegex(hostrun.HostRunError, "expected 700"):
            hostrun.run("bootstrap", cfg, stdin=io.StringIO(sha[:8] + "\n"), stdout=io.StringIO(), env=NO_AGENT_ENV,
                        ancestors=(), is_tty=lambda: True, runner=encrypted, popen=popen)
        self.assertEqual(popen.calls, [])
        self.assertEqual(list(tokdir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
