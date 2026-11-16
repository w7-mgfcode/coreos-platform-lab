"""Redaction for logs and sanitization for public evidence.

``redact`` removes secrets: it runs on every log line the tooling writes.
``sanitize`` additionally replaces lab-private identifiers (addresses, names) with
placeholders: it runs on evidence before it enters the public repository.
``scan`` reports anything that should not be published; it is the check, not the fix.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.S),
     "<redacted-private-key>"),
    (re.compile(r"PVEAPIToken=[^\s'\"]+"), "PVEAPIToken=<redacted>"),
    (re.compile(r"(?i)(authorization:\s*)\S.*"), r"\1<redacted>"),
    (re.compile(r"(?i)(\"?(?:password|passwd|secret|token_value|value)\"?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)"),
     r"\1<redacted>"),
    (re.compile(r"(?i)(--password[= ])\S+"), r"\1<redacted>"),
    (re.compile(r"CORELAB_TOKEN_SECRET=\S+"), "CORELAB_TOKEN_SECRET=<redacted>"),
]

_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_IPV4 = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_MAC = re.compile(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Addresses that are fine in public text: documentation ranges, loopback, unspecified.
_PUBLIC_OK_V4 = re.compile(r"^(?:192\.0\.2\.|198\.51\.100\.|203\.0\.113\.|127\.|0\.0\.0\.0$)")


def redact(text: str) -> str:
    """Remove secret values; keeps everything else readable."""
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


# No word boundary: a secret printed with letters or digits glued to it must not survive.
_UUID_ANYWHERE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def redact_uuids(text: str) -> str:
    """Replace UUID-shaped strings wherever they occur, also with other characters glued to them.
    A Proxmox token secret is a UUID, so a log of the token action must not show one in any shape
    the host happens to print it. (It also hides ordinary UUIDs; that is the point here.)"""
    return _UUID_ANYWHERE.sub("<redacted-uuid>", text)


class SecretScrubber:
    """Exact-value scrubber for credentials that become known while a command runs. Unlike a
    pattern it does not depend on how the host formats the line: any occurrence of a registered
    secret, in any letter case and glued to any other text, is replaced. It is kept alive through
    error handling and draining, so a failure cannot make it forget the value."""

    def __init__(self) -> None:
        self._patterns: list[re.Pattern[str]] = []

    def add(self, secret: str) -> None:
        if secret:
            self._patterns.append(re.compile(re.escape(secret), re.IGNORECASE))

    def scrub(self, text: str) -> str:
        for pattern in self._patterns:
            text = pattern.sub("<redacted>", text)
        return text


# Candidate IPv6 text; ipaddress decides whether it really is one (times like 12:34:56 are not).
_IPV6_CANDIDATE = re.compile(r"(?<![0-9A-Za-z:.])[0-9A-Fa-f:]*:[0-9A-Fa-f:.]*(?![0-9A-Za-z:])")


def _ipv6_findings(text: str):
    """Yield (start, end, address) for each IPv6 address in ``text`` that is not fine in public
    text: the documentation range 2001:db8::/32, loopback and unspecified are fine."""
    for m in _IPV6_CANDIDATE.finditer(text):
        token = m.group(0).rstrip(".")  # a full stop that ends a sentence is not part of the address
        try:
            addr = ipaddress.IPv6Address(token)
        except ValueError:
            continue
        if addr.is_loopback or addr.is_unspecified or addr in _DOC_V6:
            continue
        if addr.ipv4_mapped is not None and _PUBLIC_OK_V4.match(str(addr.ipv4_mapped)):
            continue  # ::ffff: plus a documentation or loopback IPv4 address
        yield m.start(), m.start() + len(token), addr


_DOC_V6 = ipaddress.IPv6Network("2001:db8::/32")


def sanitize(text: str, mapping: Mapping[str, str] | None = None) -> str:
    """Redact, replace known lab values, then pseudonymise addresses consistently."""
    text = redact(text)
    for real in sorted(mapping or {}, key=len, reverse=True):
        if real:
            text = text.replace(real, mapping[real])
    text = _UUID.sub("<uuid>", text)
    text = _EMAIL.sub("<email>", text)

    seen: dict[str, str] = {}

    def _pseudo(kind: str, value: str) -> str:
        if value not in seen:
            seen[value] = f"<{kind}-{sum(1 for v in seen.values() if v.startswith('<' + kind)) + 1}>"
        return seen[value]

    text = _MAC.sub(lambda m: _pseudo("mac", m.group(0).lower()), text)
    text = _IPV4.sub(
        lambda m: m.group(0) if _PUBLIC_OK_V4.match(m.group(0)) else _pseudo("ipv4", m.group(0)), text
    )
    pieces, last = [], 0
    for start, end, addr in _ipv6_findings(text):
        pieces += [text[last:start], _pseudo("ipv6", str(addr))]
        last = end
    return "".join(pieces) + text[last:]


def scan(text: str, mapping: Mapping[str, str] | None = None) -> list[str]:
    """List the reasons this text must not be published. Empty means clean."""
    findings = []
    for real in mapping or {}:
        if real and real in text:
            findings.append(f"lab value for {mapping[real]} present")
    # Match real values, not the pattern text that redaction code itself contains.
    if re.search(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----\s*\n[A-Za-z0-9+/=\s]{16,}", text):
        findings.append("private key block")
    if re.search(r"PVEAPIToken=[^\s'\"<=]+=[0-9A-Za-z-]{8,}", text):
        findings.append("API token header")
    if re.search(r"CORELAB_TOKEN_SECRET=[0-9A-Za-z-]{8,}", text):
        findings.append("token secret line")
    if _UUID.search(text):
        findings.append("UUID (possible token secret)")
    for m in _IPV4.finditer(text):
        if not _PUBLIC_OK_V4.match(m.group(0)):
            findings.append(f"IPv4 address {m.group(0)}")
            break
    for _start, _end, addr in _ipv6_findings(text):
        findings.append(f"IPv6 address {addr}")
        break
    if _MAC.search(text):
        findings.append("MAC address")
    if _EMAIL.search(text):
        findings.append("mail address")
    return findings
