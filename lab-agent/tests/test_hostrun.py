import io
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from lab_agent import hostrun, manifest
from lab_agent.config import ConfigError
from tests import fixtures
from tests.test_inventory_manifest import EVIDENCE, classes, load_inventory

STUBS = Path(__file__).resolve().parent / "stubs"
NO_AGENT_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "SSH_AUTH_SOCK": "/tmp/agent.sock"}


class FakeProc:
    def __init__(self, output: bytes, code: int = 0):
        self.stdin = io.BytesIO()
        self.stdin.close = lambda: None  # keep the buffer readable after close()
        self.stdout = io.BytesIO(output)
        self.code = code

    def wait(self):
        return self.code


class Recorder:
    def __init__(self, output=b"", code=0):
        self.calls = []
        self.output, self.code = output, code
        self.proc = None

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        self.proc = FakeProc(self.output, self.code)
        return self.proc


def encrypted(_argv, **_kw):
    return subprocess.CompletedProcess(_argv, 1)  # ssh-keygen -y -P '' fails: key is encrypted


class HostRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)
        (self.dir / "root_key").write_text("placeholder")
        os.chmod(self.dir / "root_key", 0o600)
        (self.dir / "snip_key.pub").write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBTESTKEYONLYxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx test\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_action(self, action, answer, *, popen=None, env=None, ancestors=(), tty=True, **kw):
        out = io.StringIO()
        code = hostrun.run(action, self.cfg, stdin=io.StringIO(answer), stdout=out,
                           env=NO_AGENT_ENV if env is None else env, ancestors=ancestors,
                           is_tty=lambda: tty, runner=encrypted, popen=popen or Recorder(),
                           addr_check=lambda _addr: None, **kw)
        return code, out.getvalue()

    # -- rendering ---------------------------------------------------------------------
    def test_every_action_renders_to_valid_bash(self):
        inv, _ = load_inventory()
        m = manifest.build(inv, classes(inv, EVIDENCE))
        for name in hostrun.ACTIONS:
            extra = {"inventory": inv, "overrides": EVIDENCE} if name == "apply-manifest" else {}
            script = hostrun.render(name, self.cfg, m if name == "apply-manifest" else None, **extra)
            self.assertTrue(script.startswith("set -euo pipefail\n"), name)
            proc = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, f"{name}: {proc.stderr}")

    def test_parameters_are_quoted(self):
        # L1B (HA-P), deliberate change: a bridge name with shell syntax is now refused before
        # anything is rendered. Quoting stays as the second line of defence, so this test takes
        # the type check away (patched) to show the quoting still holds on its own.
        cfg = fixtures.make_lab(self.dir, PVE_BRIDGE="vmbr0'; reboot; '")
        with self.assertRaises(ConfigError):
            hostrun.render("prepare", cfg)
        with mock.patch.dict(hostrun._PARAM_CHECKS, {"PVE_BRIDGE": lambda c: c.get("PVE_BRIDGE")}):
            script = hostrun.render("prepare", cfg)
        line = next(l for l in script.splitlines() if l.startswith("export CL_BRIDGE="))
        value = subprocess.run(["bash", "-c", line + '\nprintf %s "$CL_BRIDGE"'], capture_output=True, text=True)
        self.assertEqual(value.stdout, "vmbr0'; reboot; '")

    def test_prepare_embeds_writer_and_validates_pubkey(self):
        script = hostrun.render("prepare", self.cfg)
        self.assertIn("cl_file_snippet_writer()", script)
        self.assertIn("corelab-snippet-put — forced-command snippet writer", script)
        (self.dir / "snip_key.pub").write_text("ssh-rsa AAAA bad\n")
        with self.assertRaisesRegex(hostrun.HostRunError, "public key"):
            hostrun.render("prepare", self.cfg)

    def test_unknown_action_and_stray_manifest_refused(self):
        with self.assertRaises(hostrun.HostRunError):
            hostrun.render("rm-rf", self.cfg)
        with self.assertRaises(hostrun.HostRunError):
            hostrun.render("preflight", self.cfg, {"items": []})

    # -- approval ----------------------------------------------------------------------
    def test_wrong_confirmation_sends_nothing(self):
        popen = Recorder()
        code, out = self.run_action("preflight", "yes\n", popen=popen)
        self.assertEqual(code, 1)
        self.assertEqual(popen.calls, [])
        self.assertIn("aborted", out)

    def test_correct_confirmation_runs_exact_script_with_safe_ssh(self):
        popen = Recorder(b"[corelab] preflight done\n")
        sha = hostrun.script_hash(hostrun.render("preflight", self.cfg))
        code, out = self.run_action("preflight", sha[:8] + "\n", popen=popen)
        self.assertEqual(code, 0)
        argv, kw = popen.calls[0]
        for opt in ("IdentitiesOnly=yes", "IdentityAgent=none", "ControlMaster=no", "ControlPath=none",
                    "ForwardAgent=no", "StrictHostKeyChecking=yes"):
            self.assertIn(opt, argv)
        self.assertNotIn("SSH_AUTH_SOCK", kw["env"])
        self.assertEqual(popen.proc.stdin.getvalue().decode(), hostrun.render("preflight", self.cfg))
        log = next((self.dir / "state" / "runs").iterdir())
        self.assertEqual(log.stat().st_mode & 0o777, 0o600)

    def test_review_shows_first_unchanged_and_changed(self):
        state = self.cfg.state_dir()
        script = hostrun.render("preflight", self.cfg)
        self.assertIn("first run", hostrun.review_text("preflight", script, state))
        hostrun.record_approval(state, "preflight", script, now="2026-11-16T00:00:00+00:00")
        self.assertIn("unchanged since", hostrun.review_text("preflight", script, state))
        changed = script + "echo extra\n"
        text = hostrun.review_text("preflight", changed, state)
        self.assertIn("CHANGED", text)
        self.assertIn("+echo extra", text)
        self.assertEqual((state / "approvals.jsonl").stat().st_mode & 0o777, 0o600)

    # -- guards ------------------------------------------------------------------------
    def test_refuses_inside_claude_code_or_without_tty(self):
        with self.assertRaisesRegex(hostrun.HostRunError, "CLAUDECODE"):
            self.run_action("preflight", "x", env=dict(NO_AGENT_ENV, CLAUDECODE="1"))
        with self.assertRaisesRegex(hostrun.HostRunError, "parent process"):
            self.run_action("preflight", "x", ancestors=("bash", "claude"))
        with self.assertRaisesRegex(hostrun.HostRunError, "TTY"):
            self.run_action("preflight", "x", tty=False)

    def test_unencrypted_root_key_refused(self):
        if not shutil.which("ssh-keygen"):
            self.skipTest("ssh-keygen not installed")
        key = self.dir / "k_plain"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
        with self.assertRaisesRegex(hostrun.HostRunError, "NOT passphrase-protected"):
            hostrun.check_root_key(key)
        key2 = self.dir / "k_enc"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "test-passphrase", "-f", str(key2)], check=True)
        hostrun.check_root_key(key2)  # no exception
        os.chmod(key2, 0o644)
        with self.assertRaisesRegex(hostrun.HostRunError, "600"):
            hostrun.check_root_key(key2)

    def test_manifest_hash_mismatch_refused_before_anything(self):
        inv, _ = load_inventory()
        m = manifest.build(inv, classes(inv, EVIDENCE))
        path = self.dir / "m.json"
        path.write_text(json.dumps(m))
        popen = Recorder()
        with self.assertRaisesRegex(hostrun.HostRunError, "manifest hash"):
            self.run_action("apply-manifest", "x", popen=popen, manifest_path=str(path), expected_sha="0" * 64)
        self.assertEqual(popen.calls, [])

    # -- output ------------------------------------------------------------------------
    def test_token_secret_goes_to_file_only(self):
        secret = "11111111-2222-3333-4444-555555555555"
        popen = Recorder(f"[corelab] user created\nCORELAB_TOKEN_SECRET={secret}\n[corelab] done\n".encode())
        sha = hostrun.script_hash(hostrun.render("bootstrap", self.cfg))
        (self.dir / "token").unlink()
        code, out = self.run_action("bootstrap", sha[:8] + "\n", popen=popen)
        self.assertEqual(code, 0)
        self.assertNotIn(secret, out)
        self.assertEqual((self.dir / "token").read_text().strip(), secret)
        self.assertEqual((self.dir / "token").stat().st_mode & 0o777, 0o600)
        for log in (self.dir / "state" / "runs").iterdir():
            self.assertNotIn(secret, log.read_text())

    def test_existing_token_file_refused(self):
        with self.assertRaisesRegex(hostrun.HostRunError, "already exists"):
            self.run_action("bootstrap", "x")

    def test_file_output_is_private(self):
        popen = Recorder(b"\x1f\x8bbinary-tar")
        sha = hostrun.script_hash(hostrun.render("backup-config", self.cfg))
        code, out = self.run_action("backup-config", sha[:8] + "\n", popen=popen)
        self.assertEqual(code, 0)
        files = list((self.dir / "state" / "host-backup").iterdir())
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_bytes(), b"\x1f\x8bbinary-tar")
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)


