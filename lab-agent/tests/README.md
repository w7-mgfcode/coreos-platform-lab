# Test fixtures: `tls-fixture-*`

Four files in this directory are TLS test fixtures. They exist for one test module,
`test_tls_strict_compat.py`, which runs real TLS handshakes in memory (no socket, no host)
between the API client's TLS context and a server that holds these certificates.

| File | What it is |
|------|------------|
| `tls-fixture-ca-nokeyusage.pem` | Self-signed CA certificate with the shape of a Proxmox VE cluster CA: critical basic constraints (`CA:TRUE`), both key identifiers, **no key usage extension** |
| `tls-fixture-server.pem` | Leaf certificate signed by that CA for `pve-test.example.invalid` (subject alternative name `DNS:pve-test.example.invalid`, `CA:FALSE`, key usage digital signature and key agreement, extended key usage TLS server authentication) |
| `tls-fixture-server.key` | The leaf's private key, an EC P-256 key generated only for this purpose |
| `tls-fixture-ca-unrelated.pem` | A second CA certificate of the same shape that signed nothing; the test uses it to show that an unrelated CA is still refused |

## Provenance

- Synthetic and invented: every name is made up (organisation `lab-agent test fixture`, host
  name under the reserved `.invalid` top-level domain). They describe no real host, person or lab.
- Made once, on 2026-11-16, with `openssl`, by a generator script that was not kept in the
  repository. Validity 2026-01-01 to 2126-01-01, so the tests do not expire in practice.
- The private key was generated only for these fixtures and protects nothing. All keys are
  EC P-256 with ECDSA-SHA256 signatures.

What `openssl x509 -noout -subject -issuer -dates -ext
keyUsage,basicConstraints,extendedKeyUsage,subjectKeyIdentifier,authorityKeyIdentifier,subjectAltName`
shows on 2026-11-16:

- both CA certificates: subject equal to issuer, `CA:TRUE` (critical), no key usage extension;
- the server certificate: issuer is the "no key usage" fixture CA, `CA:FALSE` (critical), key
  usage critical with digital signature and key agreement, extended key usage TLS server
  authentication, subject and authority key identifiers present;
- all three: not before 2026-01-01 00:00:00 GMT, not after 2126-01-01 00:00:00 GMT.

## Rules for these files

- They are test data. Never add any of them to a trust store, a system or browser certificate
  list, a Compose secret or a lab configuration, and never reuse the key for anything.
- The private key sits here, directly in `tests/`, on purpose: the repository hygiene test
  (`RepoHygieneTests` in `test_hook_and_repo.py`) tolerates a fake private key only in this
  directory. Do not move the files and do not widen that exemption.
- Do not edit the files by hand. If a test needs a different shape, make new equivalents.

## Regenerating equivalents

The tests need the shape, not these exact bytes. Generate a fresh throw-away key for each
certificate (for example `openssl ecparam -name prime256v1 -genkey -noout` followed by
`openssl req -x509 -new` for the CAs, with `-addext basicConstraints=critical,CA:TRUE` and
subject and authority key identifiers, and no `keyUsage` extension) and sign the leaf with
`openssl x509 -req -CA ... -extfile` carrying `basicConstraints=critical,CA:FALSE`,
`keyUsage=critical,digitalSignature,keyAgreement`, `extendedKeyUsage=serverAuth` and a subject alternative name of
`DNS:pve-test.example.invalid`. Use a long enough validity and the same file names, then re-run
`test_tls_strict_compat.py`. Keep the names invented; never use a real host name.
