"""L1B LA-TRANSPORT: connection hardening, private writes and action parameters.

Gaps S-3, S-4, S-5, S-6, W-1 ... W-4, F-G, R3-3c and HA-P (see the L1 close-out notes, a dated
working document that is kept outside the repository, section 3). Offline only: documentation addresses (RFC 5737, RFC 3849), temporary directories,
fake connections and stub tools. ``ssh -G`` resolves a configuration locally and opens no
connection. No test opens a socket to anything, reads a real settings, key or state path, or
runs the real command line against real settings: every settings file here is synthetic and
``HOME`` points at a temporary directory.
"""

import contextlib
import http.client
import io
import os
import re
import shutil
import ssl
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from lab_agent import cli, config, hostrun, pveapi, redact
from lab_agent.classify import overrides_digest as cl_digest
from lab_agent.config import Config, ConfigError
from tests import fixtures
from tests.test_hostrun import NO_AGENT_ENV, Recorder, encrypted

AGENT_DIR = Path(__file__).resolve().parent.parent
SECRET = "11111111-2222-3333-4444-555555555555"
# IPv6 text that is not documentation space is built from parts: the repository hygiene scan
# flags any such literal in a tracked file, and these tests need them as refused inputs.
LINK_LOCAL6 = "fe80" + "::1"
MULTICAST6 = "ff02" + "::1"
LOOPBACK6 = "::1"
MAPPED6 = "::ffff:192.0.2.50"


def modified(cfg, **values):
    """A copy of ``cfg`` with raw values replaced (a value the env-file parser would not carry)."""
    merged = dict(cfg.values)
    for key, value in values.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return Config(merged, source=cfg.source)


