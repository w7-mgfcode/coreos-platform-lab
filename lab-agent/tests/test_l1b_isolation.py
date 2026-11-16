"""L1B LA-TRANSPORT round 2: the test-isolation guard (``tests/__init__.py``) and its proof.

Offline only. Nothing here connects anywhere: the guard raises before a system call, the positive
controls use AF_UNIX sockets in a temporary directory, socketpairs, fake connection classes and
stubs. Child processes are started only in the safe forms the guard allows (``ssh -G``, local
``git``, a stub first on PATH).

A test that proves the guard acknowledges its trips with ``expect_guard_trips()``; a test that
passes only because the guard raised is reported as a failure (``GuardDoesNotHideFailuresTests``).
"""

import ast
import contextlib
import http.client
import io
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import unittest
import urllib.request
import urllib.response
from pathlib import Path
from unittest import mock

import tests
from lab_agent import pveapi
from lab_agent.config import ConfigError
from tests import NetworkIsolationViolation, expect_guard_trips, fixtures
from tests.test_l1b_transport import FakeConnection, http_answer, modified

AGENT_DIR = Path(__file__).resolve().parent.parent
SECRET = "11111111-2222-3333-4444-555555555555"
TARGET = ("192.0.2.1", 9)  # documentation address: it is NOT isolation, the guard is


def untripped(testcase):
    """No unacknowledged trip may exist at the end of a test that is not about the guard."""
    testcase.assertEqual([t for t in tests.TRIPS if not t["acked"]], [])


class GuardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def assert_trips(self, fn, *args, **kwargs):
        """The call raises the guard's error (an AssertionError that is not an OSError), naming the
        rule; the trip is acknowledged. Returns what the guard recorded."""
        with expect_guard_trips() as seen:
            with self.assertRaises(NetworkIsolationViolation) as ctx:
                fn(*args, **kwargs)
        self.assertIsInstance(ctx.exception, AssertionError)
        self.assertNotIsInstance(ctx.exception, OSError)
        self.assertIn("TEST ISOLATION RULE", str(ctx.exception))
        return seen

    def unix_pair(self):
        path = str(self.dir / "s")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(server.close)
        server.bind(path)
        server.listen(1)
        return path, server


# --------------------------------------------------------------------------- sockets

