import contextlib
import io
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from lab_agent import cli, config, manifest, mcp
from tests import fixtures
from tests.test_inventory_manifest import EVIDENCE, load_inventory


class CliTests(unittest.TestCase):
    """The routine CLI end to end on files (no API: discover is covered by inventory tests)."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)
        self.env = mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)})
        self.env.start()
        inv, _ = load_inventory()
        self.inv = self.dir / "inventory.json"
        self.inv.write_text(json.dumps(inv))
        (self.dir / "overrides.json").write_text(json.dumps(EVIDENCE))

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_classify_reports_counts_and_range_conflict(self):
        code, out, _ = self.run_cli("classify", "--inventory", str(self.inv), "--overrides",
                                    str(self.dir / "overrides.json"), "--out", str(self.dir / "cls.json"))
        self.assertEqual(code, 1)  # the fixture has a backup of VMID 9150 inside 9100-9199
        self.assertIn("REMOVE_CANDIDATE=2", out)
        self.assertIn("VMID range conflict", out)
        self.assertEqual((self.dir / "cls.json").stat().st_mode & 0o777, 0o600)

    def test_manifest_build_check_hash_dry_run(self):
        self.run_cli("classify", "--inventory", str(self.inv), "--overrides", str(self.dir / "overrides.json"),
                     "--out", str(self.dir / "cls.json"))
        m = str(self.dir / "m.json")
        # L1B round 3: build and check recompute the classification from the settings, the inventory
        # and the overrides (X1-a), so they are given the overrides the classification was made with.
        ov = str(self.dir / "overrides.json")
        self.assertEqual(self.run_cli("manifest", "build", "--inventory", str(self.inv), "--classification",
                                      str(self.dir / "cls.json"), "--overrides", ov, "--out", m)[0], 0)
        self.assertEqual(self.run_cli("manifest", "check", m, "--inventory", str(self.inv),
                                      "--classification", str(self.dir / "cls.json"), "--overrides", ov)[0], 0)
        code, out, _ = self.run_cli("manifest", "hash", m)
        self.assertEqual(out.strip(), manifest.manifest_hash(manifest.load(m)))
        code, out, _ = self.run_cli("manifest", "dry-run", m)
        self.assertIn("vm/105", out)

    def test_baseline_save_and_verify(self):
        b = str(self.dir / "baseline.json")
        self.assertEqual(self.run_cli("baseline", "save", "--inventory", str(self.inv), "--out", b)[0], 0)
        code, out, _ = self.run_cli("baseline", "verify", "--baseline", b, "--inventory", str(self.inv))
        self.assertEqual((code, out.strip()), (0, "baseline: no drift"))

    def test_sanitize_refuses_unclean_output_and_scan_reports(self):
        raw = self.dir / "raw.txt"
        raw.write_text(f"node {fixtures.NODE} at 192.0.2.10 key -----BEGIN OPENSSH PRIVATE KEY-----\n"
                       "AAAAAAAAAAAAAAAAAAAAAAAA\n-----END OPENSSH PRIVATE KEY-----\n")
        clean = self.dir / "clean.txt"
        self.assertEqual(self.run_cli("sanitize", str(raw), str(clean))[0], 0)
        text = clean.read_text()
        self.assertNotIn(fixtures.NODE, text)
        self.assertNotIn("AAAAAAAA", text)
        self.assertEqual(self.run_cli("scan", str(clean))[0], 0)
        self.assertEqual(self.run_cli("scan", str(raw))[0], 1)

    def test_errors_are_reported_not_raised(self):
        code, _, err = self.run_cli("manifest", "dry-run", str(self.inv))  # not a manifest
        self.assertEqual(code, 2)
        self.assertIn("lab-agent:", err)


class McpLaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.cfg = fixtures.make_lab(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_server_env(self):
        env = mcp.server_env(self.cfg, {"PATH": "/usr/bin", "SSH_AUTH_SOCK": "/x", "AWS_SECRET": "y"})
        self.assertEqual(env["PROXMOX_USER"], "corelab-agent@pve")
        self.assertEqual(env["PROXMOX_TOKEN_NAME"], "lab")
        self.assertEqual(env["PROXMOX_TOKEN_VALUE"], self.cfg.token_secret())
        self.assertTrue(env["PROXMOX_CA_BUNDLE"].endswith("ca.pem"))
        self.assertEqual(env["PROXMOX_TOOLSETS"], mcp.TOOLSETS)
        self.assertEqual(env["PROXMOX_PROTECTED_VMIDS"], "100-9099,9200-109199")
        self.assertNotIn("PROXMOX_VERIFY_SSL", env)
        self.assertNotIn("SSH_AUTH_SOCK", env)
        self.assertNotIn("AWS_SECRET", env)

    def test_missing_ca_refused(self):
        (Path(self.tmp.name) / "ca.pem").unlink()
        with self.assertRaisesRegex(config.ConfigError, "PVE_CA_FILE"):
            mcp.server_env(self.cfg, {})

    def test_launch_refuses_without_pinned_install(self):
        with self.assertRaisesRegex(config.ConfigError, "not installed"):
            mcp.launch(self.cfg)


if __name__ == "__main__":
    unittest.main()