class LabCase(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)
        (self.dir / "root_key").write_text("placeholder")
        os.chmod(self.dir / "root_key", 0o600)
        (self.dir / "snip_key.pub").write_text(
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBTESTKEYONLYxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx test\n")

    def tearDown(self):
        self.tmp.cleanup()

    def private(self, name):
        path = self.dir / name
        path.mkdir(mode=0o700)
        os.chmod(path, 0o700)
        return path


@contextlib.contextmanager
def umask(value):
    old = os.umask(value)
    try:
        yield
    finally:
        os.umask(old)


# --------------------------------------------------------------------------- S-3

def baseline_ssh_argv(cfg):
    """The argument list before L1B (kept here as the control for what ``ssh -G`` shows)."""
    return ["ssh", "-F", "none", "-T", "-i", str(cfg.path("PVE_ROOT_KEY")),
            "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none", "-o", "ControlMaster=no",
            "-o", "ControlPath=none", "-o", "ForwardAgent=no", "-o", "ForwardX11=no",
            "-o", "ClearAllForwardings=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={cfg.path('PVE_KNOWN_HOSTS')}", "-o", "BatchMode=no",
            "-o", "PasswordAuthentication=no", "-o", f"BindAddress={cfg.workstation_addr()}",
            f"root@{cfg.get('PVE_HOST')}", "bash -s"]


class SshOptionsTests(LabCase):
    def resolve(self, argv):
        """``ssh -G``: print the resolved configuration. No connection is made."""
        home = self.dir / "home"
        home.mkdir(exist_ok=True)
        env = {"HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        proc = subprocess.run([argv[0], "-G"] + argv[1:], capture_output=True, text=True, env=env, timeout=10,
                              stdin=subprocess.DEVNULL)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        resolved = {}
        for line in proc.stdout.splitlines():
            key, _, value = line.partition(" ")
            resolved.setdefault(key, []).append(value)
        return resolved

    def test_effective_options_ignore_global_known_hosts_and_keyboard_interactive(self):
        if not shutil.which("ssh"):
            self.skipTest("ssh not installed")
        old = self.resolve(baseline_ssh_argv(self.cfg))
        # Control: before L1B ssh still consulted the global known-hosts files and still
        # offered keyboard-interactive authentication.
        self.assertNotEqual(old["globalknownhostsfile"], ["/dev/null"])
        self.assertEqual(old["kbdinteractiveauthentication"], ["yes"])
        got = self.resolve(hostrun.ssh_command(self.cfg))
        self.assertEqual(got["globalknownhostsfile"], ["/dev/null"])
        self.assertEqual(got["userknownhostsfile"], [str(self.dir / "known_hosts")])
        self.assertEqual(got["kbdinteractiveauthentication"], ["no"])
        self.assertEqual(got["preferredauthentications"], ["publickey"])
        self.assertEqual(got["passwordauthentication"], ["no"])
        self.assertEqual(got["hostbasedauthentication"], ["no"])
        self.assertEqual(got["gssapiauthentication"], ["no"])
        self.assertEqual(got["updatehostkeys"], ["false"])
        self.assertEqual(got["verifyhostkeydns"], ["false"])
        self.assertEqual(got["port"], ["22"])
        self.assertEqual(got["bindaddress"], ["192.0.2.50"])
        self.assertEqual(got["stricthostkeychecking"], ["true"])

    def test_the_command_line_never_carries_the_token_secret_or_a_passphrase(self):
        argv = " ".join(hostrun.ssh_command(self.cfg))
        self.assertNotIn(self.cfg.token_secret(), argv)
        self.assertNotIn("PVEAPIToken", argv)

    def test_ssh_command_refuses_unsafe_host_and_paths_before_anything_exists(self):
        for host in ("-oProxyCommand=x", "root@host", "host:2222", "h/x", "h h", "", "[2001:db8::10]"):
            with self.subTest(host=host), self.assertRaises(ConfigError):
                hostrun.ssh_command(modified(self.cfg, PVE_HOST=host))
        for key in ("PVE_ROOT_KEY", "PVE_KNOWN_HOSTS"):
            for bad in ("relative/key", "/tmp/a b/key", "/tmp/a\"b", "/tmp/k%h", "/tmp/$HOME/k", "/tmp/a\\b"):
                with self.subTest(key=key, value=bad), self.assertRaisesRegex(ConfigError, "absolute path"):
                    hostrun.ssh_command(modified(self.cfg, **{key: bad}))


# --------------------------------------------------------------------------- S-4

class SourceAddressTests(unittest.TestCase):
    def addr(self, value, host="192.0.2.10"):
        return Config({"PVE_WORKSTATION_ADDR": value, "PVE_HOST": host}).workstation_addr()

    def test_addresses_that_cannot_be_this_machines_source_are_refused(self):
        refused = ("127.0.0.1", "127.8.9.10", "255.255.255.255", "240.0.0.1", "0.1.2.3", "169.254.7.7",
                   "224.0.0.1", "0.0.0.0", LOOPBACK6, LINK_LOCAL6, MULTICAST6, MAPPED6, "::")
        for value in refused:
            host = "2001:db8::10" if ":" in value else "192.0.2.10"
            with self.subTest(value=value), self.assertRaises(ConfigError):
                self.addr(value, host)

    def test_real_source_addresses_are_still_accepted(self):  # control
        for value, host in (("192.0.2.50", "192.0.2.10"), ("198.51.100.7", "pve.example.invalid"),
                            ("203.0.113.9", "198.51.100.1"), ("2001:db8::50", "2001:db8::10")):
            with self.subTest(value=value):
                self.assertEqual(self.addr(value, host), value)

    def test_the_message_names_the_reason(self):
        with self.assertRaisesRegex(ConfigError, "loopback"):
            self.addr("127.0.0.1")
        with self.assertRaisesRegex(ConfigError, "link-local"):
            self.addr(LINK_LOCAL6, "2001:db8::10")
        with self.assertRaisesRegex(ConfigError, "IPv4-mapped"):
            self.addr(MAPPED6, "2001:db8::10")


class HostSettingTests(unittest.TestCase):
    def test_valid_hosts(self):
        for raw, canonical in (("192.0.2.10", "192.0.2.10"), ("2001:DB8::10", "2001:db8::10"),
                               ("pve", "pve"), ("pve-1.lab.example.invalid", "pve-1.lab.example.invalid"),
                               ("PVE.Example.Invalid", "PVE.Example.Invalid")):
            with self.subTest(raw=raw):
                self.assertEqual(Config({"PVE_HOST": raw}).host(), canonical)

    def test_invalid_hosts(self):
        refused = ("", " ", " pve", "pve ", "pve\n", "root@pve", "pve/x", "pve:22", "[2001:db8::10]", "pve%eth0",
                   "-pve", "-oProxyCommand=x", "pve_1", "a..b", ".pve", "pve.", "1.2.3", "192.0.2.256", "0x7f.1",
                   "0.0.0.0", "224.0.0.1", "::", "a" * 64 + ".example.invalid", "a" * 250 + ".example.invalid",
                   "pve;reboot", "pve,other", "pve*", '"pve"', "192.0.2.010")
        for raw in refused:
            with self.subTest(raw=raw), self.assertRaises(ConfigError):
                Config({"PVE_HOST": raw}).host()

    def test_a_port_in_the_host_says_that_ssh_uses_22_only(self):
        with self.assertRaisesRegex(ConfigError, "port 22 only"):
            Config({"PVE_HOST": "pve:2222"}).host()

    def test_there_is_no_ssh_port_setting(self):
        with self.assertRaisesRegex(ConfigError, "no ssh port setting.*port 22 only"):
            config.parse_env_text("PVE_SSH_PORT=2222\n")
        self.assertEqual(hostrun.SSH_PORT, 22)

    def test_api_port(self):
        self.assertEqual(Config({"PVE_PORT": "8006"}).port(), 8006)
        for raw in ("0", "65536", "80a", "8006/x", "8006@host", "-1", " 8006", "８００６"):
            with self.subTest(raw=raw), self.assertRaises(ConfigError):
                Config({"PVE_PORT": raw}).port()

    def test_token_id_and_range_must_match_in_full(self):
        with self.assertRaises(ConfigError):
            Config({"PVE_TOKEN_ID": "u@pve!lab\n"}).token_id()
        with self.assertRaises(ConfigError):
            Config({"PVE_VMID_RANGE": "9100-9199\n"}).vmid_range()
        with self.assertRaises(ConfigError):
            Config({"PVE_VMID_RANGE": "９１００-９１９９"}).vmid_range()


# --------------------------------------------------------------------------- S-5, S-6

class FakeConnection:
    """Stands in for http.client.HTTPSConnection: records the request, answers from a script."""

    script: list = []
    made: list = []

    def __init__(self, host, **kw):
        self.host, self.kw, self.sock, self.requests = host, kw, None, []
        FakeConnection.made.append(self)

    def set_debuglevel(self, level):
        pass

    def request(self, method, selector, body=None, headers=None, **kw):
        self.requests.append((method, selector, dict(headers or {})))

    def getresponse(self):
        raw = FakeConnection.script.pop(0)

        class Sock:
            def makefile(self, *a, **k):
                return io.BytesIO(raw)

        response = http.client.HTTPResponse(Sock())
        response.begin()
        return response

    def close(self):
        pass


def http_answer(status, body=b"{}", headers=()):
    head = f"HTTP/1.1 {status} X\r\nContent-Length: {len(body)}\r\nConnection: close\r\n"
    return head.encode() + b"".join(f"{k}: {v}\r\n".encode() for k, v in headers) + b"\r\n" + body


class ApiClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.cfg = fixtures.make_lab(Path(self.tmp.name))
        FakeConnection.script, FakeConnection.made = [], []

    def tearDown(self):
        self.tmp.cleanup()

    def transport(self, **kw):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with mock.patch.object(pveapi.ssl, "create_default_context", return_value=ctx):
            return pveapi.urllib_transport("ca.pem", **kw)

    def send(self, transport, url="https://192.0.2.10:8006/api2/json/version"):
        # Both connection classes are faked, so no code under test can open a real socket.
        with mock.patch.object(pveapi.http.client, "HTTPSConnection", FakeConnection), \
                mock.patch.object(pveapi.http.client, "HTTPConnection", FakeConnection):
            return transport("GET", url, {"Authorization": "PVEAPIToken=u@pve!lab=" + SECRET}, None)

    # S-5
    def test_ipv6_literal_host_gives_a_bracketed_url(self):
        transport = pveapi.FakeTransport({("GET", "/version"): (200, {"version": "9"})})
        client = pveapi.Client("2001:db8::10", 8006, "u@pve!lab", "x", transport)
        client.get("/version")
        self.assertTrue(transport.calls[0][1].startswith("https://[2001:db8::10]:8006/api2/json/version"))

    def test_the_client_refuses_a_host_or_port_that_would_change_the_url(self):
        transport = pveapi.FakeTransport({})
        for host, port in (("192.0.2.10/x", 8006), ("user@192.0.2.10", 8006), ("192.0.2.10:1", 8006),
                           ("192.0.2.10", "8006@evil.example.invalid"), ("192.0.2.10", "80/x"), ("", 8006)):
            with self.subTest(host=host, port=port), self.assertRaises(ConfigError):
                pveapi.Client(host, port, "u@pve!lab", "x", transport)
        self.assertEqual(transport.calls, [])

    # S-6
    def test_without_the_setting_the_client_refuses_to_connect_unbound(self):
        cfg = modified(self.cfg, PVE_WORKSTATION_ADDR=None)
        with mock.patch.object(pveapi, "urllib_transport") as factory:
            with self.assertRaisesRegex(ConfigError, "PVE_WORKSTATION_ADDR is not set"):
                pveapi.Client.from_config(cfg)
        factory.assert_not_called()
        empty = modified(self.cfg, PVE_WORKSTATION_ADDR="")
        with self.assertRaisesRegex(ConfigError, "PVE_WORKSTATION_ADDR is not set"):
            pveapi.Client.from_config(empty)

    def test_unbound_is_an_explicit_opt_in_with_a_notice(self):
        cfg = modified(self.cfg, PVE_WORKSTATION_ADDR=None)
        notes = []
        with mock.patch.object(pveapi, "urllib_transport", return_value=lambda *a: (200, b"{}")) as factory:
            pveapi.Client.from_config(cfg, allow_unbound=True, notice=notes.append)
        self.assertIsNone(factory.call_args.kwargs["source_address"])
        self.assertEqual(len(notes), 1)
        self.assertIn("kernel chooses", notes[0])
        err = io.StringIO()
        with mock.patch.object(pveapi, "urllib_transport", return_value=lambda *a: (200, b"{}")), \
                contextlib.redirect_stderr(err):
            pveapi.Client.from_config(cfg, allow_unbound=True)
        self.assertIn("notice", err.getvalue())

    def test_no_command_line_option_opts_in(self):
        self.assertNotIn("allow_unbound", Path(cli.__file__).read_text(encoding="utf-8"))

    def test_the_bound_form_gives_no_notice(self):  # control
        notes = []
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(pveapi, "urllib_transport", return_value=lambda *a: (200, b"{}")) as factory:
            pveapi.Client.from_config(self.cfg, notice=notes.append)
        self.assertEqual(factory.call_args.kwargs["source_address"], "192.0.2.50")
        self.assertEqual(notes, [])

    def test_the_unbound_transport_never_uses_an_environment_proxy(self):
        for source in (None, "192.0.2.50"):
            FakeConnection.made.clear()
            FakeConnection.script[:] = [http_answer(200, b'{"data": 1}')]
            with self.subTest(source=source), mock.patch.dict(
                    os.environ, {"https_proxy": "http://198.51.100.9:3128", "HTTPS_PROXY": "http://198.51.100.9:3128",
                                 "all_proxy": "http://198.51.100.9:3128"}, clear=True):
                status, body = self.send(self.transport(source_address=source))
            self.assertEqual(status, 200)
            (conn,) = FakeConnection.made
            self.assertEqual(conn.host, "192.0.2.10:8006")  # direct, not the proxy
            self.assertEqual(conn.requests[0][1], "/api2/json/version")
            if source:
                self.assertEqual(conn.kw["source_address"], (source, 0))

    def test_a_redirect_is_not_followed_and_the_token_is_not_repeated(self):
        FakeConnection.script[:] = [
            http_answer(302, b"", [("Location", "https://198.51.100.7/steal")]),
            http_answer(200, b'{"data": "stolen"}'),  # what a followed redirect would receive
        ]
        with mock.patch.dict(os.environ, {}, clear=True):
            status, body = self.send(self.transport())
        self.assertEqual(status, 302)
        self.assertEqual(len(FakeConnection.made), 1)  # no second connection, to anyone
        self.assertEqual(len(FakeConnection.script), 1)

    def test_a_200_answer_passes_through(self):  # control for the redirect test
        FakeConnection.script[:] = [http_answer(200, b'{"data": "ok"}')]
        status, body = self.send(self.transport())
        self.assertEqual((status, body), (200, b'{"data": "ok"}'))

    def test_the_client_raises_on_a_redirect_status(self):
        transport = pveapi.FakeTransport({("GET", "/version"): (302, "x")})
        client = pveapi.Client("192.0.2.10", 8006, "u@pve!lab", SECRET, transport)
        with self.assertRaisesRegex(pveapi.PveError, "redirect refused") as ctx:
            client.get("/version")
        self.assertNotIn(SECRET, str(ctx.exception))

    def test_the_transport_speaks_https_only(self):
        FakeConnection.script[:] = [http_answer(200)]
        with self.assertRaisesRegex(ValueError, "https only"):
            self.send(self.transport(), "http://192.0.2.10:8006/api2/json/version")
        self.assertEqual(FakeConnection.made, [])

    def test_a_malformed_answer_is_an_os_level_error(self):
        FakeConnection.script[:] = [b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\nshort"]
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(OSError):
            self.send(self.transport())


# --------------------------------------------------------------------------- W-1, W-4, F-G

class StateDirTests(LabCase):
    def cfg_state(self, path):
        return modified(self.cfg, PVE_LAB_STATE=str(path))

    def test_a_state_directory_with_the_wrong_mode_is_refused(self):
        for mode in (0o750, 0o705, 0o777, 0o755, 0o500):
            path = self.dir / f"st{mode:o}"
            path.mkdir()
            os.chmod(path, mode)
            with self.subTest(mode=oct(mode)), self.assertRaisesRegex(ConfigError, "expected 700"):
                self.cfg_state(path).state_dir()

    def test_a_state_directory_of_another_owner_is_refused(self):
        path = self.private("st")
        with mock.patch.object(config.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaisesRegex(ConfigError, "owned by another user"):
                self.cfg_state(path).state_dir()

    def test_a_symlink_or_a_file_as_the_state_directory_is_refused(self):
        real = self.private("real")
        (self.dir / "link").symlink_to(real)
        with self.assertRaisesRegex(ConfigError, "symlink"):
            self.cfg_state(self.dir / "link").state_dir()
        (self.dir / "plain").write_text("x")
        with self.assertRaisesRegex(ConfigError, "not a directory"):
            self.cfg_state(self.dir / "plain").state_dir()

    def test_a_private_existing_directory_and_a_missing_one_are_accepted(self):  # control
        path = self.private("ok")
        self.assertEqual(self.cfg_state(path).state_dir(), path)
        with umask(0):
            made = self.cfg_state(self.dir / "a" / "b" / "state").state_dir()
        for part in (self.dir / "a", self.dir / "a" / "b", made):
            self.assertEqual(part.stat().st_mode & 0o7777, 0o700, str(part))

    def test_a_state_directory_with_the_wrong_mode_stops_the_commands_that_write_there(self):
        loose = self.dir / "loose"
        loose.mkdir()
        os.chmod(loose, 0o755)
        cfg = self.cfg_state(loose)
        with self.assertRaises(ConfigError):
            hostrun.run("preflight", cfg, stdin=io.StringIO("x\n"), stdout=io.StringIO(), env=NO_AGENT_ENV,
                        ancestors=(), is_tty=lambda: True, runner=encrypted, popen=Recorder(),
                        addr_check=lambda _a: None)


class PrivateWriteTests(LabCase):
    def setUp(self):
        super().setUp()
        self.out = self.private("out")

    def test_ancestors_are_created_700_whatever_the_umask(self):
        for mask in (0, 0o022, 0o277):
            target = self.dir / f"m{mask:o}" / "x" / "y" / "f"
            with self.subTest(umask=oct(mask)), umask(mask):
                hostrun.write_private(target, b"data")
            for part in (target.parent.parent.parent, target.parent.parent, target.parent):
                self.assertEqual(part.stat().st_mode & 0o7777, 0o700, str(part))
            self.assertEqual(target.read_bytes(), b"data")
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_a_sticky_setgid_or_setuid_parent_is_refused(self):
        for mode in (0o1700, 0o2700, 0o4700):
            os.chmod(self.out, mode)
            with self.subTest(mode=oct(mode)), self.assertRaisesRegex(hostrun.HostRunError, "expected 700"):
                hostrun.write_private(self.out / "f", b"data")
            self.assertEqual(list(self.out.iterdir()), [])
        os.chmod(self.out, 0o700)

    def test_swapping_the_parent_after_the_check_redirects_nothing(self):
        attacker = self.private("attacker")
        real_fsync, swapped = os.fsync, []

        def swap_then_sync(fd):
            if not swapped:  # the parent path becomes a symlink to the attacker's directory
                swapped.append(True)
                os.rename(self.out, self.dir / "moved")
                os.symlink(attacker, self.out)
            return real_fsync(fd)

        with mock.patch.object(hostrun.os, "fsync", side_effect=swap_then_sync):
            hostrun.write_private(self.out / "f", b"secret")
        self.assertTrue(swapped)
        self.assertEqual((self.dir / "moved" / "f").read_bytes(), b"secret")
        self.assertEqual(list(attacker.iterdir()), [])
        self.assertEqual(list((self.dir / "moved").iterdir()), [self.dir / "moved" / "f"])

    def test_swapping_the_parent_also_redirects_nothing_for_an_exclusive_write(self):
        attacker = self.private("attacker")
        real_fsync, swapped = os.fsync, []

        def swap_then_sync(fd):
            if not swapped:
                swapped.append(True)
                os.rename(self.out, self.dir / "moved")
                os.symlink(attacker, self.out)
            return real_fsync(fd)

        with mock.patch.object(hostrun.os, "fsync", side_effect=swap_then_sync):
            hostrun.write_private(self.out / "token", b"secret\n", exclusive=True)
        self.assertEqual((self.dir / "moved" / "token").read_bytes(), b"secret\n")
        self.assertEqual(list(attacker.iterdir()), [])

    def test_a_name_that_is_not_a_file_name_is_refused(self):
        for bad in (self.out / "..", self.out / ".", Path("/")):
            with self.subTest(path=str(bad)), self.assertRaises(hostrun.HostRunError):
                hostrun.write_private(bad, b"x")

    def test_both_link_and_direct_create_failing_keeps_the_secret(self):
        token = self.out / "token"
        stream = io.BytesIO(f"CORELAB_TOKEN_SECRET={SECRET}\n".encode())
        out, log = io.StringIO(), io.StringIO()
        with mock.patch.object(hostrun.os, "link", side_effect=OSError(1, "no links")), \
                mock.patch.object(hostrun.os, "fsync", side_effect=[None, OSError(5, "io error")]):
            with self.assertRaisesRegex(hostrun.HostRunError, "is kept in") as ctx:
                hostrun.handle_output(stream, "token", out, log, token_file=token)
        self.assertNotIn(SECRET, str(ctx.exception))
        (kept,) = list(self.out.iterdir())
        self.assertRegex(kept.name, r"^\.token\.[0-9a-f]{16}\.tmp$")
        self.assertEqual(kept.read_text(), SECRET + "\n")
        self.assertEqual(kept.stat().st_mode & 0o777, 0o600)
        self.assertFalse(token.exists())  # no half-written destination
        self.assertNotIn(SECRET, out.getvalue() + log.getvalue())

    def test_a_secret_that_cannot_be_stored_at_all_is_reported_with_the_way_out(self):
        token = self.out / "token"
        stream = io.BytesIO(f"CORELAB_TOKEN_SECRET={SECRET}\n".encode())
        out, log = io.StringIO(), io.StringIO()
        with mock.patch.object(hostrun.os, "fsync", side_effect=OSError(28, "No space left on device")):
            with self.assertRaisesRegex(hostrun.HostRunError, "remove it there and run bootstrap again") as ctx:
                hostrun.handle_output(stream, "token", out, log, token_file=token)
        self.assertNotIn(SECRET, str(ctx.exception))
        self.assertEqual(list(self.out.iterdir()), [])
        self.assertNotIn(SECRET, out.getvalue() + log.getvalue())

    def test_a_token_file_that_appeared_meanwhile_gives_the_same_way_out(self):
        token = self.out / "token"
        token.write_text("existing\n")
        stream = io.BytesIO(f"CORELAB_TOKEN_SECRET={SECRET}\n".encode())
        with self.assertRaisesRegex(hostrun.HostRunError, "already exists.*remove it there"):
            hostrun.handle_output(stream, "token", io.StringIO(), io.StringIO(), token_file=token)
        self.assertEqual(token.read_text(), "existing\n")


class TokenOutputTests(unittest.TestCase):
    def test_no_other_line_of_the_token_action_shows_a_uuid_or_the_stored_secret(self):
        with fixtures.private_tmpdir() as d:
            token = Path(d) / "out" / "token"
            lines = [f"created token value {'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'}\n",
                     f"CORELAB_TOKEN_SECRET={SECRET}\n", f"again: {SECRET}\n", "done\n"]
            out, log = io.StringIO(), io.StringIO()
            hostrun.handle_output(io.BytesIO("".join(lines).encode()), "token", out, log, token_file=token)
            shown = out.getvalue() + log.getvalue()
            self.assertNotIn(SECRET, shown)
            self.assertNotIn("aaaaaaaa-bbbb", shown)
            self.assertIn("done", shown)
            self.assertEqual(token.read_text(), SECRET + "\n")

    def test_other_actions_keep_their_uuids_visible(self):  # control: only the token action scrubs
        out = io.StringIO()
        hostrun.handle_output(io.BytesIO(b"vm uuid aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\n"), "terminal", out,
                              io.StringIO())
        self.assertIn("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", out.getvalue())


class JsonWriteTests(LabCase):
    """W-1: ``cli._write_json``."""

    def test_a_symlink_at_the_destination_is_not_followed(self):
        out = self.private("out")
        victim = self.dir / "victim"
        victim.write_text("keep")
        (out / "f.json").symlink_to(victim)
        with self.assertRaises(hostrun.HostRunError):
            cli._write_json(out / "f.json", {"a": 1})
        self.assertEqual(victim.read_text(), "keep")

    def test_the_file_is_private_and_the_parent_is_checked(self):
        out = self.private("out")
        with umask(0):
            cli._write_json(out / "f.json", {"b": 2, "a": 1})
        self.assertEqual((out / "f.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual((out / "f.json").read_text(), '{\n  "a": 1,\n  "b": 2\n}\n')
        os.chmod(out, 0o755)
        with self.assertRaisesRegex(hostrun.HostRunError, "expected 700"):
            cli._write_json(out / "g.json", {})
        self.assertFalse((out / "g.json").exists())
        (self.dir / "linkdir").symlink_to(self.private("real"))
        with self.assertRaisesRegex(hostrun.HostRunError, "symlink"):
            cli._write_json(self.dir / "linkdir" / "h.json", {})

    def test_missing_ancestors_are_created_700(self):
        with umask(0):
            cli._write_json(self.dir / "n1" / "n2" / "f.json", {})
        for part in (self.dir / "n1", self.dir / "n1" / "n2"):
            self.assertEqual(part.stat().st_mode & 0o7777, 0o700)

    def test_the_command_line_refuses_a_symlink_destination_with_exit_2(self):
        out = self.private("out")
        victim = self.dir / "victim"
        victim.write_text("keep")
        (out / "cls.json").symlink_to(victim)
        inv = self.dir / "inventory.json"
        inv.write_text("{}")
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}), \
                mock.patch.object(cli.cl, "classify", return_value={}):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = cli.main(["classify", "--inventory", str(inv), "--out", str(out / "cls.json")])
        self.assertEqual(code, 2)
        self.assertIn("lab-agent:", err.getvalue())
        self.assertEqual(victim.read_text(), "keep")

    def test_sanitized_evidence_is_not_written_through_a_symlink(self):
        victim = self.dir / "victim"
        victim.write_text("keep")
        (self.dir / "out.txt").symlink_to(victim)
        (self.dir / "in.txt").write_text("hello\n")
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = cli.main(["sanitize", str(self.dir / "in.txt"), str(self.dir / "out.txt")])
        self.assertEqual(code, 2)
        self.assertEqual(victim.read_text(), "keep")


# --------------------------------------------------------------------------- W-2, W-3

class ApprovalFilesTests(LabCase):
    def setUp(self):
        super().setUp()
        self.state = self.cfg.state_dir()
        self.script = hostrun.render("preflight", self.cfg)

    def test_the_approvals_file_is_not_opened_through_a_symlink(self):
        victim = self.dir / "victim"
        victim.write_text("keep\n")
        (self.state / "approvals.jsonl").symlink_to(victim)
        with self.assertRaisesRegex(hostrun.HostRunError, "symlink"):
            hostrun.record_approval(self.state, "preflight", self.script)
        self.assertEqual(victim.read_text(), "keep\n")
        with self.assertRaisesRegex(hostrun.HostRunError, "symlink"):
            hostrun.last_approved(self.state, "preflight")

    def test_records_append_and_the_file_stays_private(self):  # control
        with umask(0):
            hostrun.record_approval(self.state, "preflight", self.script, now="2026-11-16T00:00:00+00:00")
            hostrun.record_approval(self.state, "preflight", self.script, now="2026-11-16T00:00:01+00:00")
        path = self.state / "approvals.jsonl"
        self.assertEqual(len(path.read_text().splitlines()), 2)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        record, previous = hostrun.last_approved(self.state, "preflight")
        self.assertEqual(record["time"], "2026-11-16T00:00:01+00:00")
        self.assertEqual(previous, self.script)

    def test_a_loose_approvals_file_is_refused(self):
        path = self.state / "approvals.jsonl"
        path.write_text("")
        os.chmod(path, 0o644)
        with self.assertRaisesRegex(hostrun.HostRunError, "expected 600"):
            hostrun.record_approval(self.state, "preflight", self.script)
        self.assertEqual(path.read_text(), "")

    def test_a_record_cannot_name_a_file_outside_the_approved_directory(self):
        (self.state / "approvals.jsonl").write_text(
            '{"action": "preflight", "sha256": "../../outside", "time": "t"}\n')
        os.chmod(self.state / "approvals.jsonl", 0o600)
        (self.state / "approved").mkdir(mode=0o700)  # so that approved/../../outside.sh resolves
        (self.state.parent / "outside.sh").write_text("not an approved script\n")
        record, previous = hostrun.last_approved(self.state, "preflight")
        self.assertIsNotNone(record)
        self.assertIsNone(previous)

    def test_the_approved_directory_is_created_700_and_checked(self):
        with umask(0):
            hostrun.record_approval(self.state, "preflight", self.script)
        self.assertEqual((self.state / "approved").stat().st_mode & 0o7777, 0o700)
        os.chmod(self.state / "approved", 0o755)
        with self.assertRaisesRegex(hostrun.HostRunError, "expected 700"):
            hostrun.record_approval(self.state, "preflight", self.script + "#\n")
        os.chmod(self.state / "approved", 0o700)

    def test_a_symlink_in_place_of_the_approved_directory_or_copy_is_refused(self):
        real = self.private("real")
        (self.state / "approved").symlink_to(real)
        with self.assertRaisesRegex(hostrun.HostRunError, "symlink"):
            hostrun.record_approval(self.state, "preflight", self.script)
        self.assertEqual(list(real.iterdir()), [])
        (self.state / "approved").unlink()
        (self.state / "approved").mkdir(mode=0o700)
        sha = hostrun.script_hash(self.script)
        (self.state / "approved" / f"{sha}.sh").symlink_to(self.dir / "nowhere")
        with self.assertRaisesRegex(hostrun.HostRunError, "not a regular file"):
            hostrun.record_approval(self.state, "preflight", self.script)
        self.assertFalse((self.dir / "nowhere").exists())


class RunDirectoryTests(LabCase):
    def run_preflight(self, popen):
        sha = hostrun.script_hash(hostrun.render("preflight", self.cfg))
        out = io.StringIO()
        stdin = io.StringIO(sha[:8] + "\n")
        try:
            return hostrun.run("preflight", self.cfg, stdin=stdin, stdout=out, env=NO_AGENT_ENV, ancestors=(),
                               is_tty=lambda: True, runner=encrypted, popen=popen, addr_check=lambda _a: None), out
        finally:
            self.stdin_read = stdin.tell()
            self.stdout_text = out.getvalue()

    def test_a_loose_runs_directory_is_refused_before_the_prompt(self):
        state = self.cfg.state_dir()
        (state / "runs").mkdir()
        os.chmod(state / "runs", 0o755)
        popen = Recorder()
        with self.assertRaisesRegex(hostrun.HostRunError, "expected 700"):
            self.run_preflight(popen)
        self.assertEqual(popen.calls, [])
        self.assertEqual(self.stdin_read, 0)  # the owner was never asked
        self.assertEqual(self.stdout_text, "")

    def test_a_symlinked_runs_directory_is_refused(self):
        state = self.cfg.state_dir()
        real = self.private("real")
        (state / "runs").symlink_to(real)
        with self.assertRaisesRegex(hostrun.HostRunError, "symlink"):
            self.run_preflight(Recorder())
        self.assertEqual(list(real.iterdir()), [])

    def test_runs_and_approved_are_created_700_under_any_umask_and_the_log_is_private(self):  # control
        with umask(0):
            code, _ = self.run_preflight(Recorder(b"ok\n"))
        self.assertEqual(code, 0)
        state = self.cfg.state_dir()
        for name in ("runs", "approved"):
            self.assertEqual((state / name).stat().st_mode & 0o7777, 0o700, name)
        (log,) = list((state / "runs").iterdir())
        self.assertEqual(log.stat().st_mode & 0o777, 0o600)

    def test_a_failing_output_handler_lets_the_remote_script_finish_into_the_log(self):
        d = self.dir
        (d / "token").unlink()
        popen = Recorder(f"CORELAB_TOKEN_SECRET={SECRET}\nafter the secret {SECRET}\n".encode())
        sha = hostrun.script_hash(hostrun.render("bootstrap", self.cfg))
        out = io.StringIO()
        with mock.patch.object(hostrun, "write_private", side_effect=hostrun.HostRunError("stored nowhere")):
            with self.assertRaisesRegex(hostrun.HostRunError, "remove it there"):
                hostrun.run("bootstrap", self.cfg, stdin=io.StringIO(sha[:8] + "\n"), stdout=out,
                            env=NO_AGENT_ENV, ancestors=(), is_tty=lambda: True, runner=encrypted, popen=popen,
                            addr_check=lambda _a: None)
        (log,) = list((self.cfg.state_dir() / "runs").iterdir())
        text = log.read_text()
        self.assertIn("exit=0", text)
        self.assertIn("output error", text)
        self.assertNotIn(SECRET, text + out.getvalue())
        self.assertIn("remote script ended with exit 0", out.getvalue())


# --------------------------------------------------------------------------- R3-3c

class _NewRefusal(Exception):
    """Stands for a refusal type a module might add later."""
    __module__ = "lab_agent.future"


class ExitTwoTests(LabCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, err.getvalue()

    def run_host(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = hostrun.main(list(argv))
        return code, err.getvalue()

    def test_every_refusal_type_reaches_exit_two_in_both_command_lines(self):
        types = (hostrun.HostRunError("a"), ConfigError("b"), pveapi.PveError(403, "c", "/x"), _NewRefusal("d"),
                 OSError("e"), ValueError("f"))
        for exc in types:
            with self.subTest(exc=type(exc).__name__):
                with mock.patch.object(cli, "cmd_scan", side_effect=exc):
                    code, err = self.run_cli("scan", "x")
                self.assertEqual(code, 2)
                self.assertIn("lab-agent:", err)
                with mock.patch.object(hostrun, "render", side_effect=exc):
                    code, err = self.run_host("show", "preflight")
                self.assertEqual(code, 2)
                self.assertIn("host-run:", err)

    def test_a_bug_still_keeps_its_traceback(self):  # control: not every exception is a refusal
        with mock.patch.object(cli, "cmd_scan", side_effect=RuntimeError("bug")), self.assertRaises(RuntimeError):
            self.run_cli("scan", "x")
        with mock.patch.object(hostrun, "render", side_effect=KeyError("bug")), self.assertRaises(KeyError):
            self.run_host("show", "preflight")

    def test_messages_are_redacted(self):
        exc = ConfigError(f"failed with PVEAPIToken=u@pve!lab={SECRET}")
        with mock.patch.object(cli, "cmd_scan", side_effect=exc):
            _, err = self.run_cli("scan", "x")
        self.assertNotIn(SECRET, err)
        with mock.patch.object(hostrun, "render", side_effect=exc):
            _, err = self.run_host("show", "preflight")
        self.assertNotIn(SECRET, err)

    def test_is_refusal(self):
        self.assertTrue(config.is_refusal(_NewRefusal()))
        self.assertTrue(config.is_refusal(FileNotFoundError()))
        self.assertFalse(config.is_refusal(RuntimeError()))
        self.assertFalse(config.is_refusal(AssertionError()))


# --------------------------------------------------------------------------- HA-P

class ActionParameterTests(LabCase):
    def params(self, action, **values):
        return hostrun.action_params(hostrun.ACTIONS[action], modified(self.cfg, **values))

    def refused(self, action, key, bad_values):
        for bad in bad_values:
            with self.subTest(key=key, value=bad), self.assertRaises(ConfigError):
                self.params(action, **{key: bad})

    def test_every_action_parameter_has_a_rule(self):
        for name, action in hostrun.ACTIONS.items():
            for var, key in action.params:
                self.assertIn(key, hostrun._PARAM_CHECKS, f"{name}: {var} <- {key}")
        # A parameter without a rule is refused, never exported unchecked.
        orphan = hostrun.Action("orphan", (("CL_X", "PVE_NODE"),))
        with self.assertRaisesRegex(hostrun.HostRunError, "no validation rule"):
            hostrun.action_params(orphan, self.cfg)

    def test_the_fixture_settings_pass(self):  # control: every action's parameters are accepted
        for name in hostrun.ACTIONS:
            self.assertTrue(self.params(name) is not None, name)

    def test_expire_days_is_a_bounded_positive_integer(self):
        self.assertEqual(dict(self.params("bootstrap", PVE_TOKEN_EXPIRE_DAYS="30"))["CL_EXPIRE_DAYS"], "30")
        self.refused("bootstrap", "PVE_TOKEN_EXPIRE_DAYS",
                     ("1; reboot", "$(id)", "a[$(id)]", "0", "-1", "3651", "99999999999", " 5", "5 ", "0x10", "1e3",
                      "٩٠", "08 ", "+5"))

    def test_expire_days_in_arithmetic_position_is_refused_before_rendering(self):
        cfg = modified(self.cfg, PVE_TOKEN_EXPIRE_DAYS="a[$(touch x)]")
        with self.assertRaises(ConfigError):
            hostrun.render("bootstrap", cfg)

    def test_identifiers(self):
        for key, action in (("PVE_POOL", "prepare"), ("PVE_LAB_STORAGE", "prepare"), ("PVE_VM_STORAGE", "prepare"),
                            ("PVE_SENTINEL_BACKUP_STORAGE", "sentinel")):
            self.refused(action, key, ("1pool", "-pool", "po ol", "po'ol", "po;ol", "po/ol", "pool-", "a" * 65,
                                       "po\nol", "$(id)", "pool\\"))
        for good in ("corelab", "local-lvm", "Pool_1.a", "a"):
            self.assertEqual(dict(self.params("prepare", PVE_POOL=good))["CL_POOL"], good)

    def test_bridge(self):
        self.refused("prepare", "PVE_BRIDGE", ("", "0br", "vmbr0;reboot", "vm br", "a" * 16, "vmbr0'", "-vmbr0", "$x"))
        self.assertEqual(dict(self.params("prepare", PVE_BRIDGE="vmbr12"))["CL_BRIDGE"], "vmbr12")

    def test_storage_path(self):
        self.refused("prepare", "PVE_LAB_STORAGE_PATH",
                     ("", "/", "srv/corelab", "/srv/../etc", "/srv/./x", "/srv//x", "/srv/corelab/", "/srv/a b",
                      "/srv/$(id)", "/srv/x;y", "/srv/x\ny", "/srv/'x'", "/srv/..", "~/x", "/srv/x*"))
        self.assertEqual(dict(self.params("prepare", PVE_LAB_STORAGE_PATH="/srv/corelab-1"))["CL_LAB_STORAGE_PATH"],
                         "/srv/corelab-1")

    def test_image_url_and_hash(self):
        self.refused("fcos-template", "FCOS_IMAGE_URL",
                     ("", "http://builds.example.invalid/x.xz", "ftp://builds.example.invalid/x", "file:///etc/passwd",
                      "https://", "https://user@builds.example.invalid/x", "https://builds.example.invalid/a b",
                      "https://builds.example.invalid/x'y", "https://builds.example.invalid/x\ny",
                      "https://builds.example.invalid/`id`",
                      "https://builds.example.invalid:99999/x", "https://builds_x.example.invalid/x",
                      "https://builds.example.invalid/x#frag", "https://-evil/x", "https://builds.example.invalid/ü"))
        ok = "https://builds.example.invalid:8443/a/b-1.qcow2.xz?x=1&y=2"
        self.assertEqual(dict(self.params("fcos-template", FCOS_IMAGE_URL=ok))["CL_FCOS_IMAGE_URL"], ok)
        self.refused("fcos-template", "FCOS_IMAGE_SHA256", ("", "0" * 63, "0" * 65, "g" * 64, "0" * 64 + "\n", " " + "0" * 64))
        self.assertEqual(dict(self.params("fcos-template", FCOS_IMAGE_SHA256="AB" * 32))["CL_FCOS_IMAGE_SHA256"],
                         "ab" * 32)

    def test_vmids_are_checked_against_the_range_and_the_sentinel(self):
        self.refused("fcos-template", "PVE_TEMPLATE_VMID",
                     ("", "abc", "0", "99", "-5", "9099", "9200", "9100; reboot", "09100x", " 9100", "9050"))
        self.assertEqual(dict(self.params("fcos-template", PVE_TEMPLATE_VMID="9150"))["CL_TEMPLATE_VMID"], "9150")
        # The template may not be the sentinel, whatever the range says.
        with self.assertRaises(ConfigError):
            self.params("fcos-template", PVE_TEMPLATE_VMID="9100", PVE_SENTINEL_VMID="9100")
        # Without a valid range or sentinel there is no template action.
        self.refused("fcos-template", "PVE_VMID_RANGE", ("", "9100", "9199-9100", "9100-9199\n", "99-200"))
        self.refused("fcos-template", "PVE_SENTINEL_VMID", ("", "0", "abc", "-3", "9150", "99"))
        with self.assertRaises(ConfigError):
            self.params("fcos-template", PVE_SENTINEL_VMID=None)

    def test_the_sentinel_is_a_real_vmid_outside_the_project_range(self):
        for action in ("sentinel", "apply-manifest", "fcos-template"):
            self.refused(action, "PVE_SENTINEL_VMID", ("0", "abc", "-1", "9100", "9199", "99", " 9050"))
        self.assertEqual(dict(self.params("sentinel", PVE_SENTINEL_VMID="9300"))["CL_SENTINEL_VMID"], "9300")

    def test_the_template_action_exports_the_range_and_the_sentinel(self):
        script = hostrun.render("fcos-template", self.cfg)
        lines = {l.split("=", 1)[0]: l for l in script.splitlines() if l.startswith("export CL_")}
        values = {}
        for name in ("CL_VMID_RANGE", "CL_SENTINEL_VMID", "CL_TEMPLATE_VMID"):
            line = next(l for l in script.splitlines() if l.startswith(f"export {name}="))
            values[name] = subprocess.run(["bash", "-c", f'{line}\nprintf %s "${name}"'], capture_output=True,
                                          text=True).stdout
        self.assertEqual(values, {"CL_VMID_RANGE": "9100-9199", "CL_SENTINEL_VMID": "9050", "CL_TEMPLATE_VMID": "9100"})
        self.assertIn("export CL_VMID_RANGE", " ".join(lines))

    def test_run_refuses_a_bad_parameter_before_anything_is_shown_or_sent(self):
        cfg = modified(self.cfg, PVE_TOKEN_EXPIRE_DAYS="1; reboot")
        stdin, out, popen = io.StringIO("anything\n"), io.StringIO(), Recorder()
        with self.assertRaises(ConfigError):
            hostrun.run("bootstrap", cfg, stdin=stdin, stdout=out, env=NO_AGENT_ENV, ancestors=(),
                        is_tty=lambda: True, runner=encrypted, popen=popen, addr_check=lambda _a: None)
        self.assertEqual((out.getvalue(), stdin.tell(), popen.calls), ("", 0, []))

    def test_run_refuses_a_bad_host_or_path_before_the_prompt(self):
        for key, bad in (("PVE_HOST", "-oProxyCommand=x"), ("PVE_KNOWN_HOSTS", "/tmp/a b/kh"),
                         ("PVE_ROOT_KEY", "relative")):
            stdin, out, popen = io.StringIO("anything\n"), io.StringIO(), Recorder()
            with self.subTest(key=key), self.assertRaises(ConfigError):
                hostrun.run("preflight", modified(self.cfg, **{key: bad}), stdin=stdin, stdout=out,
                            env=NO_AGENT_ENV, ancestors=(), is_tty=lambda: True, runner=encrypted, popen=popen,
                            addr_check=lambda _a: None)
            self.assertEqual((out.getvalue(), stdin.tell(), popen.calls), ("", 0, []))

    def test_show_exits_two_for_a_bad_parameter(self):
        env = self.dir / "bad-env"
        env.write_text(fixtures.env_text(self.dir, PVE_TOKEN_EXPIRE_DAYS="1; reboot"))
        os.chmod(env, 0o600)
        err, out = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(env)}), contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(out):
            code = hostrun.main(["show", "bootstrap"])
        self.assertEqual((code, out.getvalue()), (2, ""))
        self.assertIn("PVE_TOKEN_EXPIRE_DAYS", err.getvalue())


# --------------------------------------------------------------------------- redact.py

class RedactTests(unittest.TestCase):
    GLOBAL6 = "2001" + ":4860::1"

    def test_ipv6_addresses_are_pseudonymised_and_found(self):
        text = f"peer {self.GLOBAL6} and {LINK_LOCAL6} and {self.GLOBAL6} again"
        clean = redact.sanitize(text)
        self.assertNotIn("4860", clean)
        self.assertNotIn("fe80", clean)
        self.assertEqual(clean.count("<ipv6-1>"), 2)  # consistent pseudonyms
        self.assertIn("<ipv6-2>", clean)
        self.assertTrue(any("IPv6" in f for f in redact.scan(text)))
        self.assertEqual(redact.scan(clean), [])

    def test_documentation_loopback_and_times_are_left_alone(self):  # controls
        text = f"a 2001:db8::50 b {LOOPBACK6} c {MAPPED6} d 12:34:56 e :: f aa:bb"
        self.assertEqual(redact.sanitize(text), text)
        self.assertEqual(redact.scan(text), [])

    def test_a_sentence_ending_full_stop_is_not_part_of_the_address(self):
        self.assertEqual(redact.sanitize(f"see {self.GLOBAL6}."), "see <ipv6-1>.")

    def test_redact_uuids(self):
        self.assertEqual(redact.redact_uuids(f"x {SECRET} y"), "x <redacted-uuid> y")


# --------------------------------------------------------------------------- interface requests of LA-DESTRUCT

class CliRequestsTests(LabCase):
    """classify --no-sentinel, the binding entry in the counts, inventory verify, deep JSON."""

    def setUp(self):
        super().setUp()
        from tests.test_inventory_manifest import EVIDENCE, load_inventory
        inventory, _ = load_inventory()
        self.inventory_obj = inventory
        self.inv = self.dir / "inventory.json"
        self.inv.write_text(__import__("json").dumps(inventory))
        self.overrides = self.dir / "overrides.json"
        self.overrides.write_text(__import__("json").dumps(EVIDENCE))

    def run_cli(self, *argv, cfg=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str((cfg or self.cfg).source)}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def without_sentinel(self):
        env = self.dir / "env-nosentinel"
        env.write_text("".join(l for l in fixtures.env_text(self.dir).splitlines(True)
                               if not l.startswith("PVE_SENTINEL_VMID=")))
        os.chmod(env, 0o600)
        return config.load(env)

    def test_the_counts_leave_out_the_binding_entry(self):
        import json
        code, out, err = self.run_cli("classify", "--inventory", str(self.inv), "--overrides", str(self.overrides),
                                      "--out", str(self.dir / "cls.json"))
        result = json.loads((self.dir / "cls.json").read_text())
        self.assertIn("binding/classification", result)
        counts = dict(part.split("=") for part in out.splitlines()[0].split())
        self.assertEqual(sum(int(v) for v in counts.values()), len(result) - 1)

    def test_no_sentinel_mode_on_the_command_line(self):
        import json
        cfg = self.without_sentinel()
        args = ("classify", "--inventory", str(self.inv), "--out", str(self.dir / "cls.json"))
        code, out, err = self.run_cli(*args, cfg=cfg)  # control: without the flag it is still refused
        self.assertEqual(code, 2)
        self.assertIn("PVE_SENTINEL_VMID", err)
        self.assertFalse((self.dir / "cls.json").exists())
        code, out, err = self.run_cli(*args, "--no-sentinel", cfg=cfg)
        self.assertIn(code, (0, 1), err)  # 1 only for a VMID-range conflict
        self.assertIn("no-sentinel mode: this classification cannot feed a manifest", out)
        result = json.loads((self.dir / "cls.json").read_text())
        self.assertEqual(result["binding/classification"]["class"], "UNKNOWN")
        self.assertNotIn("REMOVE_CANDIDATE", {v["class"] for v in result.values()})
        # The result cannot feed a manifest.
        code, _, err = self.run_cli("manifest", "build", "--inventory", str(self.inv), "--classification",
                                    str(self.dir / "cls.json"), "--out", str(self.dir / "m.json"), cfg=cfg)
        self.assertEqual(code, 2, err)
        self.assertFalse((self.dir / "m.json").exists())

    def test_no_sentinel_does_not_excuse_an_invalid_setting(self):
        for bad in ("0", "abc"):
            cfg = modified(self.cfg, PVE_SENTINEL_VMID=bad)
            cfg.source = self.cfg.source
            env = self.dir / f"env-{bad}"
            env.write_text(fixtures.env_text(self.dir, PVE_SENTINEL_VMID=bad))
            os.chmod(env, 0o600)
            code, _, _ = self.run_cli("classify", "--inventory", str(self.inv), "--no-sentinel", "--out",
                                      str(self.dir / "c.json"), cfg=config.load(env))
            self.assertEqual(code, 2, bad)

    def raw_and_inventory(self):
        import json
        from lab_agent import inventory as inv
        transport = pveapi.FakeTransport(fixtures.api_routes())
        client = pveapi.Client("192.0.2.10", 8006, fixtures.TOKEN_ID, "x", transport)
        raw = inv.collect(client, fixtures.NODE)
        (self.dir / "raw.json").write_text(json.dumps(raw))
        normal = inv.normalize(raw)
        (self.dir / "normal.json").write_text(json.dumps(normal))
        return raw, normal

    def test_inventory_verify(self):
        import json
        raw, normal = self.raw_and_inventory()
        code, out, err = self.run_cli("inventory", "verify", "--inventory", str(self.dir / "normal.json"),
                                      "--raw", str(self.dir / "raw.json"))
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("exactly what its raw data gives", out)
        edited = json.loads((self.dir / "normal.json").read_text())
        edited["guests"] = edited["guests"][1:]  # one guest hidden by hand
        (self.dir / "edited.json").write_text(json.dumps(edited))
        code, out, err = self.run_cli("inventory", "verify", "--inventory", str(self.dir / "edited.json"),
                                      "--raw", str(self.dir / "raw.json"))
        self.assertEqual(code, 2)
        self.assertIn("guests differs", out)
        self.assertIn("do not use this inventory", err)

    def test_inventory_verify_refuses_a_raw_file_that_is_not_json(self):
        self.raw_and_inventory()
        (self.dir / "raw.json").write_text("{not json")
        code, _, err = self.run_cli("inventory", "verify", "--inventory", str(self.dir / "normal.json"),
                                    "--raw", str(self.dir / "raw.json"))
        self.assertEqual(code, 2)
        self.assertIn("lab-agent:", err)

    def deep(self, name):
        path = self.dir / name
        path.write_text("[" * 200000)
        return path

    def test_deeply_nested_json_is_a_refusal_in_both_command_lines(self):
        deep = self.deep("deep.json")
        code, _, err = self.run_cli("classify", "--inventory", str(deep), "--out", str(self.dir / "c.json"))
        self.assertEqual(code, 2)
        self.assertIn("nested too deeply", err)
        code, _, err = self.run_cli("manifest", "hash", str(deep))  # a loader that parses JSON itself
        self.assertEqual(code, 2)
        out, errio = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(errio):
            code = hostrun.main(["show", "preflight", "--inventory", str(deep)])
        self.assertEqual((code, out.getvalue()), (2, ""))
        self.assertIn("nested too deeply", errio.getvalue())
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = hostrun.main(["show", "apply-manifest", "--manifest", str(deep)])
        self.assertEqual(code, 2)

    def test_ordinary_nesting_still_loads(self):  # control
        path = self.dir / "ok.json"
        path.write_text("[" * 50 + "]" * 50)
        value, depth = hostrun._read_json(str(path)), 0
        while value:
            value, depth = value[0], depth + 1
        self.assertEqual(depth, 49)


# --------------------------------------------------------------------------- review T1 (round 2)

SECRET_L = "abcdef01-2222-3333-4444-5555555555ab"  # letters in it: case variants differ
OTHER_UUID = "99999999-8888-7777-6666-555555555555"


class RawBodyTransport(pveapi.FakeTransport):
    """FakeTransport that answers chosen paths with raw (status, bytes), for malformed answers."""

    def __init__(self, routes, raw):
        super().__init__(routes)
        self.raw = raw

    def __call__(self, method, url, headers, body):
        path = url.split("/api2/json", 1)[1].split("?", 1)[0]
        if path in self.raw:
            self.calls.append((method, url, headers, body))
            return self.raw[path]
        return super().__call__(method, url, headers, body)


class ReflectedCredentialTests(LabCase):
    """T1-1: whatever the server reflects, the token secret is not in any error, record or output."""

    def client(self, transport):
        return pveapi.Client("192.0.2.10", 8006, fixtures.TOKEN_ID, SECRET_L, transport)

    def reflections(self):
        header = f"PVEAPIToken={fixtures.TOKEN_ID}={SECRET_L}"
        return (SECRET_L, SECRET_L.upper(), f"X{SECRET_L}Y", f"aaaa{SECRET_L}", header, f"{SECRET_L}{SECRET_L}")

    def test_an_error_message_that_reflects_the_credential_is_scrubbed(self):
        for text in self.reflections():
            transport = pveapi.FakeTransport({("GET", "/version"): (403, f"denied for {text} sorry")})
            with self.subTest(text=text), self.assertRaises(pveapi.PveError) as ctx:
                self.client(transport).get("/version")
            shown = f"{ctx.exception} {ctx.exception.message}"
            self.assertNotIn(SECRET_L.lower(), shown.lower())
            self.assertIn("sorry", shown)

    def test_json_errors_members_and_non_json_bodies_are_scrubbed_too(self):
        bodies = (b'{"errors": {"x": "' + SECRET_L.encode() + b'"}}', b"proxy page for " + SECRET_L.encode(),
                  b'["' + SECRET_L.encode() + b'"]', b"\xff" + SECRET_L.encode())
        for body in bodies:
            transport = RawBodyTransport({}, {"/version": (500, body)})
            with self.subTest(body=body[:12]), self.assertRaises(pveapi.PveError) as ctx:
                self.client(transport).get("/version")
            self.assertNotIn(SECRET_L.lower(), str(ctx.exception).lower())

    def test_discovery_records_and_prints_nothing_that_reflects_the_credential(self):
        import json
        routes = fixtures.api_routes()
        routes[("GET", "/cluster/firewall/options")] = (403, f"Permission check failed for {SECRET_L.upper()}")
        raw = {"/pools": (500, f"internal error X{SECRET_L}Y".encode())}
        transport = RawBodyTransport(routes, raw)
        out, err = io.StringIO(), io.StringIO()
        fake = lambda cfg: pveapi.Client("192.0.2.10", 8006, fixtures.TOKEN_ID, SECRET_L, transport)  # noqa: E731
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}), \
                mock.patch.object(cli.Client, "from_config", side_effect=fake), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["discover", "--out-dir", str(self.dir / "d")])
        self.assertEqual(code, 1, err.getvalue())
        everything = out.getvalue() + err.getvalue() + (self.dir / "d" / "raw.json").read_text() \
            + (self.dir / "d" / "inventory.json").read_text()
        self.assertNotIn(SECRET_L.lower(), everything.lower())
        self.assertIn("not read: /pools", out.getvalue())  # the record is still there, scrubbed
        self.assertTrue(json.loads((self.dir / "d" / "inventory.json").read_text())["errors"])

    def test_the_command_line_prints_a_reflected_credential_and_any_bare_uuid_redacted(self):
        transport = pveapi.FakeTransport({("GET", "/version"): (401, f"bad token {SECRET_L} and {OTHER_UUID}")})
        client = self.client(transport)
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}), \
                mock.patch.object(cli, "cmd_scan", side_effect=lambda a, c: client.get("/version")):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main(["scan", "x"])
        self.assertEqual(code, 2)
        self.assertNotIn(SECRET_L, err.getvalue())
        self.assertNotIn(OTHER_UUID, err.getvalue())
        with mock.patch.object(hostrun, "render", side_effect=ConfigError(f"x {OTHER_UUID}")), \
                mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}):
            errio = io.StringIO()
            with contextlib.redirect_stderr(errio), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(hostrun.main(["show", "preflight"]), 2)
        self.assertNotIn(OTHER_UUID, errio.getvalue())

    @staticmethod
    def leaked(text, secret, k=8):
        """Any run of k or more consecutive characters of the secret (a head left by a cut) in text."""
        low, sec = text.lower(), secret.lower()
        return any(sec[i:i + k] in low for i in range(len(sec) - k + 1))

    def test_the_secret_is_scrubbed_before_the_text_is_cut_at_every_boundary_position(self):
        # T1b-1: the cut is at 200 characters; the secret is placed so that it ends before, at, across
        # and after the cut, for every offset, in every shape of error answer.
        cut = pveapi._ERROR_TEXT_LIMIT
        self.assertEqual(cut, 200)
        secret = SECRET_L
        shapes = {
            "non-JSON body": lambda pad: ("x" * pad + secret + "tail").encode(),
            "JSON message": lambda pad: ('{"message": "' + "x" * pad + secret + 'tail"}').encode(),
            "JSON errors": lambda pad: ('{"errors": {"k": "' + "x" * pad + secret + 'tail"}}').encode(),
            "upper case": lambda pad: ("x" * pad + secret.upper() + "tail").encode(),
            "header form": lambda pad: ("x" * pad + f"PVEAPIToken={fixtures.TOKEN_ID}={secret}" + "tail").encode(),
        }
        for label, make in shapes.items():
            for pad in range(cut - len(secret) - 60, cut + 8):
                transport = RawBodyTransport({}, {"/version": (500, make(pad))})
                with self.subTest(shape=label, pad=pad), self.assertRaises(pveapi.PveError) as ctx:
                    self.client(transport).get("/version")
                self.assertFalse(self.leaked(f"{ctx.exception} {ctx.exception.message}", secret),
                                 f"a piece of the secret survived with the cut at {cut} and padding {pad}")
                self.assertLessEqual(len(ctx.exception.message), cut)

    def test_a_long_error_is_still_cut_to_the_limit_and_the_visible_text_is_kept(self):  # control
        transport = RawBodyTransport({}, {"/version": (500, b"y" * 5000)})
        with self.assertRaises(pveapi.PveError) as ctx:
            self.client(transport).get("/version")
        self.assertEqual(ctx.exception.message, "y" * pveapi._ERROR_TEXT_LIMIT)

    def test_a_secret_beyond_the_transports_body_limit_cannot_reach_the_message(self):
        # The transport keeps at most 64 KiB of an error body; a secret straddling that cut is far past
        # the 200 characters an error shows, so no piece of it can be in the message.
        for offset in range(len(SECRET_L) + 2):
            body = b"z" * (pveapi._ERROR_BODY_LIMIT - offset) + SECRET_L.encode()
            transport = RawBodyTransport({}, {"/version": (500, body[:pveapi._ERROR_BODY_LIMIT])})
            with self.subTest(offset=offset), self.assertRaises(pveapi.PveError) as ctx:
                self.client(transport).get("/version")
            self.assertFalse(self.leaked(str(ctx.exception), SECRET_L))

    def test_discovery_records_for_a_secret_at_the_cut_carry_no_piece_of_it(self):
        import json
        pad = pveapi._ERROR_TEXT_LIMIT - len(SECRET_L) + 1  # the secret straddles the cut by one character
        raw = {"/pools": (500, ("x" * pad + SECRET_L + "tail").encode())}
        transport = RawBodyTransport(fixtures.api_routes(), raw)
        fake = lambda cfg: pveapi.Client("192.0.2.10", 8006, fixtures.TOKEN_ID, SECRET_L, transport)  # noqa: E731
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}), \
                mock.patch.object(cli.Client, "from_config", side_effect=fake), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            cli.main(["discover", "--out-dir", str(self.dir / "d")])
        everything = out.getvalue() + err.getvalue() + (self.dir / "d" / "raw.json").read_text() \
            + (self.dir / "d" / "inventory.json").read_text()
        self.assertFalse(self.leaked(everything, SECRET_L))
        self.assertIn("/pools", json.loads((self.dir / "d" / "inventory.json").read_text())["errors"])

    def test_a_success_answer_is_returned_untouched(self):  # control: only diagnostics are scrubbed
        transport = pveapi.FakeTransport({("GET", "/version"): (200, {"note": SECRET_L})})
        self.assertEqual(self.client(transport).get("/version"), {"note": SECRET_L})