class SocketEntryPointTests(GuardCase):
    def test_connect_is_refused_for_every_non_unix_family_and_a_control_succeeds(self):
        for family, address in ((socket.AF_INET, TARGET), (socket.AF_INET6, ("2001:db8::1", 9, 0, 0)),
                                (socket.AF_INET, ("pve.example.invalid", 9))):
            sock = socket.socket(family, socket.SOCK_STREAM)  # creating a socket is not network use
            self.addCleanup(sock.close)
            with self.subTest(family=family.name, address=address):
                seen = self.assert_trips(sock.connect, address)
                self.assertEqual(seen.entries, ["socket.connect"])
        path, server = self.unix_pair()  # control: the same call on AF_UNIX works
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(client.close)
        client.connect(path)
        conn, _ = server.accept()
        self.addCleanup(conn.close)
        client.sendall(b"x")
        self.assertEqual(conn.recv(1), b"x")
        untripped(self)

    def test_connect_ex_is_refused_not_answered_with_an_errno(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(sock.close)
        self.assertEqual(self.assert_trips(sock.connect_ex, TARGET).entries, ["socket.connect_ex"])
        path, server = self.unix_pair()  # control
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(client.close)
        self.assertEqual(client.connect_ex(path), 0)

    def test_sendto_is_refused_and_a_unix_datagram_control_succeeds(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sock.close)
        self.assertEqual(self.assert_trips(sock.sendto, b"x", TARGET).entries, ["socket.sendto"])
        self.assertEqual(self.assert_trips(sock.sendto, b"x", 0, TARGET).entries, ["socket.sendto"])
        path = str(self.dir / "d")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.addCleanup(server.close)
        server.bind(path)
        client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.addCleanup(client.close)
        client.sendto(b"hi", path)
        self.assertEqual(server.recv(2), b"hi")

    def test_sendmsg_is_refused_and_a_socketpair_control_succeeds(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sock.close)
        self.assertEqual(self.assert_trips(sock.sendmsg, [b"x"], [], 0, TARGET).entries, ["socket.sendmsg"])
        a, b = socket.socketpair()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        a.sendmsg([b"hi"])
        self.assertEqual(b.recv(2), b"hi")

    def test_send_and_sendall_are_refused_before_the_kernel_answers(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(sock.close)
        self.assertEqual(self.assert_trips(sock.send, b"x").entries, ["socket.send"])
        self.assertEqual(self.assert_trips(sock.sendall, b"x").entries, ["socket.sendall"])
        a, b = socket.socketpair()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        a.send(b"1")
        a.sendall(b"2")
        self.assertEqual(b.recv(2), b"12")

    def test_create_connection_is_refused_and_the_original_works_against_fakes(self):
        for address in (TARGET, ("2001:db8::1", 9), ("pve.example.invalid", 9)):
            with self.subTest(address=address):
                seen = self.assert_trips(socket.create_connection, address, 1)
                self.assertEqual(seen.entries, ["socket.create_connection"])
        self.assertIn("pve.example.invalid", seen.details)

        class FakeSocket:  # control: the saved original needs nothing but a socket class and a resolver
            def __init__(self, *a):
                self.connected = None

            def settimeout(self, t):
                pass

            def connect(self, sa):
                self.connected = sa

            def close(self):
                pass

        original = tests.ORIGINALS["socket.create_connection"]
        resolver = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", TARGET)]
        with mock.patch.object(socket, "socket", FakeSocket), mock.patch.object(socket, "getaddrinfo",
                                                                                  return_value=resolver):
            self.assertEqual(original(TARGET, 1).connected, TARGET)
        self.assertIsNot(socket.create_connection, original)

    def test_getaddrinfo_refuses_a_name_and_answers_a_literal(self):
        for name in ("pve.example.invalid", b"pve.example.invalid", "localhost", ""):
            with self.subTest(name=name):
                self.assertEqual(self.assert_trips(socket.getaddrinfo, name, 8006).entries, ["socket.getaddrinfo"])
        v4 = socket.getaddrinfo("192.0.2.10", 8006, type=socket.SOCK_STREAM)
        self.assertEqual(v4[0][4], ("192.0.2.10", 8006))
        v6 = socket.getaddrinfo("2001:db8::10", 8006, type=socket.SOCK_STREAM)
        self.assertEqual(v6[0][4][:2], ("2001:db8::10", 8006))
        self.assertTrue(socket.getaddrinfo(None, 8006, flags=socket.AI_PASSIVE, type=socket.SOCK_STREAM))
        untripped(self)

    def test_gethostbyname_family_and_reverse_lookups(self):
        self.assertEqual(self.assert_trips(socket.gethostbyname, "pve.example.invalid").entries,
                         ["socket.gethostbyname"])
        self.assertEqual(self.assert_trips(socket.gethostbyname_ex, "pve.example.invalid").entries,
                         ["socket.gethostbyname_ex"])
        self.assertEqual(self.assert_trips(socket.gethostbyaddr, "192.0.2.10").entries, ["socket.gethostbyaddr"])
        self.assertEqual(self.assert_trips(socket.getnameinfo, ("192.0.2.10", 8006), 0).entries,
                         ["socket.getnameinfo"])
        self.assertEqual(socket.gethostbyname("192.0.2.10"), "192.0.2.10")  # controls: no resolver involved
        self.assertEqual(socket.gethostbyname_ex("192.0.2.10")[2], ["192.0.2.10"])
        numeric = socket.getnameinfo(("192.0.2.10", 8006), socket.NI_NUMERICHOST | socket.NI_NUMERICSERV)
        self.assertEqual(numeric, ("192.0.2.10", "8006"))
        untripped(self)

    def test_an_except_oserror_in_the_code_under_test_does_not_swallow_the_guard(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(sock.close)
        swallowed = []

        def code_under_test():
            try:
                sock.connect(TARGET)
            except OSError:
                swallowed.append(True)

        self.assert_trips(code_under_test)
        self.assertEqual(swallowed, [])

    def test_name_bound_copies_in_imported_modules_are_replaced(self):
        self.assertIs(ssl.create_connection, socket.create_connection)  # ssl did `from socket import ...`
        self.assertIsNot(ssl.create_connection, tests.ORIGINALS["socket.create_connection"])
        conn = http.client.HTTPConnection(*TARGET, timeout=1)  # control: building one is not network use
        self.assertEqual(self.assert_trips(conn.connect).entries, ["socket.create_connection"])
        untripped(self)


# --------------------------------------------------------------------------- urllib

class UrllibEntryPointTests(GuardCase):
    def test_the_default_opener_is_refused(self):
        for target in ("https://192.0.2.10:8006/", "http://pve.example.invalid/",
                       urllib.request.Request("https://192.0.2.10/")):
            with self.subTest(target=str(target)):
                self.assertEqual(self.assert_trips(urllib.request.urlopen, target).entries,
                                 ["urllib.request.urlopen"])

    def test_environment_proxy_handlers_are_refused_and_an_empty_map_is_the_control(self):
        self.assertEqual(self.assert_trips(urllib.request.ProxyHandler).entries, ["urllib.request.ProxyHandler"])
        self.assertEqual(self.assert_trips(urllib.request.build_opener).entries,  # its defaults include one
                         ["urllib.request.ProxyHandler"])
        urllib.request.ProxyHandler({})
        self.assertEqual(urllib.request.ProxyHandler({"https": "http://198.51.100.9:3128"}).proxies,
                         {"https": "http://198.51.100.9:3128"})  # explicit: nothing read from the environment

    def test_an_opener_with_a_fake_handler_works(self):  # control
        class FakeHttps(urllib.request.HTTPSHandler):  # a subclass: the default HTTPSHandler is not added
            def https_open(self, req):
                response = urllib.response.addinfourl(io.BytesIO(b"ok"), http.client.HTTPMessage(), req.full_url, 200)
                response.msg = "OK"
                return response

        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), FakeHttps)
        with mock.patch.dict(os.environ, {"https_proxy": "http://198.51.100.9:3128"}):
            with opener.open("https://192.0.2.10:8006/") as response:
                self.assertEqual(response.read(), b"ok")
            self.assertIn("https", urllib.request.getproxies())  # reading the environment is still allowed
        untripped(self)


# --------------------------------------------------------------------------- the guard is on

class GuardIsActiveTests(GuardCase):
    def test_probe_guard_is_active(self):
        self.assertTrue(tests.guard_active())
        self.assertIsNot(socket.socket.connect, tests.ORIGINALS["socket.connect"])
        self.assertIs(urllib.request.urlopen.__module__, tests.__name__)

    def test_probe_connect_is_refused(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(sock.close)
        self.assert_trips(sock.connect, TARGET)

    def child(self, *argv, cwd=AGENT_DIR):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1",
               "HOME": str(self.dir)}
        return subprocess.run([sys.executable, *argv], capture_output=True, text=True, env=env, cwd=cwd,
                              timeout=120, stdin=subprocess.DEVNULL)

    def test_the_guard_is_active_when_the_suite_is_started_by_discover(self):
        proc = self.child("-m", "unittest", "discover", "-s", "tests", "-t", ".", "-p", "test_l1b_isolation.py",
                          "-k", "test_probe_")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Ran 2 tests", proc.stderr)

    def test_the_guard_is_active_in_the_gates_own_form_of_the_command(self):
        gate = (AGENT_DIR / "tests" / "run.sh").read_text()
        self.assertIn("python3 -m unittest discover -v -s tests -t .", gate)  # what the gate runs
        proc = self.child("-m", "unittest", "discover", "-v", "-s", "tests", "-t", ".", "-p",
                          "test_l1b_isolation.py", "-k", "test_probe_")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("test_probe_connect_is_refused", proc.stderr)
        self.assertIn("Ran 2 tests", proc.stderr)

    def test_the_guard_is_active_for_one_module_and_for_a_bare_import(self):
        proc = self.child("-m", "unittest", "tests.test_l1b_isolation.GuardIsActiveTests.test_probe_connect_is_refused")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc = self.child("-c", "import tests.fixtures, tests; print(tests.guard_active())")
        self.assertEqual(proc.stdout.strip(), "True", proc.stderr)

    def test_installing_twice_changes_nothing(self):
        before = (socket.socket.connect, socket.create_connection, urllib.request.urlopen,
                  unittest.case.TestCase.run, subprocess.Popen.__init__)
        tests.install()
        self.assertEqual(before, (socket.socket.connect, socket.create_connection, urllib.request.urlopen,
                                  unittest.case.TestCase.run, subprocess.Popen.__init__))


# --------------------------------------------------------------------------- the API client's fallback paths

class ApiFallbackTests(GuardCase):
    """The real transport, with the real guard and no fake connection: every fallback path ends in
    the guard or in a refusal, never in a socket."""

    def setUp(self):
        super().setUp()
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        FakeConnection.script, FakeConnection.made = [], []

    def transport(self, **kw):
        with mock.patch.object(pveapi.ssl, "create_default_context", return_value=self.ctx):
            return pveapi.urllib_transport("ca.pem", timeout=1, **kw)

    def send(self, transport, url="https://192.0.2.10:8006/api2/json/version"):
        return transport("GET", url, {"Authorization": "PVEAPIToken=u@pve!lab=" + SECRET}, None)

    def test_without_a_source_address_the_attempt_reaches_the_guard(self):
        seen = self.assert_trips(self.send, self.transport())
        self.assertEqual(seen.entries, ["socket.create_connection"])
        self.assertIn("192.0.2.10", seen.details)

    def test_with_proxy_variables_set_the_attempt_is_direct_and_reaches_the_guard(self):
        proxies = {k: "http://198.51.100.9:3128" for k in ("https_proxy", "HTTPS_PROXY", "all_proxy", "http_proxy")}
        with mock.patch.dict(os.environ, proxies):
            seen = self.assert_trips(self.send, self.transport())
        self.assertIn("192.0.2.10", seen.details)
        self.assertNotIn("198.51.100.9", seen.details)  # not through the proxy

    def test_with_a_source_address_the_bound_attempt_reaches_the_guard(self):
        seen = self.assert_trips(self.send, self.transport(source_address="192.0.2.50"))
        self.assertIn("192.0.2.50", seen.details)

    def test_an_ipv6_literal_reaches_the_guard(self):
        seen = self.assert_trips(self.send, self.transport(), "https://[2001:db8::10]:8006/api2/json/version")
        self.assertIn("2001:db8::10", seen.details)

    def test_a_host_name_that_would_need_resolution_reaches_the_guard(self):
        seen = self.assert_trips(self.send, self.transport(), "https://pve.example.invalid:8006/api2/json/version")
        self.assertIn("pve.example.invalid", seen.details)

    def test_an_http_url_is_refused_before_anything_is_built(self):
        before = len(tests.TRIPS)
        with self.assertRaisesRegex(ValueError, "https only"):
            self.send(self.transport(), "http://192.0.2.10:8006/api2/json/version")
        self.assertEqual(len(tests.TRIPS), before)

    def test_a_redirect_answer_is_a_refusal_and_never_a_second_connection(self):
        FakeConnection.script[:] = [http_answer(302, b"", [("Location", "https://198.51.100.7/x")]),
                                    http_answer(200, b'{"data": "stolen"}')]
        client = pveapi.Client("192.0.2.10", 8006, "u@pve!lab", SECRET, self.transport())
        with mock.patch.object(pveapi.http.client, "HTTPSConnection", FakeConnection):
            with self.assertRaisesRegex(pveapi.PveError, "redirect refused"):
                client.get("/version")
        self.assertEqual(len(FakeConnection.made), 1)
        untripped(self)

    def test_the_whole_client_chain_ends_in_the_guard(self):
        client = pveapi.Client("192.0.2.10", 8006, "u@pve!lab", SECRET, self.transport(source_address="192.0.2.50"))
        seen = self.assert_trips(client.get, "/version")  # the guard's error is not turned into a PveError
        self.assertEqual(seen.entries, ["socket.create_connection"])

    def test_from_config_without_the_setting_refuses_before_any_transport_exists(self):
        with fixtures.private_tmpdir() as d:
            cfg = modified(fixtures.make_lab(Path(d)), PVE_WORKSTATION_ADDR=None)
            with mock.patch.object(pveapi, "urllib_transport") as factory:
                with self.assertRaises(ConfigError):
                    pveapi.Client.from_config(cfg)
            factory.assert_not_called()
        untripped(self)

    def test_the_client_never_uses_the_default_opener(self):
        source = Path(pveapi.__file__).read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\burlopen\s*\(", source))
        self.assertIsNone(re.search(r"\bbuild_opener\s*\(\s*\)", source))
        self.assertIn("ProxyHandler({})", source)


# --------------------------------------------------------------------------- the guard does not hide failures

class GuardDoesNotHideFailuresTests(unittest.TestCase):
    def run_inner(self, body):
        class Inner(unittest.TestCase):
            def test_it(inner):
                body(inner)

        result = unittest.TestResult()
        unittest.TestSuite([Inner("test_it")]).run(result)
        return result

    def texts(self, result):
        return " ".join(tb for _, tb in result.failures + result.errors)

    def test_a_test_that_swallows_the_trip_with_except_exception_fails(self):
        def body(inner):
            try:
                socket.create_connection(TARGET)
            except Exception:  # the code under test hides the guard's error, and the test would pass
                pass

        result = self.run_inner(body)
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(result.failures), 1)
        self.assertIn("only because the guard raised", self.texts(result))
        untripped(self)  # reported once; the outer test is not blamed for it

    def test_catching_oserror_does_not_hide_it(self):
        def body(inner):
            try:
                socket.create_connection(TARGET)
            except OSError:
                pass

        result = self.run_inner(body)
        self.assertFalse(result.wasSuccessful())
        self.assertIn("TEST ISOLATION RULE", self.texts(result))
        untripped(self)

    def test_assert_raises_assertion_error_around_the_trip_does_not_make_it_pass(self):
        def body(inner):
            with inner.assertRaises(AssertionError):
                socket.create_connection(TARGET)

        result = self.run_inner(body)
        self.assertFalse(result.wasSuccessful())
        self.assertIn("only because the guard raised", self.texts(result))
        untripped(self)

    def test_an_acknowledged_trip_in_a_test_about_the_guard_passes(self):  # control
        def body(inner):
            with expect_guard_trips():
                with inner.assertRaises(NetworkIsolationViolation):
                    socket.create_connection(TARGET)

        self.assertTrue(self.run_inner(body).wasSuccessful())

    def test_a_test_without_network_use_passes(self):  # control
        self.assertTrue(self.run_inner(lambda inner: inner.assertEqual(1, 1)).wasSuccessful())

    def test_expecting_a_trip_that_does_not_happen_fails(self):
        def body(inner):
            with expect_guard_trips():
                pass

        result = self.run_inner(body)
        self.assertFalse(result.wasSuccessful())
        self.assertIn("did not", self.texts(result))

    def test_a_trip_in_a_subtest_is_reported_too(self):
        def body(inner):
            with inner.subTest("one"):
                try:
                    socket.getaddrinfo("pve.example.invalid", 1)
                except Exception:
                    pass

        result = self.run_inner(body)
        self.assertFalse(result.wasSuccessful())
        untripped(self)


# --------------------------------------------------------------------------- child processes

SPAWN_CALLS = ({("subprocess", n) for n in ("run", "Popen", "call", "check_call", "check_output", "getoutput",
                                            "getstatusoutput")}
               | {("os", n) for n in ("system", "popen", "execv", "execve", "execvp", "execvpe", "posix_spawn",
                                      "posix_spawnp")}
               | {("pty", "spawn")})
INTERPRETERS = {"bash", "/usr/bin/bash", "sh", "perl", "<python>"}


class _SpawnScan(ast.NodeVisitor):
    def __init__(self, rel):
        self.rel, self.stack, self.sites, self.imports = rel, [], [], []

    def _scope(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scope

    def visit_ImportFrom(self, node):
        if node.module in ("subprocess", "pty") or (node.module == "os" and any(
                a.name in {n for _, n in SPAWN_CALLS} for a in node.names)):
            self.imports.append((self.rel, node.lineno, node.module))

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name in ("subprocess", "os", "pty") and alias.asname:
                self.imports.append((self.rel, node.lineno, f"{alias.name} as {alias.asname}"))

    def visit_Call(self, node):
        f = node.func
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and (f.value.id, f.attr) in SPAWN_CALLS:
            arg = node.args[0] if node.args else None
            if isinstance(arg, (ast.List, ast.Tuple)) and arg.elts:
                first = arg.elts[0]
                argv0 = first.value if isinstance(first, ast.Constant) else (
                    "<python>" if ast.unparse(first) == "sys.executable" else "<dynamic:" + ast.unparse(first) + ">")
            elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                argv0 = arg.value.split()[0] if arg.value.split() else ""
            else:
                argv0 = "<dynamic:" + (ast.unparse(arg) if arg is not None else "?") + ">"
            mentioned = sorted({n.value.split()[0] for n in ast.walk(node) if isinstance(n, ast.Constant)
                                and isinstance(n.value, str) and n.value.split()
                                and n.value.split()[0] in tests.NETWORK_TOOLS})
            self.sites.append({"file": self.rel, "scope": ".".join(self.stack), "call": f"{f.value.id}.{f.attr}",
                               "argv0": argv0, "tools": mentioned, "line": node.lineno})
        self.generic_visit(node)


def scan_spawns(source, rel):
    visitor = _SpawnScan(rel)
    visitor.visit(ast.parse(source))
    return visitor.sites, visitor.imports


def needs_a_listing(site):
    """A call that starts a real child process is free only when it runs a local interpreter and
    names no network tool anywhere in its arguments."""
    return site["argv0"] not in INTERPRETERS or bool(site["tools"])


# Every real child process of the suite that is not a plain local interpreter, with the form that
# makes it unable to connect and a marker that must still be in the file for the claim to hold.
# The runtime guard (tests/__init__.py check_spawn) enforces the same forms when the child starts.
LISTED_SPAWNS = {
    ("tests/stubs/l1b_tools.py", ""): ("local /usr/bin/install and /usr/bin/stat, absolute paths, no network",
                                       ['"/usr/bin/install"', '"/usr/bin/stat"']),
    ("tests/test_closeout_source_addr.py", "SshCommandTests.resolve"): (
        "ssh -G: prints the resolved configuration, opens no connection", ['"-G"']),
    ("tests/test_l1b_transport.py", "SshOptionsTests.resolve"): (
        "ssh -G: prints the resolved configuration, opens no connection", ['"-G"']),
    ("tests/test_gate_run.py", "GateTests.run_gate"): (
        "the gate in a temporary tree with an isolated PATH of a few symlinked local tools; docker is a "
        "stub or absent", ["self.stub_bin", "isolated PATH"]),
    ("tests/test_hostrun.py", "HostRunTests.test_unencrypted_root_key_refused"): (
        "ssh-keygen generating a key file in a temporary directory (not a connection tool)", ['"ssh-keygen"', '"-f"']),
    ("tests/test_l1b_destruct.py", "StubSelfTests.test_stub_snapshot_listing_and_raw_override"): (
        "pvesh is the stub, first on PATH", ["{STUBS}:/usr/bin:/bin"]),
    ("tests/test_l1b_guard_candidate.py", "_git_apply"): (
        "git apply of a local patch file in a temporary tree", ['"git", "apply"']),
    ("tests/test_l1b_guard_candidate.py", "CandidateProposalTests.apply"): (
        "git apply of a local patch file in a temporary tree", ['"git", "apply"']),
    ("tests/test_l1b_guard_candidate.py",
     "CandidateProposalTests.test_each_of_the_first_two_applies_to_the_active_file_alone_and_the_third_does_not"): (
        "git apply --check of a local patch file", ['"git", "apply", "--check"']),
    ("tests/test_l1b_mcp.py", "RealGitRegressionTests.sh"): (
        "local git (init, commit, rev-parse) on throwaway repositories; no clone, no remote",
        ["No network, no clone", "GIT_CONFIG_NOSYSTEM"]),
    ("tests/test_l1b_mcp.py", "RealGitRegressionTests.test_the_premise_git_environment_redirects_an_unsanitized_call"): (
        "local git rev-parse", ['"rev-parse"']),
    ("tests/test_l1b_mcp.py", "RealGitRegressionTests.test_a_gitfile_pointing_at_another_repository_is_not_a_checkout"): (
        "local git rev-parse", ['"rev-parse"']),
    ("tests/test_l1b_isolation.py", "ChildProcessAuditTests.test_shell_strings_that_name_a_network_tool_are_refused"): (
        "echo through a shell: the control that the shell form still runs", ['"echo hi"']),
    ("tests/test_l1b_isolation.py", "ChildProcessAuditTests.test_the_safe_forms_still_run"): (
        "ssh -G and local git init/rev-parse in a temporary directory", ['"-G"', '"git", "init"']),
    ("tests/test_l1b_isolation.py", "SshFormTests.test_through_the_spawn_guard"): (
        "the reviewed ssh -G -F none form (control for the refusals around it)", ['"ssh", "-G", "-F", "none"']),
    ("tests/test_l1b_isolation.py", "InterpreterChildTests.test_a_script_on_standard_input_runs_when_the_tool_is_a_stub_or_absent"): (
        "bash -s with a script that names curl: runs only because curl is a stub or absent on its PATH",
        ["curl x"]),
    ("tests/test_l1b_isolation.py", "ChildProcessAuditTests.test_a_stub_with_a_network_tool_name_is_not_the_tool"): (
        "a stub script in the temporary directory", ["stub curl"]),
    ("tests/test_l1b_hostactions.py", "PrepareTests.make_record"): (
        "stat -f on a temporary directory: a local tool that cannot connect", ['"stat", "-f"']),
    ("tests/test_netless_run.py", "NetlessScriptTests.run_script"): (
        "the network-less acceptance script in a temporary tree with an isolated PATH of symlinked local tools; "
        "docker is a stub that only logs, or absent", ["self.stub_bin", "isolated PATH"]),
    ("tests/test_snippet_writer.py", "SnippetWriterTests.call"): (
        "perl running the snippet writer on a local file", ['["perl", str(WRITER)]']),
}

# Network tool words in command position inside the shell scripts the tests run (or feed to bash),
# and the test file that shadows the tool with a stub or an absent PATH entry.
SCRIPT_NETWORK_USES = {
    ("host/actions/fcos-template.sh", "curl"): ("tests/test_l1b_hostactions.py", ['"curl"', "self.bin"]),
    ("demo/render.sh", "docker"): (None, []),  # run by no test (only the gate runs it, with a stub docker)
    ("tests/run.sh", "docker"): ("tests/test_gate_run.py", ['stub = self.stub_bin / "docker"']),
    ("tests/o4/run-o4.sh", "docker"): ("tests/test_l1b_snippet_writer.py", ['fake = self.bin / "docker"']),
    ("tests/o4/inner.sh", "ssh"): (None, []),  # runs inside the --network none container only; no test runs it
}
_TOOLS_RX = "|".join(sorted(map(re.escape, tests.NETWORK_TOOLS)))
_COMMAND_POSITION = re.compile(r"(?:^|[;&|(`]|\$\()\s*(?:\w+=\S*\s+)*(?:exec\s+|command\s+|sudo\s+|timeout\s+\S+\s+)?("
                               + _TOOLS_RX + r")(?=\s|$|;|\))")


def script_network_words(text):
    found = set()
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        for match in _COMMAND_POSITION.finditer(line):
            found.add(match.group(1))
    return found


class ChildProcessAuditTests(GuardCase):
    def test_the_scan_sees_a_new_spawn_and_classifies_it(self):  # controls for the scanner itself
        sites, imports = scan_spawns("import subprocess, sys\ndef f():\n    subprocess.run(['curl', 'https://x'])\n"
                                     "def g():\n    subprocess.run(['bash', '-s'])\n"
                                     "def h(tool):\n    subprocess.run([tool, '-G'])\n"
                                     "def i():\n    subprocess.run([sys.executable, '-c', 'pass'])\n"
                                     "def j():\n    subprocess.run(['bash', '-c', 'git clone x'])\n", "x.py")
        by = {s["scope"]: s for s in sites}
        self.assertTrue(needs_a_listing(by["f"]))
        self.assertFalse(needs_a_listing(by["g"]))
        self.assertTrue(needs_a_listing(by["h"]))
        self.assertFalse(needs_a_listing(by["i"]))
        self.assertTrue(needs_a_listing(by["j"]))  # a network tool named inside an interpreter's arguments
        self.assertEqual(imports, [])
        _, imports = scan_spawns("from subprocess import run\nimport os as o\n", "y.py")
        self.assertEqual(len(imports), 2)  # the from-import and the aliased import

    def test_every_real_child_process_in_the_suite_is_in_the_allow_list_of_safe_forms(self):
        unlisted, stale_markers = [], []
        files = sorted((AGENT_DIR / "tests").glob("*.py")) + sorted((AGENT_DIR / "tests" / "stubs").glob("*.py"))
        self.assertGreater(len(files), 10)
        for path in files:
            rel = path.relative_to(AGENT_DIR).as_posix()
            text = path.read_text(encoding="utf-8")
            sites, imports = scan_spawns(text, rel)
            self.assertEqual(imports, [], "spawn functions must be called as module attributes so they can be audited")
            for site in sites:
                if not needs_a_listing(site):
                    continue
                entry = LISTED_SPAWNS.get((rel, site["scope"]))
                if entry is None:
                    unlisted.append(f"{rel}:{site['line']} {site['scope'] or '<module>'} {site['call']}"
                                    f"({site['argv0']}) tools={site['tools']}")
                    continue
                stale_markers += [f"{rel} {site['scope']}: missing {m!r}" for m in entry[1] if m not in text]
        self.assertEqual(unlisted, [], "a test starts a real child process outside the allow-list of safe forms; "
                                       "use a stub, ssh -G, a local git subcommand or --network none, then list it")
        self.assertEqual(stale_markers, [])

    def test_every_listed_form_is_one_the_runtime_guard_accepts(self):
        for form in tests.SAFE_SPAWN_FORMS:
            self.assertIn(form, tests.NETWORK_TOOLS)
        self.assertEqual(tests.GIT_LOCAL_SUBCOMMANDS & {"clone", "fetch", "pull", "push", "ls-remote", "remote",
                                                        "submodule"}, set())

    def test_network_tool_words_in_the_scripts_the_tests_run_are_shadowed_by_a_stub_or_run_by_no_test(self):
        scripts = ([p for p in (AGENT_DIR / "host").rglob("*") if p.is_file() and p.suffix in ("", ".sh")]
                   + [AGENT_DIR / "demo" / "render.sh", AGENT_DIR / "tests" / "run.sh"]
                   + sorted((AGENT_DIR / "tests" / "o4").glob("*.sh")))
        found = {}
        for script in scripts:
            for word in script_network_words(script.read_text(encoding="utf-8", errors="replace")):
                found[(script.relative_to(AGENT_DIR).as_posix(), word)] = True
        self.assertEqual(sorted(set(found) - set(SCRIPT_NETWORK_USES)), [],
                         "a script run by tests now names a network tool: shadow it with a stub in the test and list it")
        for (script, word), (test_file, markers) in SCRIPT_NETWORK_USES.items():
            if test_file is None:
                continue
            text = (AGENT_DIR / test_file).read_text(encoding="utf-8")
            for marker in markers:
                self.assertIn(marker, text, f"{test_file} no longer shadows {word} for {script}")
        # The tests that run the scripts that name curl or ssh never spawn the scripts that are listed as "no test".
        for path in sorted((AGENT_DIR / "tests").glob("*.py")):
            sites, _ = scan_spawns(path.read_text(encoding="utf-8"), path.name)
            source = path.read_text(encoding="utf-8")
            for (script, _word), (test_file, _m) in SCRIPT_NETWORK_USES.items():
                if test_file is None and path.name != "test_l1b_isolation.py":
                    base = Path(script).name
                    for line in source.splitlines():
                        if base in line and "subprocess." in line:
                            self.fail(f"{path.name} starts {base}, which names a network tool and has no stub")

    def test_the_stub_directories_hold_stubs_for_the_tools_the_scripts_name(self):
        stub_text = (AGENT_DIR / "tests" / "stubs" / "l1b_tools.py").read_text(encoding="utf-8")
        self.assertIn('tool == "curl"', stub_text)  # the curl that fcos-template.sh calls is a stub
        self.assertFalse((AGENT_DIR / "tests" / "stubs" / "ssh").exists())

    # ---- the runtime guard on child processes

    def test_a_network_tool_outside_the_safe_forms_is_refused_before_it_starts(self):
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.dir)}
        for argv in (["curl", "https://192.0.2.10/"], ["wget", "http://192.0.2.10/"], ["ssh", "192.0.2.10", "id"],
                     ["scp", "a", "192.0.2.10:b"], ["sftp", "192.0.2.10"], ["uv", "sync"], ["uvx", "x"],
                     ["docker", "run", "x"], ["git", "clone", "https://example.invalid/r"], ["git", "ls-remote", "x"],
                     ["git", "-C", str(self.dir), "fetch"], ["git", "-c", "a=b", "pull"], ["nc", "192.0.2.10", "9"],
                     ["/usr/bin/curl", "x"], ["rsync", "a", "b:c"]):
            with self.subTest(argv=argv):
                seen = self.assert_trips(subprocess.run, argv, env=env, capture_output=True)
                self.assertEqual(seen.entries, ["spawn"])

    def test_shell_strings_that_name_a_network_tool_are_refused(self):
        self.assertEqual(self.assert_trips(subprocess.run, "echo hi; curl https://192.0.2.10/", shell=True).entries,
                         ["spawn"])
        self.assertEqual(self.assert_trips(os.system, "wget http://192.0.2.10/").entries, ["spawn"])
        self.assertEqual(self.assert_trips(os.popen, "ssh 192.0.2.10 id").entries, ["spawn"])
        self.assertEqual(self.assert_trips(os.execv, "/usr/bin/curl", ["curl", "x"]).entries, ["spawn"])
        # With executable= the program that runs is the executable, argv[0] is only a display name.
        self.assertEqual(self.assert_trips(subprocess.Popen, ["x"], executable="/usr/bin/curl").entries, ["spawn"])
        proc = subprocess.run("echo hi", shell=True, capture_output=True, text=True)  # control
        self.assertEqual(proc.stdout.strip(), "hi")

    def test_the_safe_forms_still_run(self):  # positive controls
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.dir)}
        if shutil.which("ssh"):
            proc = subprocess.run(["ssh", "-G", "-F", "none", "192.0.2.10"], capture_output=True, text=True, env=env,
                                  timeout=10, stdin=subprocess.DEVNULL)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("hostname 192.0.2.10", proc.stdout)
        if shutil.which("git"):
            repo = self.dir / "repo"
            git_env = {**env, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
            subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env, capture_output=True)
            out = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-dir"], check=True, env=git_env,
                                 capture_output=True, text=True)
            self.assertEqual(out.stdout.strip(), ".git")
        untripped(self)

    def test_a_stub_with_a_network_tool_name_is_not_the_tool(self):  # control: stubs are the safe form
        bin_dir = self.dir / "bin"
        bin_dir.mkdir()
        stub = bin_dir / "curl"
        stub.write_text("#!/bin/sh\necho stub curl\n")
        stub.chmod(0o755)
        for argv, env in ((["curl"], {"PATH": str(bin_dir)}), ([str(stub)], {"PATH": "/usr/bin:/bin"})):
            out = subprocess.run(argv, env=env, capture_output=True, text=True)
            self.assertEqual(out.stdout.strip(), "stub curl")
        # The stub exemption belongs to tests/stubs and the temporary directory, not to /usr/bin.
        self.assertTrue(tests._is_stub(str(stub)))
        self.assertTrue(tests._is_stub(str(AGENT_DIR / "tests" / "stubs" / "pvesh")))
        self.assertFalse(tests._is_stub("/usr/bin/curl"))
        self.assertFalse(tests._is_stub(None))
        untripped(self)



