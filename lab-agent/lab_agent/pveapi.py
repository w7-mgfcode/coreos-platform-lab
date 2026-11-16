"""Minimal Proxmox VE API client for the routine token.

TLS is always verified against the cluster CA file; there is no switch to turn that off.
The transport is injectable so every test runs against fixtures, never a real host.
"""

from __future__ import annotations

import functools
import http.client
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from .config import ConfigError, validate_host, validate_port

# (method, url, headers, body) -> (status, body bytes)
Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]]


class PveError(Exception):
    def __init__(self, status: int, message: str, path: str):
        super().__init__(f"{status} {path}: {message}")
        self.status = status
        self.path = path
        self.message = message

    @property
    def permission_denied(self) -> bool:
        return self.status == 403


class PveTransportError(OSError):
    """The HTTP exchange broke in a way that is not an OS error (a malformed response)."""


class _BoundHTTPSHandler(urllib.request.HTTPSHandler):
    """HTTPS with the same verifying context, from a fixed local source address."""

    def __init__(self, context: ssl.SSLContext, source_address: str):
        super().__init__(context=context)
        self.source_address = (source_address, 0)

    def https_open(self, req):
        conn = functools.partial(http.client.HTTPSConnection, source_address=self.source_address)
        return self.do_open(conn, req, context=self._context)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect: the request carries the token and would be repeated, with the
    same Authorization header, towards a place the owner did not configure."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_ERROR_BODY_LIMIT = 65536
_ERROR_TEXT_LIMIT = 200  # characters of server text kept in an error, cut only after scrubbing


def verifying_context(ca_file: str) -> ssl.SSLContext:
    """The one TLS context of the API client: the certificate chain must lead to ``ca_file``
    (the only trust root; the system store is not loaded), the certificate must be valid now,
    and it must name the host that was asked for.

    One thing is relaxed, in this context only: ``VERIFY_X509_STRICT`` is cleared. Python 3.13
    and later set that flag in ``ssl.create_default_context``. It adds RFC 5280 conformance
    checks on the certificates' extensions, and one of them (OpenSSL verify code 92, "CA cert
    does not include key usage extension") refuses the cluster CA a Proxmox VE host generates
    for itself, which has critical basic constraints but no key usage extension. With the flag
    set, no API connection is possible without reissuing the host's CA (seen on 2026-11-16,
    Python 3.14, OpenSSL 3.5). Clearing it restores the verification Python did up to 3.12:
    signature chain, validity period, basic constraints and host name are all still checked.
    Nothing else is relaxed, there is no unverified fallback, and no process-wide default is
    touched: only this context object is changed."""
    context = ssl.create_default_context(cafile=ca_file)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