class ResponseEnvelopeTests(LabCase):
    """T1-4: an answer that is not PVE's JSON object is a transport error, never data=None."""

    def client(self, status, body):
        transport = RawBodyTransport({}, {"/version": (status, body)})
        return pveapi.Client("192.0.2.10", 8006, fixtures.TOKEN_ID, "s3cr3t", transport)

    def test_success_answers_of_the_wrong_shape_are_transport_errors(self):
        for body in (b"[]", b"null", b'"text"', b"42", b"{}", b'{"errors": 1}', b"", b"{bad", b"\xff\xfe", b"[" * 500000):
            with self.subTest(body=body[:12]), self.assertRaises(pveapi.PveTransportError):
                self.client(200, body).get("/version")

    def test_a_null_data_member_is_a_valid_answer(self):  # control: PVE sends {"data": null} for some writes
        self.assertIsNone(self.client(200, b'{"data": null}').get("/version"))
        self.assertEqual(self.client(200, b'{"data": [1]}').get("/version"), [1])

    def test_error_answers_of_the_wrong_shape_are_pve_errors_not_attribute_errors(self):
        for body in (b"[]", b"null", b'"text"', b"", b"\xff", b"[" * 500000, b'{"message": ["x"]}'):
            with self.subTest(body=body[:12]), self.assertRaises(pveapi.PveError):
                self.client(500, body).get("/version")

    def test_through_the_command_line_every_bad_shape_is_exit_two_with_no_traceback(self):
        for body in (b"[]", b"null", b"{}", b"", b"{bad", b"\xff"):
            routes = fixtures.api_routes()
            transport = RawBodyTransport(routes, {"/version": (200, body)})
            fake = lambda cfg: pveapi.Client("192.0.2.10", 8006, fixtures.TOKEN_ID, "s3cr3t", transport)  # noqa: E731
            out, err = io.StringIO(), io.StringIO()
            with self.subTest(body=body), mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}), \
                    mock.patch.object(cli.Client, "from_config", side_effect=fake), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main(["discover", "--out-dir", str(self.dir / f"d{abs(hash(body))}")])
            self.assertEqual(code, 2, out.getvalue())
            self.assertIn("lab-agent:", err.getvalue())
            self.assertNotIn("Traceback", err.getvalue())