# --------------------------------------------------------------------------- T1b: child policy, accounting, repair

class SshFormTests(GuardCase):
    """Only the reviewed ssh form passes: -G among the options, before the destination, with -F none
    or a scratch configuration whose directives are all allow-listed (``Match exec`` runs while -G
    resolves a file), and allow-listed options only. ``ssh host echo -G`` connects, so it must not."""

    def setUp(self):
        super().setUp()
        (self.dir / "cfg").write_text("# scratch\nHost *\n    ProxyJump jump@198.51.100.1\n    BindInterface eth9\n"
                                      "    IdentityFile /nonexistent/key\n    ForwardAgent yes\n")
        (self.dir / "match.cfg").write_text('Match exec "/usr/bin/curl https://192.0.2.10/"\n    ForwardAgent yes\n')
        (self.dir / "include.cfg").write_text("Include /etc/ssh/ssh_config\n")
        (self.dir / "proxycommand.cfg").write_text("Host *\n  ProxyCommand /usr/bin/nc %h %p\n")
        (self.dir / "localcommand.cfg").write_text("Host *\n  PermitLocalCommand=yes\n  LocalCommand=/usr/bin/true\n")
        (self.dir / "khc.cfg").write_text("KnownHostsCommand /usr/bin/true\n")

    def test_the_reviewed_forms_pass(self):
        ok = ([ "-V"], ["-G", "-F", "none", "192.0.2.10"], ["-F", "none", "-G", "192.0.2.10"],
              ["-GF", "none", "192.0.2.10"], ["-G", "-Fnone", "-T", "-o", "BatchMode=no", "root@192.0.2.10", "bash -s"],
              ["-G", "-F", "none", "-i", "/nonexistent/key", "-o", "Port=22", "-o", "bindaddress 192.0.2.7",
               "root@192.0.2.10", "bash -s"],
              ["-T", "-G", "-F", str(self.dir / "cfg"), "192.0.2.10"])   # inspected scratch configuration
        for args in ok:
            with self.subTest(args=args):
                self.assertTrue(tests._ssh_form_ok(args))

    def test_counter_examples_are_refused(self):
        bad = (["192.0.2.10", "echo", "-G"],            # -G belongs to the remote command
               ["192.0.2.10", "-G"],                     # after the destination
               ["-F", "none", "192.0.2.10", "-G"],
               ["-G", "192.0.2.10"],                     # no -F: reads the user's and the system's configuration
               ["-G", "-F", "/etc/ssh/ssh_config", "192.0.2.10"],   # a configuration outside the temporary directory
               ["-V", "192.0.2.10"], ["-V", "-G"], [], ["192.0.2.10"], ["-F", "none", "192.0.2.10"],
               ["-o", "ProxyCommand=true", "192.0.2.10", "-G"], ["--", "-G", "-F", "none"],
               # a scratch configuration with a directive outside the allow-list: Match exec would run
               ["-G", "-F", str(self.dir / "match.cfg"), "192.0.2.10"], ["-G", "-F", str(self.dir / "include.cfg"), "x"],
               ["-G", "-F", str(self.dir / "proxycommand.cfg"), "x"], ["-G", "-F", str(self.dir / "localcommand.cfg"), "x"],
               ["-G", "-F", str(self.dir / "khc.cfg"), "x"], ["-G", "-F", str(self.dir / "missing.cfg"), "x"],
               ["-G", "-F", "none", "-F", str(self.dir / "cfg"), "x"],   # one -F only
               # options and -o keys outside the allow-list
               ["-G", "-F", "none", "-o", "ProxyCommand=true", "192.0.2.10"],
               ["-G", "-F", "none", "-o", "Include=/tmp/x", "192.0.2.10"],
               ["-G", "-F", "none", "-o", "KnownHostsCommand=/usr/bin/true", "192.0.2.10"],
               ["-G", "-F", "none", "-oLocalCommand=true", "192.0.2.10"],
               ["-G", "-F", "none", "-J", "jump", "192.0.2.10"], ["-G", "-F", "none", "-E", "/tmp/log", "192.0.2.10"],
               ["-G", "-F", "none", "-v", "192.0.2.10"], ["-G", "-F", "none", "-o"], ["-G", "-F"])
        for args in bad:
            with self.subTest(args=args):
                self.assertFalse(tests._ssh_form_ok(args))

    def test_through_the_spawn_guard(self):
        for argv in (["ssh", "192.0.2.10", "echo", "-G"], ["ssh", "192.0.2.10", "-G"], ["ssh", "-G", "192.0.2.10"],
                     ["ssh", "-G", "-F", "/etc/ssh/ssh_config", "192.0.2.10"], ["ssh", "-V", "x"]):
            with self.subTest(argv=argv):
                self.assertEqual(self.assert_trips(subprocess.run, argv, capture_output=True).entries, ["spawn"])
        if shutil.which("ssh"):  # control: the reviewed form runs
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.dir)}
            ok = subprocess.run(["ssh", "-G", "-F", "none", "192.0.2.10"], capture_output=True, text=True, env=env,
                                timeout=10, stdin=subprocess.DEVNULL)
            self.assertEqual(ok.returncode, 0, ok.stderr)