def urllib_transport(ca_file: str, timeout: float = 30.0, source_address: str | None = None) -> Transport:
    """HTTPS transport that trusts only ``ca_file`` and checks the host name.

    Whatever the arguments: no proxy (environment proxy variables are ignored, never used),
    no redirect (a 3xx answer is returned to the caller as it is, and ``Client`` refuses it),
    https URLs only. With ``source_address`` the connection is also bound to that local
    address; without it the kernel chooses the source (``Client.from_config`` only builds that
    form on an explicit opt-in)."""
    context = verifying_context(ca_file)
    https = (_BoundHTTPSHandler(context, source_address) if source_address is not None
             else urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect(), https)

    def send(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, bytes]:
        if not url.startswith("https://"):
            raise ValueError("the API client speaks https only")
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with opener.open(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:  # 3xx arrives here too, because nothing follows it
            try:
                return exc.code, exc.read(_ERROR_BODY_LIMIT)
            finally:
                exc.close()
        except http.client.HTTPException as exc:
            raise PveTransportError(f"malformed HTTP answer ({type(exc).__name__})") from None

    return send


def _stderr_notice(text: str) -> None:
    print(text, file=sys.stderr)


def _authority(host: str, port: str | int) -> str:
    """``host:port`` for a URL; an IPv6 literal is bracketed."""
    validate_host(host)
    port = validate_port(str(port))
    return f"[{host}]:{port}" if ":" in host else f"{host}:{port}"


class Client:
    def __init__(self, host: str, port: str | int, token_id: str, token_secret: str,
                 transport: Transport):
        self._base = f"https://{_authority(host, port)}/api2/json"
        # Built once; the header value is never logged or returned.
        self._headers = {"Authorization": f"PVEAPIToken={token_id}={token_secret}",
                         "Accept": "application/json"}
        self._send = transport
        # The known credential, kept only to scrub it from anything the server sends back.
        self._scrubber = re.compile(re.escape(token_secret) if token_secret else r"(?!)", re.IGNORECASE)

    @classmethod
    def from_config(cls, cfg: Any, transport: Transport | None = None, *, allow_unbound: bool = False,
                    notice: Callable[[str], None] | None = None) -> "Client":
        """Build the client from the settings.

        PVE_WORKSTATION_ADDR is required: the connection is bound to that validated address,
        never uses a proxy and never follows a redirect. Without the setting this refuses.
        A caller that really needs the unbound form passes ``allow_unbound=True``: it gets the
        kernel's choice of source address (still no proxy, still no redirect) and a notice on
        stderr, or on ``notice``. No command line option sets it. An injected ``transport`` is
        used as given: whoever injects it owns the question of the source address.

        With the address set, an HTTPS proxy in the environment is refused loudly rather than
        ignored: the owner configured a proxy, so the direct, bound connection is a surprise."""
        host, port = cfg.host(), cfg.port()
        source = cfg.workstation_addr() if cfg.has("PVE_WORKSTATION_ADDR") else None
        if transport is None:
            if source is None:
                if not allow_unbound:
                    raise ConfigError("PVE_WORKSTATION_ADDR is not set: the API client does not connect from an "
                                      "unbound source address (see README, step 2)")
                (notice or _stderr_notice)("lab-agent: notice: PVE_WORKSTATION_ADDR is not set; the API connection "
                                           "uses the source address the kernel chooses (no proxy, no redirect)")
            else:
                proxy = urllib.request.getproxies().get("https")
                if proxy and not urllib.request.proxy_bypass(host):
                    raise ConfigError("an HTTPS proxy is set in the environment; the API connection goes direct "
                                      "from PVE_WORKSTATION_ADDR and never through a proxy. Add PVE_HOST to "
                                      "no_proxy or unset the proxy variables")
            transport = urllib_transport(str(cfg.path("PVE_CA_FILE")), source_address=source)
        return cls(host, port, cfg.token_id(), cfg.token_secret(), transport)

    def request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        if not path.startswith("/") or ".." in path.split("/"):
            raise ValueError(f"unsafe API path: {path!r}")
        url = self._base + urllib.parse.quote(path, safe="/@!:")
        body = None
        headers = dict(self._headers)
        if params:
            encoded = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if method == "GET":
                url += "?" + encoded
            else:
                body = encoded.encode()
                headers["Content-Type"] = "application/x-www-form-urlencoded"
        status, raw = self._send(method, url, headers, body)
        if 300 <= status < 400:
            raise PveError(status, "redirect refused (the client never follows one)", path)
        try:
            payload = json.loads(raw.decode())
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            payload = None
        if status >= 400:
            # Everything derived from the answer is scrubbed of the known credential first, by
            # exact value: a server (or anything on the path) may reflect the request header.
            # Scrub the WHOLE text first and shorten it afterwards: cutting first would leave the
            # head of a secret that straddles the cut (35 of 36 characters) that no exact-value
            # match can find any more.
            if isinstance(payload, dict):
                message = payload.get("message") or json.dumps(payload.get("errors") or "")
            else:
                message = raw.decode(errors="replace")
            raise PveError(status, self._scrub(str(message)).strip()[:_ERROR_TEXT_LIMIT], path)
        # A success answer must be the object PVE sends: {"data": ...}. Anything else is a
        # transport-level problem (a proxy page, a truncated body), not "no data".
        if not isinstance(payload, dict) or "data" not in payload:
            raise PveTransportError(f"{method} {path}: the answer is not a PVE JSON object with a data member "
                                    f"(status {status})")
        return payload["data"]

    def _scrub(self, text: str) -> str:
        """Remove the token secret, and the header value built from it, from ``text`` (exact value,
        any letter case; not a pattern)."""
        return self._scrubber.sub("<redacted>", text)

    def get(self, path: str, **params: Any) -> Any:
        return self.request("GET", path, params or None)

    def post(self, path: str, **params: Any) -> Any:
        return self.request("POST", path, params or None)

    def put(self, path: str, **params: Any) -> Any:
        return self.request("PUT", path, params or None)

    def delete(self, path: str, **params: Any) -> Any:
        return self.request("DELETE", path, params or None)


class FakeTransport:
    """Fixture-backed transport for tests: maps (METHOD, path) to (status, data)."""

    def __init__(self, routes: dict[tuple[str, str], tuple[int, Any]]):
        self.routes = routes
        self.calls: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def __call__(self, method: str, url: str, headers: dict[str, str], body: bytes | None):
        self.calls.append((method, url, headers, body))
        path = urllib.parse.unquote(urllib.parse.urlsplit(url).path.split("/api2/json", 1)[1])
        status, data = self.routes.get((method, path), (404, None))
        if status >= 400:
            return status, json.dumps({"data": None, "message": data or "not found"}).encode()
        return status, json.dumps({"data": data}).encode()