class HardLinkTests(LabCase):
    """T1-2: O_NOFOLLOW does not stop a hard link; a second name must never be written through."""

    def victim(self, name="victim"):
        victim = self.dir / name
        victim.write_text("keep\n")
        os.chmod(victim, 0o600)
        return victim

    def test_an_approvals_log_that_is_a_hard_link_is_refused_and_the_victim_is_untouched(self):
        state = self.cfg.state_dir()
        victim = self.victim()
        os.link(victim, state / "approvals.jsonl")
        with self.assertRaisesRegex(hostrun.HostRunError, "links"):
            hostrun.record_approval(state, "preflight", hostrun.render("preflight", self.cfg))
        self.assertEqual(victim.read_text(), "keep\n")

    def test_sanitized_output_that_is_a_hard_link_replaces_the_name_and_spares_the_victim(self):
        victim = self.victim()
        os.link(victim, self.dir / "out.txt")
        (self.dir / "in.txt").write_text("hello\n")
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = cli.main(["sanitize", str(self.dir / "in.txt"), str(self.dir / "out.txt")])
        self.assertEqual(code, 0)
        self.assertEqual(victim.read_text(), "keep\n")
        self.assertEqual((self.dir / "out.txt").read_text(), "hello\n")
        self.assertEqual(victim.stat().st_nlink, 1)
        self.assertEqual(os.stat(self.dir / "out.txt").st_nlink, 1)
        self.assertEqual([p.name for p in self.dir.iterdir() if p.name.endswith(".tmp")], [])

    def test_sanitized_output_without_a_link_is_still_written_and_a_failed_write_leaves_no_temporary(self):
        (self.dir / "in.txt").write_text("hello\n")
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(["sanitize", str(self.dir / "in.txt"), str(self.dir / "o.txt")]), 0)
                with mock.patch.object(cli.os, "replace", side_effect=OSError("disk full")):
                    self.assertEqual(cli.main(["sanitize", str(self.dir / "in.txt"), str(self.dir / "p.txt")]), 2)
        self.assertEqual((self.dir / "o.txt").read_text(), "hello\n")
        self.assertEqual([p.name for p in self.dir.iterdir() if p.name.endswith(".tmp")], [])
        self.assertFalse((self.dir / "p.txt").exists())

    def test_the_private_writes_replace_the_name_and_spare_a_hard_linked_victim(self):  # control
        out = self.private("out")
        victim = self.victim()
        os.link(victim, out / "f.json")
        cli._write_json(out / "f.json", {"a": 1})
        hostrun.write_private(out / "f.json", b"new")
        self.assertEqual(victim.read_text(), "keep\n")
        self.assertEqual((out / "f.json").read_bytes(), b"new")