class BootstrapScriptTests(unittest.TestCase):
    """The bootstrap action against stub pveum: token printed once, never reused."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def run_bootstrap(self, state):
        (self.dir / "s.json").write_text(json.dumps(state))
        (self.dir / "c.log").write_text("")
        env = {"PATH": f"{STUBS}:/usr/bin:/bin", "STUB_STATE": str(self.dir / "s.json"),
               "STUB_LOG": str(self.dir / "c.log")}
        return subprocess.run(["bash", "-s"], input=hostrun.render("bootstrap", self.cfg), text=True,
                              capture_output=True, env=env)

    def test_creates_user_token_and_read_only_acl(self):
        proc = self.run_bootstrap({"users": [], "tokens": {}})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.count("CORELAB_TOKEN_SECRET="), 1)
        calls = [json.loads(l) for l in (self.dir / "c.log").read_text().splitlines()]
        acls = [c for c in calls if c[1:3] == ["acl", "modify"]]
        self.assertEqual({tuple(c[3:]) for c in acls},
                         {("/", "--users", "corelab-agent@pve", "--roles", "PVEAuditor"),
                          ("/", "--tokens", "corelab-agent@pve!lab", "--roles", "PVEAuditor")})
        add = next(c for c in calls if c[1:4] == ["user", "token", "add"])
        self.assertIn("--privsep", add)
        self.assertEqual(add[add.index("--privsep") + 1], "1")

    def test_existing_token_is_not_replaced(self):
        proc = self.run_bootstrap({"users": [{"userid": "corelab-agent@pve"}],
                                   "tokens": {"corelab-agent@pve": [{"tokenid": "lab"}]}})
        self.assertEqual(proc.returncode, 3)
        self.assertNotIn("CORELAB_TOKEN_SECRET", proc.stdout)


if __name__ == "__main__":
    unittest.main()
