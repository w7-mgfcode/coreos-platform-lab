"""The API client's TLS context against real certificates (no socket, no host).

``pveapi.verifying_context`` clears ``VERIFY_X509_STRICT`` because a Proxmox VE host's own
cluster CA carries no key usage extension, which strict verification refuses (OpenSSL verify
code 92). These tests run real TLS handshakes, in memory (``ssl.MemoryBIO``), between that
context and a server holding fixture certificates, so OpenSSL really verifies the chain and
the name. They show that the adjustment accepts the intended CA and still refuses an
unrelated CA and a wrong host name.

Fixtures (``tests/tls-fixture-*``, invented names, valid 2026 to 2126, test-only; they sit
directly in ``tests/`` because the repository hygiene test allows a fake private key only
there): ``tls-fixture-ca-nokeyusage.pem`` has the shape of a Proxmox cluster CA (critical basic constraints, both
key identifiers, no key usage); ``tls-fixture-server.pem``/``.key`` is a leaf it signed for
``pve-test.example.invalid``; ``tls-fixture-ca-unrelated.pem`` is another CA of the same shape that
signed nothing. The server key is a throw-away private key that protects nothing.
"""

import ssl
import unittest
from pathlib import Path

from lab_agent import pveapi

FIX = Path(__file__).parent
CA = str(FIX / "tls-fixture-ca-nokeyusage.pem")
OTHER_CA = str(FIX / "tls-fixture-ca-unrelated.pem")
HOST = "pve-test.example.invalid"

X509_V_ERR_UNABLE_TO_GET_ISSUER_CERT_LOCALLY = 20
X509_V_ERR_HOSTNAME_MISMATCH = 62
X509_V_ERR_IP_ADDRESS_MISMATCH = 64
X509_V_ERR_CA_CERT_MISSING_KEY_USAGE = 92


def server_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(FIX / "tls-fixture-server.pem"), str(FIX / "tls-fixture-server.key"))
    return ctx


def handshake(client_ctx: ssl.SSLContext, hostname: str) -> dict:
    """Run a full TLS handshake in memory; return the server certificate the client verified.
    A verification failure on the client side is raised as it is."""
    c_in, c_out, s_in, s_out = ssl.MemoryBIO(), ssl.MemoryBIO(), ssl.MemoryBIO(), ssl.MemoryBIO()
    client = client_ctx.wrap_bio(c_in, c_out, server_hostname=hostname)
    server = server_context().wrap_bio(s_in, s_out, server_side=True)

    def step(side) -> bool:
        try:
            side.do_handshake()
            return True
        except ssl.SSLWantReadError:
            return False

    for _ in range(32):
        client_done = step(client)
        s_in.write(c_out.read())
        try:
            server_done = step(server)
        except ssl.SSLError:
            server_done = False  # the client's alert; the client's own error is the one that matters
        c_in.write(s_out.read())
        if client_done and server_done:
            return client.getpeercert()
    raise AssertionError("the in-memory handshake did not finish")


def strict_reference_context(ca_file: str) -> ssl.SSLContext:
    """What the client's context would be without the adjustment: the same settings with
    ``VERIFY_X509_STRICT`` set (the default of Python 3.13 and later, set here explicitly so
    the control means the same on an older Python)."""
    ctx = ssl.create_default_context(cafile=ca_file)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.verify_flags |= ssl.VERIFY_X509_STRICT
    return ctx


class TlsStrictCompat(unittest.TestCase):
    def test_fixture_ca_has_the_shape_that_strict_mode_refuses(self):
        """The control that makes the next test mean something: with the strict flag, the very
        same handshake is refused, and for the key usage reason."""
        with self.assertRaises(ssl.SSLCertVerificationError) as caught:
            handshake(strict_reference_context(CA), HOST)
        self.assertEqual(caught.exception.verify_code, X509_V_ERR_CA_CERT_MISSING_KEY_USAGE)

    def test_intended_ca_without_key_usage_is_accepted(self):
        peer = handshake(pveapi.verifying_context(CA), HOST)
        self.assertIn(("DNS", HOST), peer["subjectAltName"])

    def test_unrelated_ca_is_still_refused(self):
        with self.assertRaises(ssl.SSLCertVerificationError) as caught:
            handshake(pveapi.verifying_context(OTHER_CA), HOST)
        self.assertEqual(caught.exception.verify_code, X509_V_ERR_UNABLE_TO_GET_ISSUER_CERT_LOCALLY)

    def test_wrong_host_name_is_still_refused(self):
        cases = (("other.example.invalid", X509_V_ERR_HOSTNAME_MISMATCH),
                 ("pve-test.example.invalid.evil.invalid", X509_V_ERR_HOSTNAME_MISMATCH),
                 ("192.0.2.10", X509_V_ERR_IP_ADDRESS_MISMATCH))
        for wrong, code in cases:
            with self.subTest(wrong), self.assertRaises(ssl.SSLCertVerificationError) as caught:
                handshake(pveapi.verifying_context(CA), wrong)
            self.assertEqual(caught.exception.verify_code, code)

    def test_only_the_strict_flag_differs_and_only_in_this_context(self):
        before = ssl.create_default_context().verify_flags
        ctx = pveapi.verifying_context(CA)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)
        self.assertFalse(ctx.verify_flags & ssl.VERIFY_X509_STRICT)
        reference = ssl.create_default_context(cafile=CA)
        self.assertEqual(ctx.verify_flags, reference.verify_flags & ~ssl.VERIFY_X509_STRICT)
        self.assertEqual(ctx.minimum_version, reference.minimum_version)
        # only the fixture CA is trusted: the system store was not loaded
        self.assertEqual(ctx.cert_store_stats()["x509_ca"], 1)
        # no process-wide default was changed by building the context
        self.assertEqual(ssl.create_default_context().verify_flags, before)

    def test_the_transport_uses_this_context(self):
        seen = []
        original = pveapi.verifying_context

        def spy(ca_file):
            ctx = original(ca_file)
            seen.append(ctx)
            return ctx

        pveapi.verifying_context = spy
        try:
            pveapi.urllib_transport(CA)
        finally:
            pveapi.verifying_context = original
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0].verify_flags & ssl.VERIFY_X509_STRICT)


if __name__ == "__main__":
    unittest.main()