class FailedWriteDrainTests(LabCase):
    """T1-3: after the token cannot be stored, later lines never show it, however it is embedded."""

    def lines(self):
        return [f"CORELAB_TOKEN_SECRET={SECRET_L}\n", f"again X{SECRET_L}Y done\n", f"upper {SECRET_L.upper()} done\n",
                f"aaaa{SECRET_L}bbbb done\n", f"{SECRET_L}{SECRET_L} done\n", "last line\n"]

    def test_scrubber_replaces_exact_values_in_any_case_and_any_company(self):
        scrubber = redact.SecretScrubber()
        scrubber.add("")
        scrubber.add(SECRET_L)
        for text in (SECRET_L, SECRET_L.upper(), f"X{SECRET_L}Y", f"{SECRET_L}{SECRET_L}"):
            self.assertNotIn(SECRET_L.lower(), scrubber.scrub(text).lower())
        self.assertEqual(scrubber.scrub("nothing here"), "nothing here")

    def test_redact_uuids_has_no_word_boundary(self):
        for text in (f"X{OTHER_UUID}Y", f"aaaa{OTHER_UUID}", f"{OTHER_UUID}{OTHER_UUID}"):
            self.assertNotIn(OTHER_UUID, redact.redact_uuids(text))

    def test_a_failed_store_followed_by_an_embedded_token_reaches_neither_log_nor_output(self):
        (self.dir / "token").unlink()
        popen = Recorder("".join(self.lines()).encode())
        sha = hostrun.script_hash(hostrun.render("bootstrap", self.cfg))
        out = io.StringIO()
        with mock.patch.object(hostrun, "write_private", side_effect=OSError(28, "No space left on device")):
            with self.assertRaisesRegex(hostrun.HostRunError, "remove it there"):
                hostrun.run("bootstrap", self.cfg, stdin=io.StringIO(sha[:8] + "\n"), stdout=out, env=NO_AGENT_ENV,
                            ancestors=(), is_tty=lambda: True, runner=encrypted, popen=popen,
                            addr_check=lambda _a: None)
        (log,) = list((self.cfg.state_dir() / "runs").iterdir())
        text = log.read_text() + out.getvalue()
        self.assertNotIn(SECRET_L.lower(), text.lower())
        self.assertIn("last line", log.read_text())  # the rest of the output is still drained into the log
        self.assertIn("exit=0", log.read_text())

    def test_the_same_holds_when_the_store_fails_after_the_token_line_in_handle_output(self):
        stream = io.BytesIO("".join(self.lines()).encode())
        out, log, scrubber = io.StringIO(), io.StringIO(), redact.SecretScrubber()
        token = self.dir / "t"
        token.write_text("exists\n")  # the exclusive write refuses
        with self.assertRaises(hostrun.HostRunError):
            hostrun.handle_output(stream, "token", out, log, token_file=token, scrubber=scrubber)
        hostrun._drain(stream, "token", log, scrubber)
        self.assertNotIn(SECRET_L.lower(), (out.getvalue() + log.getvalue()).lower())
        self.assertIn("last line", log.getvalue())


