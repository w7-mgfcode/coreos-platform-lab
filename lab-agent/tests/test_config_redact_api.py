import inspect
import json
import os
import ssl
import unittest
from pathlib import Path

from lab_agent import config, pveapi, redact
from tests import fixtures


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_strips_quotes_and_comments(self):
        values = config.parse_env_text("# comment\n\nPVE_NODE='n1'\nPVE_PORT=\"8006\"\n")
        self.assertEqual(values, {"PVE_NODE": "n1", "PVE_PORT": "8006"})

    def test_unknown_key_and_bad_line_rejected(self):
        with self.assertRaisesRegex(config.ConfigError, "unknown key"):
            config.parse_env_text("PVE_NOPE=1\n")
        with self.assertRaisesRegex(config.ConfigError, "KEY=VALUE"):
            config.parse_env_text("export PVE_NODE=n1\n")

    def test_value_is_never_executed(self):
        values = config.parse_env_text("PVE_NODE=$(touch /tmp/should-not-exist)\n")
        self.assertEqual(values["PVE_NODE"], "$(touch /tmp/should-not-exist)")

    def test_env_file_must_be_private(self):
        cfg = fixtures.make_lab(self.dir)
        os.chmod(cfg.source, 0o644)
        with self.assertRaisesRegex(config.ConfigError, "expected 600"):
            config.load(cfg.source)

    def test_token_secret_needs_private_file_and_is_not_in_repr(self):
        cfg = fixtures.make_lab(self.dir)
        secret = cfg.token_secret()
        self.assertTrue(secret)
        self.assertNotIn(secret, repr(cfg))
        self.assertNotIn(secret, json.dumps(cfg.redacted()))
        os.chmod(self.dir / "token", 0o640)
        fresh = config.load(cfg.source)
        with self.assertRaisesRegex(config.ConfigError, "expected 600"):
            fresh.token_secret()

    def test_vmid_range_and_token_id_validated(self):
        cfg = fixtures.make_lab(self.dir, PVE_VMID_RANGE="9199-9100")
        with self.assertRaises(config.ConfigError):
            cfg.vmid_range()
        cfg = fixtures.make_lab(self.dir, PVE_TOKEN_ID="no-bang@pve")
        with self.assertRaises(config.ConfigError):
            cfg.token_id()

    def test_defaults(self):
        cfg = fixtures.make_lab(self.dir)
        self.assertEqual(cfg.get("PVE_POOL"), "corelab")
        self.assertEqual(cfg.get("PVE_PORT"), "8006")


class RedactTests(unittest.TestCase):
    def test_redact_secrets(self):
        text = ("Authorization: PVEAPIToken=u@pve!lab=11111111-2222-3333-4444-555555555555\n"
                "curl -H 'PVEAPIToken=u@pve!lab=abc'\n"
                '{"value": "11111111-2222-3333-4444-555555555555"}\n'
                "CORELAB_TOKEN_SECRET=abc\n--password hunter2\n"
                "-----BEGIN OPENSSH PRIVATE KEY-----\nAAAA\n-----END OPENSSH PRIVATE KEY-----\n")
        out = redact.redact(text)
        for leaked in ("abc", "hunter2", "AAAA", "11111111-2222"):
            self.assertNotIn(leaked, out)

    def test_sanitize_maps_lab_values_and_pseudonymises(self):
        mapping = {"10.1.2.3": "${PVE_HOST}", "realnode": "${PVE_NODE}"}
        text = "host 10.1.2.3 node realnode peers 172.16.0.5 172.16.0.5 172.16.0.6 doc 192.0.2.7 mac AA:BB:CC:DD:EE:FF"
        out = redact.sanitize(text, mapping)
        self.assertIn("${PVE_HOST}", out)
        self.assertIn("${PVE_NODE}", out)
        self.assertEqual(out.count("<ipv4-1>"), 2)
        self.assertIn("<ipv4-2>", out)
        self.assertIn("192.0.2.7", out)  # documentation range stays
        self.assertIn("<mac-1>", out)
        self.assertEqual(redact.scan(out, mapping), [])

    def test_scan_flags_everything_unsafe(self):
        findings = redact.scan("10.0.0.9 PVEAPIToken=u@pve!lab=abcdef0123 a@b.example "
                               "11111111-2222-3333-4444-555555555555", {"realnode": "${PVE_NODE}"})
        self.assertEqual(redact.scan(r're.compile(r"PVEAPIToken=[^\s]+") "-----BEGIN PRIVATE KEY-----"'), [])
        self.assertTrue(any("IPv4" in f for f in findings))
        self.assertTrue(any("token header" in f for f in findings))
        self.assertTrue(any("mail" in f for f in findings))
        self.assertTrue(any("UUID" in f for f in findings))
        self.assertIn("lab value for ${PVE_NODE} present", redact.scan("on realnode", {"realnode": "${PVE_NODE}"}))


class ApiTests(unittest.TestCase):
    def make(self, routes):
        transport = pveapi.FakeTransport(routes)
        return pveapi.Client("192.0.2.10", 8006, "u@pve!lab", "s3cr3t", transport), transport

    def test_token_header_and_parsing(self):
        client, t = self.make({("GET", "/version"): (200, {"version": "9.1.1"})})
        self.assertEqual(client.get("/version"), {"version": "9.1.1"})
        method, url, headers, body = t.calls[0]
        self.assertEqual(headers["Authorization"], "PVEAPIToken=u@pve!lab=s3cr3t")
        self.assertTrue(url.startswith("https://192.0.2.10:8006/api2/json/version"))

    def test_permission_denied_is_distinguishable(self):
        client, _ = self.make({("PUT", "/nodes/n/qemu/1/config"): (403, "Permission check failed")})
        with self.assertRaises(pveapi.PveError) as ctx:
            client.put("/nodes/n/qemu/1/config", description="x")
        self.assertTrue(ctx.exception.permission_denied)
        self.assertNotIn("s3cr3t", str(ctx.exception))

    def test_form_body_for_writes(self):
        client, t = self.make({("POST", "/nodes/n/qemu/1/status/start"): (200, "UPID:x")})
        client.post("/nodes/n/qemu/1/status/start", timeout=5)
        self.assertEqual(t.calls[0][3], b"timeout=5")

    def test_unsafe_paths_refused(self):
        client, t = self.make({})
        for bad in ("version", "/nodes/../access", "/a/../../b"):
            with self.assertRaises(ValueError):
                client.get(bad)
        self.assertEqual(t.calls, [])

    def test_tls_cannot_be_disabled(self):
        self.assertNotIn("verify", inspect.signature(pveapi.urllib_transport).parameters)
        self.assertNotIn("insecure", inspect.getsource(pveapi).lower())
        with self.assertRaises((FileNotFoundError, ssl.SSLError, OSError)):
            pveapi.urllib_transport("/nonexistent/ca.pem")


if __name__ == "__main__":
    unittest.main()