class InterpreterChildTests(GuardCase):
    """Interpreter children cannot carry a network tool in by -c text, a script, standard input or a
    fake stub; and an executable that is not on the allow-list is refused (fail closed)."""

    def env(self, path=None):
        return {"PATH": path if path is not None else "/usr/bin:/bin", "HOME": str(self.dir)}

    def test_inline_text_naming_a_tool_by_any_path_is_refused(self):
        for argv in (["bash", "-c", "exec /usr/bin/curl https://192.0.2.10/"], ["sh", "-c", "/opt/x/git clone y"],
                     ["bash", "-c", "cd /tmp && ../../usr/bin/ssh host id"], ["bash", "-lc", "wget x"],
                     [sys.executable, "-c", "import os; os.system('curl x')"], ["perl", "-e", "exec 'curl', 'x'"],
                     ["perl", "-E", "say `nc 192.0.2.10 9`"], ["dash", "-c", "docker run x"]):
            with self.subTest(argv=argv):
                self.assertEqual(self.assert_trips(subprocess.run, argv, env=self.env(), capture_output=True).entries,
                                 ["spawn"])

    def test_inline_text_that_names_no_tool_runs(self):  # controls
        self.assertEqual(subprocess.run(["bash", "-c", "echo ok"], capture_output=True, text=True,
                                        env=self.env()).stdout.strip(), "ok")
        self.assertEqual(subprocess.run([sys.executable, "-c", "print(1 + 1)"], capture_output=True, text=True,
                                        env=self.env()).stdout.strip(), "2")
        untripped(self)

    def test_a_script_on_standard_input_that_names_a_real_tool_is_refused_and_the_child_is_stopped(self):
        if not shutil.which("curl", path="/usr/bin:/bin"):
            self.skipTest("no real curl on this machine: nothing that resolves to a real tool to refuse")
        proc = subprocess.Popen(["bash", "-s"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=self.env())
        with expect_guard_trips() as seen:
            with self.assertRaises(NetworkIsolationViolation):
                proc.communicate(b"curl https://192.0.2.10/\n")
        self.assertEqual(seen.entries, ["spawn"])
        self.assertIsNotNone(proc.wait(timeout=10))  # it was killed, not left waiting on its input

    def test_a_script_on_standard_input_runs_when_the_tool_is_a_stub_or_absent(self):  # controls
        bin_dir = self.dir / "bin"
        bin_dir.mkdir()
        stub = bin_dir / "curl"
        stub.write_text("#!/bin/sh\necho stub curl\n")
        stub.chmod(0o755)
        self.assertEqual(subprocess.run(["bash", "-s"], input="curl x\n", text=True, capture_output=True,
                                        env=self.env(f"{bin_dir}:/usr/bin:/bin")).stdout.strip(), "stub curl")
        code = subprocess.run([shutil.which("bash"), "-s"], input="curl x\n", text=True, capture_output=True,
                              env=self.env(str(self.dir / "nowhere"))).returncode  # not found: 127, no tool ran
        self.assertEqual(code, 127)
        untripped(self)

    def test_a_script_file_is_read_and_held_to_the_same_rule(self):
        script = self.dir / "go.sh"
        script.write_text("#!/bin/sh\nexec /usr/bin/curl https://192.0.2.10/\n")
        self.assertEqual(self.assert_trips(subprocess.run, ["bash", str(script)], env=self.env(),
                                           capture_output=True).entries, ["spawn"])
        script.write_text("#!/bin/sh\necho fine\n")  # control
        self.assertEqual(subprocess.run(["bash", str(script)], env=self.env(), capture_output=True,
                                        text=True).stdout.strip(), "fine")

    def test_a_tool_name_spelled_with_quotes_or_backslashes_is_refused(self):
        # The shell drops quotes and backslashes before it looks the command up; so does the screen.
        if not shutil.which("curl", path="/usr/bin:/bin"):
            self.skipTest("no real curl on this machine: nothing that resolves to a real tool to refuse")
        for line in ('"/usr/bin/curl" https://192.0.2.10/', "'curl' x", 'c"ur"l x', "cu\\rl x", "\\curl x",
                     'echo ok; "curl" x', 'x=1 "/usr/bin/curl" y', "echo $('curl' x)"):
            script = self.dir / "quoted.sh"
            script.write_text("#!/bin/sh\n" + line + "\n")
            with self.subTest(line=line):
                self.assertEqual(self.assert_trips(subprocess.run, ["bash", str(script)], env=self.env(),
                                                   capture_output=True).entries, ["spawn"])
        script = self.dir / "plain.sh"  # control: a quoted word that is not a tool
        script.write_text("#!/bin/sh\n\"echo\" 'curly braces'\n")
        self.assertEqual(subprocess.run(["bash", str(script)], env=self.env(), capture_output=True,
                                        text=True).stdout.strip(), "curly braces")
        untripped(self)

    def test_a_perl_or_python_file_in_the_temporary_directory_that_names_a_tool_is_refused(self):
        # perl -c is not parse-only: BEGIN blocks run while it compiles. The file is never started here.
        begin = self.dir / "begin.pl"
        begin.write_text('BEGIN { system "/usr/bin/curl", "https://192.0.2.10/"; }\n1;\n')
        py = self.dir / "go.py"
        py.write_text("import subprocess\nsubprocess.run(['/usr/bin/ssh', 'host', 'id'])\n")
        for argv in (["perl", "-c", str(begin)], ["perl", str(begin)], [sys.executable, str(py)]):
            with self.subTest(argv=argv):
                self.assertEqual(self.assert_trips(subprocess.run, argv, env=self.env(), capture_output=True).entries,
                                 ["spawn"])

    def test_a_script_too_large_to_screen_is_refused(self):
        # Padding must not turn the screen off: a file at the limit is refused before it starts.
        for name, argv0 in (("big.pl", "perl"), ("big.sh", "bash"), ("big.py", sys.executable)):
            big = self.dir / name
            with open(big, "wb") as fh:
                fh.write(b"# padding\n" * (tests.SCRIPT_SCREEN_LIMIT // 10 + 1))
                fh.write(b'BEGIN { system "/usr/bin/curl", "https://192.0.2.10/"; }\n')
            with self.subTest(script=name):
                self.assertGreaterEqual(big.stat().st_size, tests.SCRIPT_SCREEN_LIMIT)
                self.assertEqual(self.assert_trips(subprocess.run, [argv0, str(big)], env=self.env(),
                                                   capture_output=True).entries, ["spawn"])
            big.unlink()

    def test_a_script_outside_the_repository_and_the_temporary_directory_is_refused(self):
        outside = Path("/etc/profile")
        if not outside.exists():
            self.skipTest("no /etc/profile")
        self.assertEqual(self.assert_trips(subprocess.run, ["bash", str(outside)], env=self.env(),
                                           capture_output=True).entries, ["spawn"])

    def test_syntax_only_checks_of_a_repository_or_temporary_file_run(self):
        # bash -n FILE parses and runs nothing of the file's own commands: a file that names real tools
        # (here: a script that would call curl) is fine to PARSE. perl -c is not parse-only (BEGIN
        # blocks run); it is allowed for the repository's own writer as for any repository perl file.
        writer = AGENT_DIR / "host" / "snippet-writer" / "corelab-snippet-put"
        action = AGENT_DIR / "host" / "actions" / "fcos-template.sh"  # names curl in command position
        scratch = self.dir / "names-curl.sh"
        scratch.write_text("#!/bin/sh\ncurl https://192.0.2.10/\n")
        if shutil.which("perl"):
            self.assertEqual(subprocess.run(["perl", "-c", str(writer)], capture_output=True,
                                            env=self.env()).returncode, 0)
        self.assertEqual(subprocess.run(["bash", "-n", str(action)], capture_output=True, env=self.env()).returncode, 0)
        self.assertEqual(subprocess.run(["bash", "-n", str(scratch)], capture_output=True, env=self.env()).returncode, 0)
        proc = subprocess.run(["bash", "-n"], input=scratch.read_text(), text=True, capture_output=True,
                              env=self.env())  # bash -n on standard input: parse only
        self.assertEqual(proc.returncode, 0, proc.stderr)
        untripped(self)

    def test_syntax_only_does_not_open_the_door_for_anything_else(self):  # the counter-examples
        scratch = self.dir / "names-curl.sh"
        scratch.write_text("#!/bin/sh\ncurl https://192.0.2.10/\n")
        for argv in (["perl", "-e", "exec 'curl', 'x'"], ["perl", "-c", "-e", "exec 'curl', 'x'"],
                     ["bash", "-c", "curl x"], ["bash", "-n", "-c", "curl x"], ["bash", "-nc", "curl x"],
                     ["bash", "-n", str(scratch), "-c", "curl x"],   # more than the one file
                     ["bash", "-n", "/etc/profile"], ["perl", "-c", "/etc/hostname"],   # outside the roots
                     ["bash", str(scratch)]):                         # running it, not parsing it
            if "/etc/" in " ".join(argv) and not Path(argv[-1]).exists():
                continue
            with self.subTest(argv=argv):
                self.assertEqual(self.assert_trips(subprocess.run, argv, env=self.env(), capture_output=True).entries,
                                 ["spawn"])

    def test_perl_reading_its_program_from_standard_input_is_refused(self):
        # ``perl -c`` with no file is not the syntax-only form: perl would wait for a program on
        # standard input (and run its BEGIN blocks). Refused before the child starts; standard input is
        # /dev/null here so a guard that let it through could not hang the run.
        for argv in (["perl", "-c"], ["perl"], ["perl", "-w"], ["perl", "-I", "lib"]):
            with self.subTest(argv=argv):
                self.assertEqual(self.assert_trips(subprocess.run, argv, env=self.env(), stdin=subprocess.DEVNULL,
                                                   capture_output=True).entries, ["spawn"])
        # control: the syntax-only form on a file under the temporary directory still runs
        ok = self.dir / "ok.pl"
        ok.write_text("use strict; 1;\n")
        self.assertEqual(subprocess.run(["perl", "-c", str(ok)], capture_output=True, env=self.env()).returncode, 0)
        untripped(self)

    def test_a_python_or_perl_file_in_the_repository_is_not_read_as_a_shell_script(self):
        # A hook or tool that is repository code and merely names ssh (it exists to deny it) may run;
        # reading Python text for shell command words would refuse the guard's own hook. Checked on the
        # policy function, so nothing is started.
        hook = AGENT_DIR / "proposed" / "hooks" / "pve-guard.py"
        self.assertIn("ssh", hook.read_text(encoding="utf-8"))
        self.assertIsNone(tests.check_spawn([sys.executable, str(hook)], self.env()))
        writer = AGENT_DIR / "host" / "snippet-writer" / "corelab-snippet-put"
        self.assertIsNone(tests.check_spawn(["perl", str(writer)], self.env()))
        untripped(self)
        # The same text in a file a test wrote into the temporary directory is not reviewed code.
        script = self.dir / "names_ssh.py"
        script.write_text('print("ok")\nimport os\nos.system("/usr/bin/ssh host id")\n')
        self.assertEqual(self.assert_trips(subprocess.run, [sys.executable, str(script)], capture_output=True,
                                           env=self.env()).entries, ["spawn"])
        # A tool named without a path counts when it resolves on the child's PATH to a real program,
        # and does not when it resolves to nothing (how the hook tests run a copy of the hook).
        script.write_text('print("ok")  # would call: ssh\nTOOLS = ("ssh", "scp")\n')
        out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                             env=self.env(str(self.dir / "nowhere")))
        self.assertEqual(out.stdout.strip(), "ok")
        untripped(self)
        if shutil.which("ssh", path="/usr/bin:/bin"):
            self.assertEqual(self.assert_trips(subprocess.run, [sys.executable, str(script)], capture_output=True,
                                               env=self.env()).entries, ["spawn"])

    def test_python_modules_are_allow_listed(self):
        self.assertEqual(self.assert_trips(subprocess.run, [sys.executable, "-m", "http.server"],
                                           env=self.env()).entries, ["spawn"])
        self.assertEqual(self.assert_trips(subprocess.run, [sys.executable, "-m", "smtplib"],
                                           env=self.env()).entries, ["spawn"])

    def test_an_executable_that_is_not_on_the_allow_list_is_refused_before_it_starts(self):
        for argv in (["id"], ["ls"], ["/usr/bin/env", "curl", "x"], ["python-not-really"], ["busybox", "wget", "x"]):
            with self.subTest(argv=argv):
                self.assertEqual(self.assert_trips(subprocess.run, argv, env=self.env(), capture_output=True).entries,
                                 ["spawn"])

    def test_a_temporary_file_named_like_a_tool_is_not_a_stub_unless_it_is_a_harmless_script(self):
        bin_dir = self.dir / "bin"
        bin_dir.mkdir()
        real = shutil.which("curl", path="/usr/bin:/bin") or shutil.which("true")
        link = bin_dir / "curl"
        link.symlink_to(real)  # a symlink out of the temporary directory
        self.assertFalse(tests._is_stub(str(link)))
        copy = bin_dir / "wget"
        shutil.copy(shutil.which("true"), copy)  # a real binary copied into the temporary directory
        copy.chmod(0o755)
        self.assertFalse(tests._is_stub(str(copy)))
        runs = bin_dir / "docker"
        runs.write_text("#!/bin/sh\nexec /usr/bin/docker \"$@\"\n")  # a script that runs the real tool
        runs.chmod(0o755)
        self.assertFalse(tests._is_stub(str(runs)))
        fine = bin_dir / "git"
        fine.write_text("#!/bin/sh\necho stub git\n")  # control
        fine.chmod(0o755)
        self.assertTrue(tests._is_stub(str(fine)))
        for name in ("curl", "wget", "docker"):
            with self.subTest(name=name):
                self.assertEqual(self.assert_trips(subprocess.run, [name], env=self.env(str(bin_dir)),
                                                   capture_output=True).entries, ["spawn"])


class AccountingAndRepairTests(GuardCase):
    """Trips outside test bodies fail the run; a replaced guard is repaired and blamed."""

    def child_run(self, module_text, *names):
        (self.dir / "swallow_mod.py").write_text(module_text)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONPATH": str(self.dir), "HOME": str(self.dir)}
        return subprocess.run([sys.executable, "-m", "unittest", "swallow_mod", *names], capture_output=True,
                              text=True, env=env, cwd=AGENT_DIR, timeout=120, stdin=subprocess.DEVNULL)

    SWALLOWED = ("import socket, unittest\nimport tests\n{body}\n"
                 "class T(unittest.TestCase):\n{fixture}    def test_ok(self):\n        pass\n")

    def test_a_trip_swallowed_at_import_fails_the_run(self):
        proc = self.child_run(self.SWALLOWED.format(
            body="try:\n    socket.create_connection(('192.0.2.1', 9))\nexcept Exception:\n    pass", fixture=""))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("outside any test body", proc.stderr)
        self.assertIn("OK" if False else "FAILED", proc.stderr)

    def test_a_trip_swallowed_in_setupclass_and_setupmodule_fails_the_run(self):
        fixture = ("    @classmethod\n    def setUpClass(cls):\n        try:\n"
                   "            socket.getaddrinfo('pve.example.invalid', 1)\n        except Exception:\n"
                   "            pass\n")
        proc = self.child_run(self.SWALLOWED.format(body="", fixture=fixture))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("outside any test body", proc.stderr)
        module = ("import socket, unittest\nimport tests\n"
                  "def setUpModule():\n    try:\n        socket.gethostbyname('pve.example.invalid')\n"
                  "    except Exception:\n        pass\n"
                  "class T(unittest.TestCase):\n    def test_ok(self):\n        pass\n")
        proc = self.child_run(module)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("outside any test body", proc.stderr)

    def test_a_module_that_does_not_touch_the_network_passes(self):  # control
        proc = self.child_run(self.SWALLOWED.format(body="x = 1", fixture=""))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("outside any test body", proc.stderr)

    def run_inner(self, *bodies):
        class Inner(unittest.TestCase):
            pass

        for index, body in enumerate(bodies):
            setattr(Inner, f"test_{index}", lambda inner, body=body: body(inner))
        result = unittest.TestResult()
        unittest.TestSuite([Inner(f"test_{i}") for i in range(len(bodies))]).run(result)
        return result

    def test_a_replaced_guard_is_put_back_and_the_next_test_is_failed_for_it(self):
        original = tests.ORIGINALS["socket.create_connection"]

        def tamper(inner):
            socket.create_connection = original  # replaced, and not restored

        def next_test(inner):
            inner.assertTrue(True)

        try:
            result = self.run_inner(tamper, next_test)
            self.assertFalse(result.wasSuccessful())
            self.assertEqual(len(result.failures), 1)
            self.assertIn("found replaced", result.failures[0][1])
            self.assertIn("socket.create_connection", result.failures[0][1])
            self.assertTrue(tests.guard_active())  # put back
            self.assertIsNot(socket.create_connection, original)
        finally:
            tests.ensure_installed()
        untripped(self)

    def test_guard_status_names_what_is_replaced_and_install_repairs_or_refuses(self):
        guard = socket.create_connection
        try:
            socket.create_connection = tests.ORIGINALS["socket.create_connection"]
            self.assertFalse(tests.guard_active())
            self.assertIn("socket.create_connection", tests.guard_status())
            self.assertEqual(tests.install(), ["socket.create_connection"])  # repaired
            self.assertTrue(tests.guard_active())
            self.assertIs(socket.create_connection, guard)
            socket.create_connection = tests.ORIGINALS["socket.create_connection"]
            with mock.patch.object(tests, "ensure_installed", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "cannot be restored"):
                    tests.install()  # nothing repaired and still broken: refuse
        finally:
            tests.ensure_installed()
        self.assertTrue(tests.guard_active())

    def test_the_guard_is_checked_before_every_test(self):
        calls = []
        real = tests.ensure_installed
        with mock.patch.object(tests, "ensure_installed", side_effect=lambda: calls.append(1) or real()):
            result = self.run_inner(lambda inner: None, lambda inner: None)
        self.assertTrue(result.wasSuccessful())
        self.assertGreaterEqual(len(calls), 2)

    def test_a_replaced_socket_class_is_restored(self):
        class Fake:
            pass

        original_class = socket.socket
        try:
            socket.socket = Fake
            self.assertIn("socket.socket", tests.guard_status())
            tests.ensure_installed()
            self.assertIs(socket.socket, original_class)
        finally:
            socket.socket = original_class


class HonestClaimsTests(unittest.TestCase):
    """The module says what the guard does and what it does not (T1b: no suite-wide claim)."""

    def test_the_docstring_states_the_limits_and_names_the_container_run(self):
        doc = tests.__doc__
        for phrase in ("PREVENTS in-process Python network use", "SCREENS direct child commands",
                       "NOT containment", "it is not complete", "KNOWN GAPS of that screen",
                       "does NOT make the suite network-free", "is the network-less container run",
                       "separate acceptance command"):
            self.assertIn(phrase, doc)
        self.assertNotIn("suite-wide prevention", doc)
        self.assertNotIn("fail-closed policy", doc)  # the child screen is a text match, not a boundary
        self.assertNotIn("makes the suite network-free", doc.replace("does NOT make the suite network-free", ""))


if __name__ == "__main__":
    unittest.main()