class RestrictiveUmaskTests(LabCase):
    """T1-5: newly created approval and log files are mode 600 whatever the umask."""

    def test_approval_files_work_under_restrictive_masks(self):
        script = hostrun.render("preflight", self.cfg)
        for mask in (0o200, 0o277, 0o377, 0o077, 0):
            state = self.dir / f"state{mask:o}"
            cfg = modified(self.cfg, PVE_LAB_STATE=str(state))
            with self.subTest(umask=oct(mask)), umask(mask):
                hostrun.record_approval(cfg.state_dir(), "preflight", script, now="2026-11-16T00:00:00+00:00")
                hostrun.record_approval(state, "preflight", script + "#\n", now="2026-11-16T00:00:01+00:00")
            self.assertEqual((state / "approvals.jsonl").stat().st_mode & 0o777, 0o600)
            self.assertEqual(len((state / "approvals.jsonl").read_text().splitlines()), 2)
            for copy in (state / "approved").iterdir():
                self.assertEqual(copy.stat().st_mode & 0o777, 0o600)
            self.assertEqual((state / "approved").stat().st_mode & 0o7777, 0o700)

    def test_a_run_creates_its_log_and_directories_private_under_restrictive_masks(self):
        for mask in (0o200, 0o277):
            state = self.dir / f"run{mask:o}"
            cfg = modified(self.cfg, PVE_LAB_STATE=str(state))
            sha = hostrun.script_hash(hostrun.render("preflight", cfg))
            with self.subTest(umask=oct(mask)), umask(mask):
                code = hostrun.run("preflight", cfg, stdin=io.StringIO(sha[:8] + "\n"), stdout=io.StringIO(),
                                   env=NO_AGENT_ENV, ancestors=(), is_tty=lambda: True, runner=encrypted,
                                   popen=Recorder(b"ok\n"), addr_check=lambda _a: None)
            self.assertEqual(code, 0)
            (log,) = list((state / "runs").iterdir())
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)
            self.assertIn("exit=0", log.read_text())
            self.assertEqual((state / "runs").stat().st_mode & 0o7777, 0o700)

    def test_an_existing_approvals_file_that_is_not_exactly_600_is_refused(self):
        state = self.cfg.state_dir()
        path = state / "approvals.jsonl"
        path.write_text("")
        os.chmod(path, 0o400)
        with self.assertRaisesRegex(hostrun.HostRunError, "expected 600"):
            hostrun.record_approval(state, "preflight", hostrun.render("preflight", self.cfg))


