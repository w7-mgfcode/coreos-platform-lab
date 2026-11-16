# Security Patterns

> Vision principle: **Least exposure, proven by tests.** CoreOS Platform Lab publishes one HTTPS endpoint from a single VM, keeps every other service on internal Docker networks, and lives in a public repository. Each boundary (the repo, the host, the firewall, the containers) needs its own control.

These patterns are enforced on ALL configuration and scripts in this repository. Violations must be fixed before committing.

## Forbidden — never generate

- Secrets in git: passwords, SMTP relay credentials, API tokens, private keys, the Caddy CA private key
- Secrets in a Butane or Ignition file that is committed or served from a public location
- Committed rendered Ignition (`*.ign`). It is a build artifact and may embed secret material
- Secrets inline in `compose.yaml`, in `environment:` values, in image layers, or in issue and PR text
- Credentials embedded in Git remote URLs (`https://user:token@…`)
- Disabled certificate verification as a fix or as proof: `curl -k`, `--insecure`, `verify=False`, `tls_insecure_skip_verify`, a browser exception
- `setenforce 0`, `SELINUX=disabled`, or `security_opt: label=disable` without a justification recorded next to it
- `privileged: true`, `network_mode: host`, `pid: host` or broad `cap_add` without a justification recorded next to it
- A Docker socket mount (`/var/run/docker.sock`) without a recorded justification. A read-only mount is not read-only API access
- The Docker API on a TCP port
- `ports:` on any service other than Caddy. The database, Postfix, Loki, Grafana and Alloy are never published
- Firewall rules for published container ports placed only in `INPUT`. They belong in `DOCKER-USER`
- Unpinned images: `:latest` or a missing tag. Pin a version or a digest
- A Postfix `mynetworks` wider than the fixed Compose subnet of the allowed client, or any configuration that relays for unknown clients
- `curl … | sh` in a systemd unit or script, and package repository definitions downloaded at boot instead of shipped from version control
- Echoing the Proxmox API token, or storing it anywhere but a mode-600 file outside the repository

## Required patterns

### Secrets handling

- Secrets reach the VM by a protected channel and are read by services as Compose secrets (files), one grant per service that needs it.
- Secret source files live outside the repository or under a git-ignored path. The repository carries only an example file with key names and placeholders.
- A new secret is added to the example file and to the restore procedure in the same change.
- Compose secrets give no encryption at rest on the host. Protect the source files with ownership and mode, and say so in the docs.
- Never log secret values. Log names and booleans only.

### Host (Fedora CoreOS)

- Butane is the versioned source. Ignition is rendered from it and is not committed.
- SELinux stays enforcing. Bind mounts carry the correct label (`:Z` for a private mount, `:z` for a shared one).
- Docker CE and the Compose plugin come from `download.docker.com`, with the repository file and GPG key source recorded in the install documentation.
- Zincati updates only in the documented maintenance window. `rpm-ostree rollback` is the documented way back.
- SSH is key-only and reachable from the admin network only.

### Firewall and network

- The host layer is mandatory: `DOCKER-USER` rules allow TCP 443 from the client network and drop the rest of the forwarded traffic to published ports.
- Rules survive a Docker restart and a host reboot. A test proves it.
- IPv6 either gets rules equivalent to IPv4 or is documented as not in use.
- Each service joins only the Docker networks it needs. The database and log networks have no route to the internet.
- TCP 80 is optional and, if opened, only for the internal client network. UDP 443 stays closed.
- Every rule that blocks something has a negative test (`test-requirements.md`).

### Containers

- Images are pinned by version or digest and listed in the documentation with their versions.
- Containers get only the capabilities and mounts they need. Deviations carry a comment with the reason.
- Persistent data sits in named volumes or under the documented data directory. Nothing durable lives in a container layer.

### TLS and the internal CA

- Caddy issues and renews certificates with `tls internal`. Its data directory is persistent.
- Clients and Checkmk trust the root CA's public certificate. The CA private key never leaves the VM except in an encrypted backup.
- HTTP between the proxy and an application is allowed only on the isolated internal network.
- Grafana requires its own login even behind HTTPS.

### Mail

- Postfix relays only for the designated application client and only to the designated external relay, with STARTTLS and authentication on TCP 587.
- A refused relay attempt from an unauthorised client is a required test case.

### Logs

- Loki labels are low-cardinality: service, host, environment. Queue IDs and request IDs stay in the log line.
- Logs must not contain secrets, passwords or full authentication exchanges.
- Rotation, Loki retention and a disk alert together prevent the disk from filling.

### Lab access

- The Proxmox API is used with a privilege-separated token holding the PVEAuditor role unless a task needs more. Any wider role is agreed with the owner first.
- The token lives in `~/.config/…` with mode 600. It is passed by reading the file inside the command and is never printed.
- Verify the Proxmox certificate with its CA (`--cacert`). Do not use `-k` in documented procedures.

### Public repository hygiene

- No real names, mail addresses, relay account names or public hostnames of third parties in files, issues or PRs. This includes the reviewer and the intermediary.
- `HANDOFF.md`, `.handoffs/` and `.claude/settings.local.json` stay untracked.
- Lab addresses in examples are private-range addresses or documented placeholders.
- Before the first push and before every later push, scan what will be published for secret patterns and for files that should not leave the machine.

## When adding a service or a rule

1. State which scope-lock row it serves (`product-vision.md`).
2. Attach it only to the networks it needs and publish nothing.
3. Pin the image and record its version.
4. Decide where its secrets and durable data live, and add both to the backup and restore notes.
5. Add the positive test that shows it working and the negative test that shows the blocked path is refused.

## Memory + context

- Never copy secret values into conversation memory or session notes
- Never echo secret values in tool results — even truncated
- Memory may store key NAMES and file paths, never values
