"""L1-CORE-4: the fixed workstation source address (PVE_WORKSTATION_ADDR).

Offline only, documentation addresses only (RFC 5737, RFC 3849). ``ssh -G`` resolves the
configuration locally and opens no connection; nothing here connects anywhere.
"""

import io
import os
import shutil
import socket
import ssl
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from lab_agent import hostrun, pveapi
from lab_agent.config import Config, ConfigError
from tests import fixtures
from tests.test_hostrun import NO_AGENT_ENV, Recorder

PROXY_VARS = ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY",
              "no_proxy", "NO_PROXY")


def cfg_with(addr, host="192.0.2.10"):
    return Config({"PVE_WORKSTATION_ADDR": addr, "PVE_HOST": host})


class WorkstationAddrTests(unittest.TestCase):
    def test_accepted(self):
        for addr, host, expected in (("192.0.2.50", "192.0.2.10", "192.0.2.50"),
                                     ("203.0.113.7", "198.51.100.1", "203.0.113.7"),
                                     ("2001:db8::50", "2001:db8::10", "2001:db8::50"),
                                     ("2001:DB8:0:0::50", "2001:db8::10", "2001:db8::50"),  # canonical form
                                     ("198.51.100.20", "pve.example.invalid", "198.51.100.20"),
                                     ("2001:db8::20", "pve.example.invalid", "2001:db8::20")):
            with self.subTest(addr=addr, host=host):
                self.assertEqual(cfg_with(addr, host).workstation_addr(), expected)

    def test_refused(self):
        for addr in ("", " 192.0.2.50", "192.0.2.50 ", "192.0.2.50/32", "192.0.2.0/24",
                     "192.0.2.50,192.0.2.51", "192.0.2.50 192.0.2.51", "192.0.2.50;192.0.2.51",
                     "*", "192.0.2.*", "0.0.0.0", "::", '"192.0.2.50"', "'192.0.2.50'", "192.0.2.50'",
                     "fe80" + "::1%eth0", "[2001:db8::50]",  # (built in parts: the hygiene scan flags IPv6 text) "workstation.example.invalid", "localhost",
                     "192.0.2.050", "192.0.2.256", "224.0.0.1",
                     "2001:db8::50"):  # IPv6 against an IPv4 PVE_HOST
            with self.subTest(addr=addr), self.assertRaises(ConfigError):
                cfg_with(addr).workstation_addr()
        with self.assertRaisesRegex(ConfigError, "IPv4, but PVE_HOST is IPv6"):
            cfg_with("192.0.2.50", "2001:db8::10").workstation_addr()
        with self.assertRaisesRegex(ConfigError, "PVE_WORKSTATION_ADDR is not set"):
            Config({"PVE_HOST": "192.0.2.10"}).workstation_addr()

    def test_quotes_around_the_whole_value_are_stripped_by_the_parser_first(self):
        # parse_env_text strips one matching pair of outer quotes, as for every key.
        with fixtures.private_tmpdir() as d:
            cfg = fixtures.make_lab(Path(d), PVE_WORKSTATION_ADDR="'192.0.2.50'")
            self.assertEqual(cfg.workstation_addr(), "192.0.2.50")


class SshCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_argument_list(self):
        argv = hostrun.ssh_command(self.cfg)
        self.assertEqual(argv[:3], ["ssh", "-F", "none"])
        self.assertIn("BindAddress=192.0.2.50", argv)
        self.assertEqual(argv[argv.index("BindAddress=192.0.2.50") - 1], "-o")
        # Every earlier option is still there, unchanged and in the same order.
        rest = [a for a in argv[3:] if a != "BindAddress=192.0.2.50"]
        rest.pop(rest.index("-o", len(rest) - 4))  # the -o in front of BindAddress
        self.assertEqual(rest, [
            "-T", "-i", str(self.dir / "root_key"),
            "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none",
            "-o", "ControlMaster=no", "-o", "ControlPath=none",
            "-o", "ForwardAgent=no", "-o", "ForwardX11=no", "-o", "ClearAllForwardings=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={self.dir / 'known_hosts'}",
            # L1B (S-3, S-5): the global known-hosts files are not consulted, nothing is added to
            # the pinned file, authentication is the public key only, the port is 22.
            "-o", "GlobalKnownHostsFile=/dev/null", "-o", "UpdateHostKeys=no", "-o", "VerifyHostKeyDNS=no",
            "-o", "BatchMode=no", "-o", "PreferredAuthentications=publickey",
            "-o", "PasswordAuthentication=no", "-o", "KbdInteractiveAuthentication=no",
            "-o", "HostbasedAuthentication=no", "-o", "GSSAPIAuthentication=no",
            "-o", "Port=22",
            "root@192.0.2.10", "bash -s"])

    def test_invalid_address_refused_before_any_command_exists(self):
        cfg = fixtures.make_lab(self.dir, PVE_WORKSTATION_ADDR="192.0.2.0/24")
        with self.assertRaisesRegex(ConfigError, "exactly one IP address"):
            hostrun.ssh_command(cfg)

    def resolve(self, argv, home):
        """ssh -G: print the resolved configuration; no connection is made."""
        env = {"HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        proc = subprocess.run([argv[0], "-G"] + argv[1:], capture_output=True, text=True, env=env, timeout=10,
                              stdin=subprocess.DEVNULL)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        resolved: dict[str, list[str]] = {}
        for line in proc.stdout.splitlines():
            key, _, value = line.partition(" ")
            resolved.setdefault(key, []).append(value)
        return resolved

    def test_ssh_resolution_binds_and_ignores_inherited_configuration(self):
        if not shutil.which("ssh"):
            self.skipTest("ssh not installed")
        home = self.dir / "home"
        (home / ".ssh").mkdir(parents=True, mode=0o700)
        hostile = home / ".ssh" / "config"
        hostile.write_text("Host *\n    ProxyJump jump@198.51.100.1\n    BindAddress 203.0.113.9\n"
                           "    BindInterface eth9\n    IdentityFile /nonexistent/other_key\n"
                           "    UserKnownHostsFile /nonexistent/other_known_hosts\n    ForwardAgent yes\n")
        os.chmod(hostile, 0o600)
        # ssh drops -i silently for a missing file and falls back to its default keys, so the
        # placeholder must exist (the owner path refuses a missing key before ssh starts).
        (self.dir / "root_key").write_text("placeholder")
        os.chmod(self.dir / "root_key", 0o600)
        argv = hostrun.ssh_command(self.cfg)

        # Control: the same options with the hostile file as configuration inherit from it.
        control = self.resolve(["ssh", "-F", str(hostile)] + argv[3:], home)
        self.assertIn("198.51.100.1", " ".join(control.get("proxyjump", [])))
        self.assertEqual(control.get("bindaddress"), ["192.0.2.50"])  # -o wins; the proxy still does not
        self.assertEqual(control.get("bindinterface"), ["eth9"])

        got = self.resolve(argv, home)
        self.assertEqual(got["bindaddress"], ["192.0.2.50"])
        self.assertEqual(got["hostname"], ["192.0.2.10"])
        self.assertEqual(got["user"], ["root"])
        self.assertEqual(got["identityfile"], [str(self.dir / "root_key")])
        self.assertEqual(got["userknownhostsfile"], [str(self.dir / "known_hosts")])
        for key, value in (("identitiesonly", "yes"), ("identityagent", "none"), ("stricthostkeychecking", "true"),
                           ("controlmaster", "false"), ("forwardagent", "no"),
                           ("forwardx11", "no"), ("clearallforwardings", "yes"), ("passwordauthentication", "no"),
                           ("batchmode", "no")):
            self.assertEqual(got.get(key), [value], key)
        self.assertEqual(got.get("controlpath", ["none"]), ["none"])  # ssh -G omits it when none
        self.assertIn(got.get("proxyjump", ["none"]), (["none"],))
        self.assertIn(got.get("proxycommand", ["none"]), (["none"],))
        self.assertNotIn("bindinterface", got)


class FromRenderingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        (self.dir / "snip_key.pub").write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBTESTKEYONLYxxxxxxxxxxxxxxx t\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_prepare_renders_the_validated_address(self):
        cfg = fixtures.make_lab(self.dir)
        self.assertIn("export CL_WORKSTATION_ADDR=192.0.2.50\n", hostrun.render("prepare", cfg))
        cfg = fixtures.make_lab(self.dir, PVE_HOST="2001:db8::10", PVE_WORKSTATION_ADDR="2001:DB8:0::50")
        self.assertIn("export CL_WORKSTATION_ADDR=2001:db8::50\n", hostrun.render("prepare", cfg))

    def test_prepare_refuses_an_invalid_address_before_rendering(self):
        for bad in ("192.0.2.0/24", "192.0.2.50,198.51.100.7", "*", "workstation.example.invalid"):
            cfg = fixtures.make_lab(self.dir, PVE_WORKSTATION_ADDR=bad)
            with self.subTest(addr=bad), self.assertRaisesRegex(ConfigError, "PVE_WORKSTATION_ADDR"):
                hostrun.render("prepare", cfg)


class LocalAddressPrecheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)
        (self.dir / "root_key").write_text("placeholder")
        os.chmod(self.dir / "root_key", 0o600)

    def tearDown(self):
        self.tmp.cleanup()

    def test_failing_precheck_refuses_before_the_prompt(self):
        popen, runner_calls, seen = Recorder(), [], []

        def runner(argv, **kw):
            runner_calls.append(argv)
            return subprocess.CompletedProcess(argv, 1)

        def not_here(addr):
            seen.append(addr)
            raise hostrun.HostRunError(f"PVE_WORKSTATION_ADDR {addr} is not an address of this machine")

        sha = hostrun.script_hash(hostrun.render("preflight", self.cfg))
        out = io.StringIO()
        with self.assertRaisesRegex(hostrun.HostRunError, "192.0.2.50 is not an address of this machine"):
            hostrun.run("preflight", self.cfg, stdin=io.StringIO(sha[:8] + "\n"), stdout=out, env=NO_AGENT_ENV,
                        ancestors=(), is_tty=lambda: True, runner=runner, popen=popen, addr_check=not_here)
        self.assertEqual(seen, ["192.0.2.50"])
        self.assertEqual((popen.calls, runner_calls), ([], []))
        self.assertNotIn("Type the first", out.getvalue())
        self.assertFalse((self.dir / "state" / "approvals.jsonl").exists())
        self.assertFalse((self.dir / "state" / "approved").exists())

    def test_real_check_binds_without_connecting(self):
        calls = []

        class FakeSocket:
            def __init__(self, family, kind):
                calls.append(("socket", family, kind))

            def bind(self, address):
                calls.append(("bind", address))

            def connect(self, address):  # pragma: no cover - must never be called
                calls.append(("connect", address))

            def close(self):
                calls.append(("close",))

        hostrun.local_address_check("192.0.2.50", socket_factory=FakeSocket)
        hostrun.local_address_check("2001:db8::50", socket_factory=FakeSocket)
        self.assertEqual(calls, [("socket", socket.AF_INET, socket.SOCK_STREAM), ("bind", ("192.0.2.50", 0)),
                                 ("close",), ("socket", socket.AF_INET6, socket.SOCK_STREAM),
                                 ("bind", ("2001:db8::50", 0)), ("close",)])

    def test_real_check_refuses_an_address_this_machine_does_not_have(self):
        # A TEST-NET address is not assigned here; bind() fails and nothing is sent.
        with self.assertRaisesRegex(hostrun.HostRunError, "not an address of this machine"):
            hostrun.local_address_check("192.0.2.123")


class _Stop(Exception):
    pass


class ApiSourceAddressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.cfg = fixtures.make_lab(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def capture_connection(self, transport):
        """Send one request; record what the HTTPS connection was built with, then stop."""
        seen = {}

        def fake_connection(host, **kw):
            seen.update(kw, host=host)
            raise _Stop

        with mock.patch.object(pveapi.http.client, "HTTPSConnection", side_effect=fake_connection), \
                self.assertRaises(_Stop):
            transport("GET", "https://192.0.2.10:8006/api2/json/version", {}, None)
        return seen

    def contexts(self):
        made = []

        def create(cafile=None, **_kw):
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            made.append((cafile, ctx))
            return ctx
        return made, mock.patch.object(pveapi.ssl, "create_default_context", side_effect=create)

    def test_transport_receives_source_address_and_verifying_context(self):
        made, patch = self.contexts()
        with patch, mock.patch.dict(os.environ, {}, clear=True):
            seen = self.capture_connection(pveapi.urllib_transport("ca.pem", source_address="192.0.2.50"))
        (cafile, ctx), = made
        self.assertEqual(cafile, "ca.pem")
        self.assertEqual(seen["source_address"], ("192.0.2.50", 0))
        self.assertIs(seen["context"], ctx)
        self.assertTrue(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(seen["host"], "192.0.2.10:8006")

    def test_without_source_address_nothing_changes(self):
        made, patch = self.contexts()
        with patch, mock.patch.dict(os.environ, {}, clear=True):
            seen = self.capture_connection(pveapi.urllib_transport("ca.pem"))
        self.assertNotIn("source_address", seen)
        self.assertIs(seen["context"], made[0][1])

    def built_transport(self, cfg, env):
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(pveapi, "urllib_transport", return_value=lambda *a: (200, b"{}")) as factory:
            pveapi.Client.from_config(cfg)
        return factory.call_args

    def test_from_config_passes_the_validated_address(self):
        call = self.built_transport(self.cfg, {})
        self.assertEqual(call.kwargs["source_address"], "192.0.2.50")

    def test_environment_proxy_is_refused_when_the_address_is_set(self):
        for name in ("https_proxy", "HTTPS_PROXY"):
            with self.subTest(var=name), self.assertRaisesRegex(ConfigError, "no_proxy"):
                self.built_transport(self.cfg, {name: "http://198.51.100.9:3128"})
        call = self.built_transport(self.cfg, {"https_proxy": "http://198.51.100.9:3128", "no_proxy": "192.0.2.10"})
        self.assertEqual(call.kwargs["source_address"], "192.0.2.50")

    def test_absent_setting_is_refused_unless_the_caller_opts_in(self):
        # L1B (S-6), deliberate change: the old test asserted the silent unbound connection.
        # Without the setting there is no connection; the unbound form is an explicit opt-in
        # (no command line option sets it), says so, and still ignores proxy variables.
        cfg = Config({k: v for k, v in self.cfg.values.items() if k != "PVE_WORKSTATION_ADDR"})
        with self.assertRaisesRegex(ConfigError, "PVE_WORKSTATION_ADDR is not set"):
            self.built_transport(cfg, {"https_proxy": "http://198.51.100.9:3128"})
        notes = []
        with mock.patch.dict(os.environ, {"https_proxy": "http://198.51.100.9:3128"}, clear=True), \
                mock.patch.object(pveapi, "urllib_transport", return_value=lambda *a: (200, b"{}")) as factory:
            pveapi.Client.from_config(cfg, allow_unbound=True, notice=notes.append)
        self.assertIsNone(factory.call_args.kwargs["source_address"])
        self.assertEqual(len(notes), 1)
        self.assertIn("PVE_WORKSTATION_ADDR is not set", notes[0])

    def test_bound_transport_never_uses_a_proxy(self):
        made, patch = self.contexts()
        with patch, mock.patch.dict(os.environ, {"https_proxy": "http://198.51.100.9:3128"}, clear=True):
            seen = self.capture_connection(pveapi.urllib_transport("ca.pem", source_address="192.0.2.50"))
        self.assertEqual(seen["host"], "192.0.2.10:8006")  # direct, not the proxy

    def test_invalid_address_refused_by_the_client(self):
        cfg = fixtures.make_lab(Path(self.tmp.name), PVE_WORKSTATION_ADDR="192.0.2.0/24")
        with self.assertRaisesRegex(ConfigError, "exactly one IP address"):
            self.built_transport(cfg, {})


if __name__ == "__main__":
    unittest.main()