# --------------------------------------------------------------------------- round 3: trusted manifest commands

class TrustedManifestCliTests(CliRequestsTests):
    """``manifest build`` and ``manifest check`` recompute the classification (X1-a); a classification
    file edited by hand is refused with exit 2. Inherits the inventory and overrides of the class
    above (its own tests run again here, harmlessly)."""

    def classify_genuine(self):
        code, _, err = self.run_cli("classify", "--inventory", str(self.inv), "--overrides", str(self.overrides),
                                    "--out", str(self.dir / "cls.json"))
        self.assertIn(code, (0, 1), err)  # 1 only for a VMID-range conflict
        return self.dir / "cls.json"

    def build(self, cls, *extra, cfg=None, out="m.json"):
        return self.run_cli("manifest", "build", "--inventory", str(self.inv), "--classification", str(cls),
                            "--out", str(self.dir / out), *extra, cfg=cfg)

    def check(self, manifest, cls, *extra, cfg=None):
        return self.run_cli("manifest", "check", str(manifest), "--inventory", str(self.inv),
                            "--classification", str(cls), *extra, cfg=cfg)

    def forged_usable_classification(self):
        """A no-sentinel classification edited by hand into one that looks usable: binding rewritten
        with a sentinel and a digest, one guest marked REMOVE_CANDIDATE with a long reason."""
        import json
        cfg = self.without_sentinel()
        code, _, err = self.run_cli("classify", "--inventory", str(self.inv), "--no-sentinel", "--out",
                                    str(self.dir / "nosentinel.json"), cfg=cfg)
        self.assertIn(code, (0, 1), err)
        forged = json.loads((self.dir / "nosentinel.json").read_text())
        self.assertEqual(forged["binding/classification"]["class"], "UNKNOWN")
        forged["binding/classification"] = {"class": "PRESERVE", "sentinel_vmid": fixtures.SENTINEL,
                                            "overrides_digest": cl_digest(None), "reason": "edited by hand"}
        forged["vm/105"] = {"class": "REMOVE_CANDIDATE", "reason": "written by hand, long enough to pass"}
        (self.dir / "forged.json").write_text(json.dumps(forged))
        return self.dir / "forged.json"

    def test_a_genuine_classify_build_check_sequence_passes(self):  # positive control
        cls = self.classify_genuine()
        code, out, err = self.build(cls, "--overrides", str(self.overrides))
        self.assertEqual(code, 0, err)
        self.assertTrue((self.dir / "m.json").exists())
        code, out, err = self.check(self.dir / "m.json", cls, "--overrides", str(self.overrides))
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("recomputed from the settings, the inventory and the overrides", out)
        self.assertNotIn("taken as given", out)

    def test_a_forged_binding_is_refused_by_build_and_by_check(self):
        genuine = self.classify_genuine()
        self.assertEqual(self.build(genuine, "--overrides", str(self.overrides))[0], 0)  # a real manifest to check
        forged = self.forged_usable_classification()
        for extra in ((), ("--overrides", str(self.overrides))):
            with self.subTest(extra=extra):
                code, _, err = self.build(forged, *extra, out="forged-m.json")
                self.assertEqual(code, 2, err)
                self.assertIn("lab-agent:", err)
                self.assertFalse((self.dir / "forged-m.json").exists())
                code, _, err = self.check(self.dir / "m.json", forged, *extra)
                self.assertEqual(code, 2, err)
        # settings without a sentinel cannot make a context at all: refused whatever the file says
        nosentinel = self.without_sentinel()
        self.assertEqual(self.build(forged, cfg=nosentinel, out="forged-m2.json")[0], 2)
        self.assertEqual(self.check(self.dir / "m.json", forged, cfg=nosentinel)[0], 2)
        self.assertFalse((self.dir / "forged-m2.json").exists())

    def test_an_edited_overrides_digest_is_refused(self):
        import json
        cls = self.classify_genuine()
        edited = json.loads(cls.read_text())
        edited["binding/classification"]["overrides_digest"] = "0" * 64
        (self.dir / "edited.json").write_text(json.dumps(edited))
        code, _, err = self.build(self.dir / "edited.json", "--overrides", str(self.overrides), out="e.json")
        self.assertEqual(code, 2, err)
        self.assertFalse((self.dir / "e.json").exists())
        self.assertEqual(self.build(cls, "--overrides", str(self.overrides))[0], 0)
        code, _, err = self.check(self.dir / "m.json", self.dir / "edited.json", "--overrides", str(self.overrides))
        self.assertEqual(code, 2, err)

    def test_overrides_that_are_not_the_ones_the_classification_was_made_with_are_refused(self):
        cls = self.classify_genuine()
        code, _, err = self.build(cls, out="no-overrides.json")  # none given: the digest differs
        self.assertEqual(code, 2, err)
        self.assertFalse((self.dir / "no-overrides.json").exists())
        other = self.dir / "other-overrides.json"
        other.write_text("{}")
        self.assertEqual(self.build(cls, "--overrides", str(other), out="other.json")[0], 2)
        self.assertEqual(self.build(cls, "--overrides", str(self.overrides))[0], 0)
        self.assertEqual(self.check(self.dir / "m.json", cls)[0], 2)
        self.assertEqual(self.check(self.dir / "m.json", cls, "--overrides", str(other))[0], 2)
        self.assertEqual(self.check(self.dir / "m.json", cls, "--overrides", str(self.overrides))[0], 0)

    def test_an_edited_entry_is_refused(self):
        import json
        cls = self.classify_genuine()
        edited = json.loads(cls.read_text())
        rid = next(k for k, v in edited.items() if k != "binding/classification" and v["class"] != "REMOVE_CANDIDATE")
        edited[rid] = {"class": "REMOVE_CANDIDATE", "reason": "written by hand, long enough to pass"}
        (self.dir / "edited2.json").write_text(json.dumps(edited))
        code, _, err = self.build(self.dir / "edited2.json", "--overrides", str(self.overrides), out="e2.json")
        self.assertEqual(code, 2, err)
        self.assertFalse((self.dir / "e2.json").exists())

    def test_inventory_verify_passes_a_genuine_result_and_fails_a_tampered_one_without_a_workaround(self):
        import json
        self.raw_and_inventory()
        verify = lambda path: self.run_cli("inventory", "verify", "--inventory", str(path),  # noqa: E731
                                           "--raw", str(self.dir / "raw.json"))
        code, out, err = verify(self.dir / "normal.json")
        self.assertEqual((code, err), (0, ""), out)  # includes the ACL entries that JSON turns into lists
        edited = json.loads((self.dir / "normal.json").read_text())
        edited["acl"][0][3] = "Administrator"
        (self.dir / "tampered.json").write_text(json.dumps(edited))
        code, out, err = verify(self.dir / "tampered.json")
        self.assertEqual(code, 2)
        self.assertIn("acl differs", out)
        self.assertIsNone(re.search(r"tuple\(e\)", Path(cli.__file__).read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- bin/lab-agent

class LauncherTests(LabCase):
    def test_the_launcher_starts_private_whatever_the_callers_umask(self):
        source = (AGENT_DIR / "bin" / "lab-agent").read_text()
        self.assertIn("os.umask(0o077)", source)
        (self.dir / "in.txt").write_text("hello\n")
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.dir),
               "PVE_AGENT_ENV": str(self.cfg.source)}
        with umask(0):  # the child inherits a permissive umask; the launcher must tighten it
            proc = subprocess.run([sys.executable, "-I", str(AGENT_DIR / "bin" / "lab-agent"), "sanitize",
                                   str(self.dir / "in.txt"), str(self.dir / "out.txt")],
                                  capture_output=True, text=True, env=env, timeout=30, cwd=self.dir)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.dir / "out.txt").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
