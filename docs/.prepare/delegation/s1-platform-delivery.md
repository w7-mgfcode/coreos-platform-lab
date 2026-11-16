# S1 — Platform Design and Delivery Sequence — CoreOS Platform Lab

| Field | Value |
|---|---|
| Document ID | S1 |
| Title | Platform Design and Delivery Sequence (delegated draft) |
| Revision | r1 |
| Status | draft |
| Owner | platform-writer |
| Last updated | 2026-11-14 |
| Core-context revision used | r1 (`docs-baseline-r1`) |
| Dependencies | [core-context.md](../core-context.md) r1, [source-register.md](../source-register.md) r1, [decision-log.md](../decision-log.md) r1, [open-questions.md](../open-questions.md) r1, [plan-review.md](../plan-review.md) r1, [docs/architecture.md](../../architecture.md) (read 2026-11-14), `.claude/rules/` (read 2026-11-14) |
| Change summary | r1: first draft for integration and for the critic's review |

**Nothing in this document is built or tested.** Every design below is a proposal until the owner approves it (D-09). No lab system was contacted and no command was run to write it.

## 1. Scope and inputs

**Scope** (packet S1): VM creation and Ignition delivery; Butane structure; Docker CE first-boot installation; the seven services; log collection and the WordPress mail integration; Checkmk agent options; the delivery sequence; the OPTIONAL tier in outline.

**Not in scope, owned by S2:** firewall rules, network membership and `internal` flags, TLS trust distribution, the secrets channel and file modes, relay protection, SELinux exceptions, and the design of every acceptance and negative test. Where this draft touches one of them it names the dependency as **→ S2** and stops.

**Notation.** Each material statement carries a class: **[F]** fact with a reference · **[RD]** reviewer decision · **[OR]** owner requirement · **[P]** proposal of this draft (numbered `P-nn`) · **[A]** assumption · **[OQ]** open question · **[C]** conflict. **⟨U: …⟩** marks a statement about tool behaviour that is unverified and names the spike question (`SQ-nn`, § 7.1), the static gate, or the document that would verify it. A fact here is always a fact *about a source*; no fact about the lab exists (core-context § 5).

**Requirement rows.** `RQ-1 … RQ-10` label the rows of architecture § 2 (L24–33) in table order, for reference in this draft only [P]; the table itself is not changed: RQ-1 FCOS on Proxmox · RQ-2 Docker CE · RQ-3 web service · RQ-4 HTTPS reverse proxy · RQ-5 internal CA and automation · RQ-6 SMTP container · RQ-7 searchable logs · RQ-8 external monitoring · RQ-9 firewall and isolation · RQ-10 optional operations.

**Assigned findings and where they are answered.**

| Finding | Answer in this draft | Status |
|---|---|---|
| F-01 Docker CE has no acceptance row | § 3.5, § 7.3 step D3 and D9: the three proof commands are captured at the host step and are a required part of the AC-01 evidence (D-32) | answered; the evidence file is → S2 |
| F-02 VM creation undescribed, needs root | § 2.1–2.2: the owner's root procedure after SR-22, parameterised script, API token stays read-only | answered as a design; untried; waits on OQ-02, OQ-05 |
| F-08 log route undecided | § 6.1: route A (journal) proposed, route B as fallback | **left open**: the SELinux behaviour is unverified until SQ-09; any exception is → S2 |
| F-09 first boot not reproducible, ordering unstated | § 3.2–3.4, § 5 | answered as a design; the pin syntax waits on SQ-04 |
| F-11 Postfix image and mail integration not chosen | § 4 note, § 6.2: integration proposed (P-10); image criteria and a preference stated (P-12) | integration answered; **image left open**: no image documentation is in the register, so no candidate can be cited |
| F-12 AC-01 does not say what a rebuild includes | § 7.4: fresh build per D-32, its documented sources listed | answered, conditional on the owner confirming D-32 |
| F-13 firewall built before anything to test | § 7.3 steps D4 and D9: Caddy itself is the stub (P-14); AC-07 claimed only at D9 | answered |
| F-14 three rows without an acceptance row | § 7.5 maps every row to a step and to a check or a named evidence item | answered for sequencing; naming the evidence items is → S2 |
| F-17 blocked host update unnoticed | § 8.3, SQ-12 | **left open**: OPTIONAL tier, and no Zincati source is in the register |
| F-19 static gates cannot run as written | § 7.2 | answered as a design; OQ-18 closes only when the commands are run |

## 2. Host provisioning

### 2.1 What the sources give

- [F] The upstream procedure runs every command as `root` on the Proxmox VE host (SR-22 L7), needs a storage that accepts snippets (L22–31), downloads the FCOS image for the platform (L33–51), creates the VM and hands over Ignition through a cloud-init vendor snippet, `--cicustom vendor=…` (L94–124), and describes a static address (L132–146). It was not tried on the lab (SR-22 limitations).
- [F] The architecture names Butane as the versioned source and Ignition as a one-time initial configuration (SR-01 § 3 L43), a stable address and name resolution (L41), and leaves VM size open (L42).
- [F] Agents may hold only a read-only auditor token unless the owner agrees to more (SR-07 "Lab access"); the owner is the only one who runs anything against the lab (core-context § 3).
- [A] A-08: the owner can run root commands on the Proxmox host. [A] A-01: the host has capacity. Both unconfirmed (OQ-05, OQ-02).
- ⟨U⟩ This session did not open the upstream page; the statements above are the register's and the review's account of it. The exact commands, and whether L33–51 includes a checksum or signature check of the image, must be read from SR-22 before the script is written.

### 2.2 Procedure (P-01)

[P] **P-01** — VM creation is the owner's root procedure, not an agent action, carried by one parameterised script (planned path `scripts/`, scope `host`) that reads lab-private values from an untracked variables file; the repository tracks only an example with placeholders. Serves RQ-1, product-vision principle 4, R-02.

| # | Step | Where | Privilege | Basis |
|---|---|---|---|---|
| 1 | Render Ignition from Butane with `--strict`; the `.ign` file stays untracked | workstation | none | SR-07 "Forbidden" (no committed Ignition); SR-08 "Gates" |
| 2 | Enable snippets on a storage (once per host) | Proxmox host | root | SR-22 L22–31 |
| 3 | Fetch the pinned FCOS image and check it against its published checksum | Proxmox host | root | SR-22 L33–51; the check is [P] ⟨U: read L33–51⟩ |
| 4 | Copy the rendered Ignition into the snippet storage | Proxmox host | root | SR-22 L94–124 |
| 5 | Create the VM, import the disk, attach the vendor snippet, set size and network | Proxmox host | root | SR-22 L94–124; size is OQ-02 |
| 6 | Set the address | Proxmox side or DHCP reservation | root or network admin | SR-22 L132–146 ⟨U: mechanism not quoted in the register⟩; OQ-06 |
| 7 | Start the VM; first boot continues in § 3 and § 5 | Proxmox host | root | — |
| 8 | Read-only confirmation that the VM exists with the intended settings | workstation | auditor token | SR-07 "Lab access" |

- [P] The script prints each privileged command before running it and writes a run log; that log is the raw material of the AC-01 evidence (SR-08 AC-01 "run log of a fresh build"). How the log becomes an evidence file is → S2.
- [P] The Ignition file in snippet storage is readable by whoever administers the host, which is one more reason it carries no secret (SR-07 "Forbidden").
- [OQ] OQ-02 (size, capacity for a second VM during AC-01), OQ-05 (privileges), OQ-06 (address, name resolution) are the owner's. This draft sets no CPU, memory or disk figure.

### 2.3 Butane structure (P-02, P-03)

**Contains** [P], each item with the row or rule it serves:

| Item | Content | Serves |
|---|---|---|
| Identity | host name `app-01`; user `core` with the admin public key; no password | SR-01 § 3 L41; SR-07 "Host" (key-only SSH) |
| Docker CE source | the repository definition and its signing key as files (§ 3.2) | D-24; SR-07 "Forbidden" (no repository definition fetched at boot); R-09 |
| First-boot unit | the Docker CE installation unit (§ 3.2) | RQ-2; product-vision principle 3 |
| Engine configuration | the daemon configuration file: log driver (§ 6.1) and whatever → S2 requires for the firewall backend and IPv6 | RQ-7, RQ-9 |
| Update policy | the Zincati strategy file with the maintenance window | D-25; values are OQ-12 ⟨U: file format — Zincati documentation, not in the register⟩ |
| Journal limits | a size cap for the journal, part of the "rotation" leg of the disk rule | SR-07 "Logs" |
| Directories | `/var/lib/corelab` with a stack directory and a secrets directory (ownership and mode → S2) | SR-01 § 3 L46; D-07 |
| Stack files | `compose.yaml`, `Caddyfile` and the service configuration, embedded from the repository at render time (P-03) | product-vision principle 4 |
| Boot units | the firewall unit (content → S2) and the stack unit (§ 5) | SR-01 § 3 L45; R-03 |
| Monitoring | the agent files and its socket or key, once § 6.3 is decided | RQ-8 |

**Must not contain:** any secret, including relay credentials, database passwords and the Grafana admin password (SR-07 "Forbidden"); a download of a repository definition or a `curl … | sh` (SR-07); a lab-private value in the tracked file; anything that needs re-running, because Ignition runs once (SR-01 § 3 L43; product-vision "Not a configuration-management showcase").

- [P] **P-02** — Lab-private values (address, gateway, resolver, the admin public key with its comment, VM identifier, storage name) never appear in the tracked Butane file. They are script parameters (§ 2.2) or come from an untracked local include with a tracked example. Serves SR-07 "Public repository hygiene" and D-07/D-08. ⟨U: whether the Butane variant in use supports a local include for SSH keys — `butane --strict` at the scaffold step.⟩
- [P] **P-03** — The initial stack files reach the VM inside Ignition, embedded from the repository's own files, so a fresh VM needs no second copy step for configuration. Later changes on a running VM are the owner's documented copy over SSH followed by a restart of the stack unit; this is a manual procedure, not a configuration manager. Alternatives considered: cloning the repository on the VM at boot (fetches at boot and needs outbound access to GitHub) and copying everything after first boot (one more manual step in AC-01). ⟨U: local file and tree embedding in the pinned Butane release — static gate.⟩ Consequence [P]: the gate command in SR-08 would need the files directory option; [F] SR-08 "Gates" already says the block is updated when the scaffold fixes the invocation.
- [OQ] **S1-Q1** — D-05 lists `compose.yaml` and `Caddyfile` at the root but no place for the Postfix, Alloy, Loki, Grafana and WordPress configuration files. A per-service directory is needed; its name is the owner's (layout is D-05).

## 3. Docker CE installation

### 3.1 What the sources give

- [RD] Docker CE, not the Moby engine (D-02).
- [F] Upstream method: a one-time systemd unit at first boot adds Docker's repository, runs `rpm-ostree override remove moby-engine containerd runc docker-cli --install docker-ce`, and reboots (SR-01 § 2 L35; SR-20 L11–43, install at L37, reboot at L39).
- [F] The upstream unit installs whatever `docker-ce` the repository offers that day (plan-review F-09, citing SR-20 L37).
- [F] Overridden base packages blocked a Fedora major upgrade once, because of a new `docker-cli` package (SR-01 § 2 L37; SR-20 L62–73).
- [P, not settled] D-24: install `docker-compose-plugin` explicitly and ship the repository file in Butane. Already written into SR-01 § 2 L35 and product-vision principle 3; the owner has not confirmed it (OQ-07).
- [A] A-03: the four package names match the FCOS release that will be used ⟨U: SQ-01⟩.

### 3.2 Unit design (P-04)

[P] **P-04** — One first-boot unit, working name `corelab-docker-ce.service`, shipped by Butane:

1. Runs once: skipped when its completion stamp exists. ⟨U: the stamp path and the unit's ordering lines in SR-20 L11–43 were not re-read; copy them from the source, do not retype from memory.⟩
2. Ordered after the network is online and **before Zincati**, so that the updater and the override do not compete for the same transaction. ⟨U: SR-20 L11–43 for the upstream ordering; Zincati documentation.⟩
3. Uses the repository file and signing key already on disk from Ignition; nothing is downloaded except the packages themselves. ⟨U: a local key file reference is accepted — SQ-05.⟩
4. One transaction: remove the four base packages, install `docker-ce` and `docker-compose-plugin` (D-24), with versions per § 3.3.
5. Writes the stamp only if the transaction succeeded, then reboots.

Serves RQ-2, D-02, D-24, product-vision principle 3, SR-07 "Host". Network dependency: the first boot needs outbound HTTPS to Docker's package host; any filter in front of the VM must allow it (→ S2, EXTRA Proxmox layer).

### 3.3 Version policy (P-05)

- [F] SR-06 says component versions are "pinned in configuration and listed in the documentation"; SR-01 § 3 L44 says the verified versions "enter the installation documentation". See conflict C-2 (§ 9).
- [P] **P-05** — (a) FCOS: record stream, version and checksum of the image used in § 2.2 step 3 in one tracked version list; that pins the *starting* release. (b) Docker CE: request explicit versions of the engine packages and the Compose plugin in the install transaction if SQ-04 shows the syntax is accepted; otherwise install unpinned, capture the installed versions in the AC-01 evidence, and state in the documentation that two builds on different days can differ. Serves product-vision principles 4 and 9, R-09, OQ-14.
- [P] Stated limit: after the first maintenance window Zincati may move the host to a newer release (D-25), so "pinned" describes the build input, not the running host for ever. Evidence must record the versions actually running (SR-08 "Evidence rules").
- ⟨U⟩ Whether a version-pinned layered package holds, or blocks, a later host update is not known from any source in the register. It belongs to the update trial (§ 8.3).

### 3.4 Failure behaviour and the gate on the engine (P-06)

- [P] If the transaction fails (no network, package set mismatch), no stamp is written and no reboot happens; the unit is failed and visible in the journal, and it runs again on the next boot.
- [P] **P-06** — The stack unit and the firewall unit are gated on the **booted system containing `docker-ce`**, not on the stamp alone. Reason: the stamp is written before the reboot, while the new packages are visible only after it; a gate on the stamp could let the stack start on the Moby engine in the minutes before the reboot. A package query as the unit's start condition closes that gap. ⟨U: a failing start condition skips the unit rather than failing it — systemd documentation; check in the spike with the unit in place.⟩ Serves D-02 and F-09.

### 3.5 Proof

[F] The requirements table names the proof: `docker version`, `rpm -q docker-ce`, `rpm-ostree status` (SR-01 § 2 L25). [P] They are captured twice: at the host step (D3) as a step exit, and inside the AC-01 run on the rebuilt VM (D9), which is where the release gate looks (D-32, R-01). Adding `docker compose version` records the plugin [P]. The evidence file and its format are → S2.

## 4. Services and persistence

[P] **Common image criteria** (c1–c6), applied to every service: (c1) published by the upstream project or as a Docker Official Image; (c2) pinned by version tag and digest and listed in the version list (SR-07 "Containers", SR-06); (c3) logs to standard output, documented (SR-01 § 4 L65); (c4) reads credentials from a file, so Compose secrets can be used (SR-07 "Secrets handling"); (c5) needs no `privileged`, host namespace or added capability (SR-07 "Forbidden"); (c6) the pinned series still receives security fixes on the day of the pin. No version is named here: none is verified.

⟨U for the whole table: image behaviour — file-based credentials, health endpoints, data paths — is not in the register. Verify each row against the image's own documentation with `upstream-claim-verify` when the image is pinned.⟩

| Service | Row | Selection criteria beyond c1–c6 | Configuration source | Persistent data | Health signal ⟨U⟩ | Starts after |
|---|---|---|---|---|---|---|
| Caddy | RQ-4, RQ-5 | standard build; the internal issuer needs no plugin | tracked `Caddyfile`; access log as structured lines on standard output | named volume for its data directory (CA keys, certificates — SR-01 § 4 L55, SR-07 "TLS") and one for its config directory | process state; the real check is the HTTPS request from outside (→ S2) | WordPress and Grafana **started**, not healthy (see note 2) |
| WordPress | RQ-3 | variant with its own web server, so Caddy proxies plain HTTP on the internal network (SR-01 § 2 L27, § 5 L73); a CLI image of the same series for initialisation | environment plus file-based credentials; the mail plugin file mounted read-only (§ 6.2) | named volume for uploads only (P-11) | HTTP request to the login page from inside the container | MariaDB healthy |
| MariaDB | RQ-3 | a long-term-support series | environment plus file-based credentials | named volume for the data directory (SR-01 § 4 L57) | the image's own health script | — |
| Postfix | RQ-6 | no official image exists (OQ-11); criteria in the note below | tracked relay settings; relay credentials as a secret file (SR-01 § 4 L58) | named volume for the queue (SR-01 § 4 L58) | daemon status or a local SMTP greeting | — |
| Alloy | RQ-7 | c1–c6 | tracked configuration file | named volume for read positions (SR-01 § 4 L59) | readiness endpoint | Loki healthy |
| Loki | RQ-7 | single-process mode with local storage is enough for one VM | tracked configuration; retention value is OQ-20 | named volume for log data (SR-01 § 4 L60) | readiness endpoint | — |
| Grafana | RQ-7 | open-source edition | tracked data-source provisioning (SR-01 § 4 L61); admin credential from a secret file; its own login stays on (SR-07 "TLS") | named volume for users and settings (SR-01 § 4 L61) | health endpoint | Loki healthy |

Notes:

1. [P] **P-08 — Persistence rule.** Service data sits in named volumes; `/var/lib/corelab` holds the stack files and the secrets (SR-01 § 3 L46 allows both). The Compose project gets a fixed project name so that volume and network names do not change between builds; a renamed volume is a breaking change (SR-06 "SemVer mapping"). Bind-mounted configuration files need the correct SELinux label (SR-07 "Host"); which label on which mount is → S2.
2. [P] Caddy does not wait for healthy backends. A stopped WordPress then produces a gateway error at the proxy, which is the kind of event AC-06 searches for and AC-08 alerts on, instead of taking the proxy down with it.
3. [P] **P-11 — WordPress state.** Only uploads are persistent; core, plugins and themes come from the pinned image and the tracked plugin file on every start, which is what "configuration and plugins from a reproducible source" asks for (SR-01 § 4 L56). First-run initialisation (site address, admin account from a secret) is one scripted run of the CLI image, so that a rebuilt VM (AC-01) does not stop at an installation screen. ⟨U: the image's behaviour when its document root is not a volume.⟩ Stays inside "WordPress is the demo workload" (product-vision guardrail).
4. [P] **P-12 — Postfix image criteria**, in addition to c2–c6: relay host and submission port configurable; credentials read from a file; the trusted client list settable to a single address (value → S2, F-05); outbound TLS can be made mandatory (SR-07 "Mail"); log target documented (SR-01 § 4 L65 forbids assuming it). Two routes: (i) a maintained third-party image that meets every criterion on its own documentation; (ii) a small image built from a digest-pinned base with the distribution's Postfix package and a tracked configuration. **Preference: (ii)**, because every criterion is then set in a tracked file rather than by a third party's start script, and no third-party publisher sits in the path of the relay credentials. Cost of (ii): a build step on the VM and a package version to pin. The final choice is left open (F-11) until a candidate's documentation is read.
5. [P] One Compose project at first (SR-01 § 3 L49; product-vision principle 2). Splitting it is not proposed.

## 5. Boot-time start and ordering

[F] The architecture asks systemd to start the Compose project after the network and Docker (SR-01 § 3 L45). [F] The review asks that no published port exists before the host rules are loaded (F-03 b; R-03) — the rule mechanism is → S2.

[P] **P-07** — Chain and ownership:

| Boot | Order | Notes |
|---|---|---|
| First | Ignition → `corelab-docker-ce.service` → reboot | § 3.2. Firewall and stack units are skipped (P-06) |
| Every later | network online → `docker.service` → `corelab-firewall.service` (→ S2) → `corelab-stack.service` | the stack unit requires both predecessors and is tied to Docker, so a Docker restart re-runs firewall then stack — the mechanism AC-09 relies on |
| Fresh VM, before secrets arrive | as above, but the stack unit is skipped until the secrets directory is marked complete | the marker and the channel are → S2 (OQ-16, R-18) |

```ini
# illustrative, untested — ordering only; names and paths are placeholders
[Unit]
Requires=docker.service corelab-firewall.service
After=network-online.target docker.service corelab-firewall.service
PartOf=docker.service
ConditionPathExists=/var/lib/corelab/secrets/.ready
[Service]
Type=oneshot
RemainAfterExit=yes
ExecCondition=/usr/bin/rpm -q docker-ce
ExecStart=/usr/bin/docker compose --project-directory /var/lib/corelab/stack up --detach --wait
ExecStop=/usr/bin/docker compose --project-directory /var/lib/corelab/stack stop
```

- [P] `up … --wait` makes the unit fail when a service does not become healthy, so a broken start is visible to systemd and to monitoring. ⟨U: the flag in the pinned Compose version — `docker compose up --help` at the scaffold step.⟩ The start timeout must cover the first image pull; no figure is set here.
- [P] **systemd is the only starter of the stack.** Docker's own restart policy can start containers as soon as the daemon is up, which would be before the firewall unit. The restart policy is therefore chosen so that the daemon does not start containers by itself after a reboot, including an unclean one. ⟨U: which policy behaves that way — SQ-10.⟩ **Cross-draft dependency:** if S2 loads the rules before Docker starts, this constraint relaxes; the orchestrator should compare the two drafts on this point.
- [P] A reboot test for each new unit — it ran once, and the host is in the expected state afterwards — is required by SR-08 "When new tests are required"; its design is → S2.

## 6. Log collection, mail integration, monitoring agent

### 6.1 Log collection (P-09) — RQ-7, AC-06

| Route | Mechanism | Host access the collector needs | Assessment |
|---|---|---|---|
| **A (proposed)** | Docker's `journald` log driver, set in the daemon configuration; Alloy reads the journal | read-only mount of the journal directory and the machine identifier | no Docker socket; host units (install, firewall, updater, SSH) become searchable too; journal size cap gives rotation |
| B (fallback) | default log driver; Alloy discovers containers through the Docker socket | the socket | forbidden without a recorded justification (SR-07 "Forbidden"); a read-only socket mount is still API access (SR-01 § 6 L103) |
| C (rejected) | Alloy tails Docker's log files | Docker's data directory | no service name without the API, so labels would be container identifiers — against the low-cardinality rule (SR-07 "Logs") |

- [P] **P-09** — Route A. Labels: service (from the container name the journal records), host, environment (SR-01 § 7 L109); queue IDs and request IDs stay in the line. Caddy's access log and Postfix's log both go to standard output, so web and mail events take the same path.
- ⟨U⟩ Whether a container can read the journal directory under enforcing SELinux without a label option is unknown (F-08, OQ-09): SQ-09. Relabelling a system directory with a mount option is **not** an acceptable way out, since it would change the host's own labels [P]. If an exception is needed, its form and its recorded justification are → S2 (packet S2 scope h); if none is acceptable, route B with its justification, or the route stays open.
- ⟨U⟩ Journal field names for the container and the Alloy component that reads the journal: Docker and Alloy documentation (SR-27 was not retrieved).
- [P] **P-16** — The log driver is part of the daemon configuration that Ignition writes once. It must be decided from the spike **before** the host step (D3), otherwise the log step forces a rebuild or a manual host edit.
- [OQ] Loki retention and the disk alert threshold are OQ-20. The disk alert itself needs a host agent (§ 6.3); active checks alone do not see the disk.

### 6.2 Mail integration on the WordPress side (P-10) — RQ-6, AC-04

- [A] The official WordPress image contains no mail transfer agent, so PHP's built-in mail function delivers nothing (OQ-10) ⟨U: image documentation⟩.

| Option | How | Assessment |
|---|---|---|
| **Must-use plugin (proposed)** | one small tracked PHP file, mounted read-only, that points WordPress's mailer at the Postfix service over SMTP | no database state, nothing to update, reproducible from the repository (SR-01 § 4 L56) |
| SMTP plugin from the plugin directory | installed and configured in the database | settings live in the database, the plugin needs updates; more than "what mail and the demo need" (product-vision guardrail) |
| Mail wrapper inside a derived WordPress image | custom image build | a second image to maintain for one setting |

- [P] **P-10** — The must-use plugin. WordPress speaks plain SMTP to Postfix on the `mail` network only; no credentials are needed on that hop because the relay credentials live in Postfix (SR-01 § 4 L58). Whether an unencrypted hop on an internal network is acceptable follows the same reasoning as SR-01 § 5 L73 for HTTP; confirming it is → S2. ⟨U: the mailer hook's name and behaviour — WordPress developer reference.⟩
- [P] WordPress gets a **fixed address on the `mail` network**, on a fixed subnet declared in the Compose file, so that S2 can name exactly one allowed client (F-05, R-05; SR-07 "Forbidden" on `mynetworks`). The subnet is a Compose-internal value, not a lab address. Its value and the trust rule are → S2.
- [OQ] **S1-Q2** — The sender address WordPress uses must be one the external relay accepts (OQ-04). It is a mail address, so it is configuration from an untracked file, never a tracked value (SR-07 "Public repository hygiene").
- [P] A test message can be triggered without the browser through the CLI image; how AC-04 uses it is → S2.

### 6.3 Checkmk agent on an image-based host (P-13) — RQ-8, AC-08

**Every statement about Checkmk in this section is unverified against its documentation** (SR-26 not retrieved; OQ-25). [A] A-04: the host has no Python ⟨U: SQ-08⟩. [A] A-06: an instance exists (OQ-03).

| Option | What it is | For | Against |
|---|---|---|---|
| M0 Active checks only | Checkmk requests the HTTPS endpoints and checks the certificate | nothing on the host; enough for the AC-08 row as written (R-07) | no host resources, container state, queue or disk; see conflict C-3 |
| **M1 Agent script without a package (proposed)** | the agent's shell script placed on the host by Butane, started by a systemd socket or reached over SSH with a restricted key | no second layered package; host resource and disk checks | the script must match the server's version; transport and port are → S2 |
| M2 Agent as a layered package | `rpm-ostree install` of the agent package | the vendor's usual route | a second package layered on the host adds to the update risk already taken for Docker CE (F-07; SR-20 L62–73) |
| M3 Agent in a container | a container with host mounts and host namespaces | nothing installed on the host | needs privileges SR-07 forbids without justification; an eighth service |

- [P] **P-13** — M0 is the floor that gives AC-08 a route independent of unverified facts (R-07). M1 is the route for the requirement row, which names an agent (SR-01 § 2 L31), with **local checks** instead of the Docker plugin: small host scripts for Compose service state, the Postfix queue (SR-01 § 7 L111 foresees this) and, in the OPTIONAL tier, backup age and update state. Local checks run on the host with the Docker CLI, so no socket is mounted into any container. M2 and M3 are fallbacks only.
- [OQ] The decision waits on OQ-03 (which instance, which version), OQ-25 (what the agent and plugin require) and SQ-08. This draft does not choose a transport or a port.

## 7. Delivery sequence

Order follows D-33 (proposed, not settled) with one refinement, P-15. No durations are given (OQ-01). "Exit" is what must be observed and recorded before the next step starts; none of it has been observed.

### 7.1 Spike (D1)

A throwaway VM created by the procedure of § 2.2 with a minimal Butane file. It needs the implementation gate (D-09), OQ-02 and OQ-05. Spike notes are working notes, **not acceptance evidence** (R-08); they are kept outside `docs/evidence/`.

| ID | Question | Command (on the spike VM unless stated) | Decision that depends on it | Closes |
|---|---|---|---|---|
| SQ-01 | Are the four base packages present on this FCOS release? | `rpm -q moby-engine containerd runc docker-cli` (before the override) | the package list in the install transaction (P-04) | A-03 |
| SQ-02 | Does the override leave the host on Docker CE after the reboot? | `rpm-ostree status` | D-24's method is adopted as written or amended | D-02 feasibility |
| SQ-03 | Does `docker-ce` alone bring in the plugins? | `rpm -q docker-compose-plugin docker-buildx-plugin` (after an install that named only `docker-ce`) | the explicit plugin install is necessary, or kept only as a guard | OQ-13 |
| SQ-04 | Is a version-qualified package request accepted? | `sudo rpm-ostree install --dry-run docker-ce-<version>` ⟨U: the flag itself; if refused, the answer comes from a real install on a second boot⟩ | P-05: pinned versions, or record-only with a stated limit | OQ-14, R-09 |
| SQ-05 | Does the install succeed with the repository file and key shipped by Butane? | `journalctl --unit corelab-docker-ce.service --no-pager` | ship the key in Butane, or let the repository file reference Docker's key location and record that source | D-24, R-09 |
| SQ-06 | Does the `DOCKER-USER` chain exist? | `sudo iptables -S DOCKER-USER` | the host firewall mechanism (→ S2, R-03) | A-02 |
| SQ-07 | Is IPv6 active on the host? | `ip -6 addr show scope global` | equivalent IPv6 rules, or a documented "not in use" (→ S2) | OQ-15 |
| SQ-08 | Is Python present? | `command -v python3` | § 6.3: Docker plugin on the host possible, or local checks only | A-04, OQ-08 |
| SQ-09 | Can a container read the journal under enforcing SELinux? | `docker run --rm --volume /var/log/journal:/var/log/journal:ro <pinned image> ls /var/log/journal` (with `getenforce` reporting `Enforcing`) | § 6.1: route A without exception, route A with an exception (→ S2), or route B | OQ-09, F-08 |
| SQ-10 | Does the daemon start a container by itself after an unclean reboot? | `docker inspect --format '{{.State.Status}}' probe` after a forced reboot, with a container `probe` created beforehand under the candidate restart policy and the stack unit disabled | § 5: the restart policy, and whether systemd can be the only starter | F-03 b (shared with S2) |
| SQ-11 | Did Ignition arrive through the vendor snippet? | from the workstation: `ssh -o PasswordAuthentication=no core@<VM address> cat /etc/hostname` | P-01: the procedure is scripted as designed, or SR-22 is re-read for another delivery path | F-02, R-02 |
| SQ-12 | Where does a held or failed host update show? (OPTIONAL) | `systemctl status zincati.service --no-pager` | what the update-state check in § 8.3 reads | F-17, R-19 |

SQ-06 and SQ-07 are listed because R-08 puts them in the same spike; their decisions belong to S2. SQ-12 costs one command and delays nothing; it does not move an OPTIONAL item ahead of a MUST HAVE row.

### 7.2 Scaffold (D2)

- [P] Creates the layout of D-05, empty or minimal, plus `scripts/validate.sh`, the example variables file, and `docs/evidence/` with its index. Scope `repo` for layout, `tests`/`host`/`compose`/`proxy` as files gain content (SR-04).
- [P] `scripts/validate.sh` runs each static gate from a version-pinned container of the tool's own project: Butane (strict, with the files directory), `docker compose config`, `caddy validate`, `shellcheck` (SR-08 "Gates" allows this; F-19, R-17). The gate block in SR-08 is updated in the same change, as that rule requires; the rule edit itself is proposed through the readiness report, not made here.
- [P] Exit: the script passes on the scaffold and exits non-zero on a deliberately broken copy of each input (R-17 acceptance). This closes OQ-18. ⟨U: whether `docker compose config` passes when the secret source files are absent, as in CI — to be seen at this step.⟩
- [P] **P-15 — refinement of D-33.** The spike needs a rendered Ignition file, and the workstation has no Butane (core-context § 5). The pinned Butane invocation is therefore prepared before the spike; everything in the scaffold that depends on a spike answer (daemon configuration, install transaction, units) comes after. The order "spike, then scaffold" stays true for content.

### 7.3 Steps

| Step | Work | Files (planned paths; scope) | Needs | Exit condition | Rows | Feeds |
|---|---|---|---|---|---|---|
| D0 | Owner inputs; no lab contact (SR-01 § 10 step 1) | none | — | OQ-02 … OQ-07, OQ-12, OQ-14 answered or explicitly deferred | all | — |
| D1 | Spike (§ 7.1) | throwaway Butane, untracked; notes | implementation gate; OQ-02, OQ-05 | every SQ has a recorded answer; the VM is destroyed | RQ-1, RQ-2 | none claimed |
| D2 | Scaffold (§ 7.2) | D-05 layout; `scripts/validate.sh` (`repo`, `tests`) | P-15 | static gates pass and fail correctly | — | all later steps |
| D3 | Host: Butane, provisioning script, install documentation, version list | `butane/app-01.bu`, `scripts/` (`host`), `docs/` (`docs`) | D1 answers; OQ-06, OQ-12; P-16 | VM created by the owner from the repository; the three Docker CE proof commands and `docker compose version` captured; a second reboot leaves the install unit skipped and Docker running | RQ-1, RQ-2 | AC-01 (Docker CE proof), AC-09 (units) |
| D4 | Host firewall, proven against a stub (P-14: the stub is Caddy alone, with `tls internal` and a static response) | `firewall/**` (`firewall`); first `compose.yaml`, `Caddyfile` (`compose,proxy`) | rules and tests → S2; OQ-06 | S2's partial check: allowed source reaches 443, forbidden source does not, and both hold after a Docker restart and a reboot | RQ-9 (mandatory layer), RQ-4, RQ-5 begin | AC-07 **in part only**, AC-09 mechanism, AC-02 first run |
| D5 | Web: MariaDB, WordPress, the proxy route, initialisation | `compose.yaml`, `Caddyfile`, WordPress files (`compose`, `proxy`, `web`) | secrets channel → S2 (OQ-16) | login, a post and an upload through HTTPS; the upload is still there after the stack is stopped and started | RQ-3, RQ-4, RQ-5 | AC-02; AC-03 trial can start; the RQ-3 evidence item |
| D6 | Mail: Postfix, the must-use plugin, fixed addressing on `mail` | Postfix files (`mail`), plugin (`web`), `compose.yaml` | OQ-04; P-12 choice; S2 relay rule | a message from WordPress is accepted by Postfix, its queue ID appears in the log, and the hand-over to the relay is logged | RQ-6 | AC-04, AC-05 |
| D7 | Logs: Alloy, Loki, Grafana, the `logs` name on the proxy | logging files (`logs`), `compose.yaml`, `Caddyfile` | SQ-09 outcome; any exception → S2; OQ-20 | one HTTP error line and one queue ID line found by a query in Grafana, with Grafana behind its own login | RQ-7 | AC-06 |
| D8 | Monitoring: active checks, agent route, local checks | agent and check files (`monitoring`), Butane additions (`host`) | OQ-03, OQ-25, SQ-08; root CA trust in Checkmk → S2 | stopping a service changes the check state and restoring it clears the state | RQ-8 | AC-08 |
| D9 | Restart and rebuild; then the release gate | `tests/**` (→ S2), evidence (`docs`) | D3–D8; capacity for a second VM or consent to destroy the first (OQ-02) | AC-02 and AC-07 re-run after a Docker restart and after a reboot; AC-07 in full; a fresh VM built per § 7.4 | RQ-1, RQ-2, RQ-9 closed | AC-09, AC-07, AC-01; then AC-01 … AC-09 for the gate (SR-06, D-22) |
| D10 | EXTRA layers: Proxmox firewall, Docker-network isolation | → S2 | every MUST HAVE row proven (SR-03 "Order of work") | → S2 | RQ-9 (extras) | AC-07 additions |
| D11 | OPTIONAL: backup and restore, update procedure (§ 8) | scripts and documentation (`backup`) | OQ-19; D10 done or skipped by the owner | restore trial with measured times; update trial recorded | RQ-10 | AC-10; update and secrets evidence items |

- [P] **P-14** — Using Caddy as the stub at D4 avoids a throwaway service and starts RQ-4 and RQ-5 early. AC-07 is not claimed at D4: the database, SMTP and Loki paths can only fail for the right reason once those services run (SR-08 "Load-bearing tests"; F-13).
- [F] The architecture lists five networks (SR-01 § 6 L81–87). [P] They are created from D4–D7 as base design; their `internal` flags and isolation tests are the EXTRA item at D10. Where exactly that line runs is → S2 (R-10).
- [P] Tagging `v0.1.0` after D9 is the owner's act (SR-06 "Ask the owner before pushing any tag").

### 7.4 What AC-01 rebuilds (F-12)

[P, conditional on D-32] A fresh build, no data restore. Its documented sources: the repository at a named commit; the FCOS image by stream, version and checksum; Docker's package repository with the recorded key; the container images by digest; the untracked variables file and the secret source files, described by their tracked examples. Consequences: a new internal CA is created, so trust is distributed again (→ S2); WordPress is initialised again by the scripted run (P-11); the rebuilt VM needs its own address or the first VM stopped (OQ-06, OQ-02). The run log of § 2.2 and the Docker CE proof of § 3.5 are parts of the evidence.

### 7.5 Requirement rows in the sequence

| Row | Steps | Closed by |
|---|---|---|
| RQ-1 FCOS on Proxmox | D1, D3, D9 | AC-01 |
| RQ-2 Docker CE | D1, D3, D9 | the Docker CE proof inside the AC-01 evidence (D-32; F-01) |
| RQ-3 Web service | D5 | no acceptance row (F-14): a named evidence item for login, content and upload — name → S2 |
| RQ-4 HTTPS reverse proxy | D4, D5 | AC-02 |
| RQ-5 Internal CA and automation | D4, D5 | AC-02, AC-03 |
| RQ-6 SMTP container | D6 | AC-04, AC-05 |
| RQ-7 Searchable logs | D3 (log driver), D7 | AC-06 |
| RQ-8 External monitoring | D8 | AC-08 |
| RQ-9 Firewall and isolation | D4, D9 (mandatory); D10 (extras) | AC-07, AC-09 |
| RQ-10 Optional operations | D11 | AC-10 for restore; named evidence items for the update trial and for secrets (F-14) — names → S2 |

## 8. OPTIONAL tier outline

Outline only. Nothing here starts while a MUST HAVE row is unproven (SR-03 "Out of Scope"). Whether the tier is delivered at all is OQ-19.

### 8.1 Backup

- [F] To be saved: a consistent MariaDB backup, WordPress uploads, the Caddy CA and configuration, Grafana settings, and the protected material needed to restore secrets (SR-01 § 8 L117). A copy of a live database volume is not a consistent backup (L119).
- [P] Database: a logical dump made by the database's own tool inside the running container. Volumes: archived while the owning service is stopped or from a consistent source. Postfix queue: **not** backed up by default, because a restored queue can send twice (L117); stated in the procedure. Logs: not backed up unless the owner decides otherwise (L117 leaves it open).
- [F] The backup is encrypted and leaves the VM; a copy on the same physical host does not protect against losing it (L119). [OQ] Target, encryption tool, RPO and RTO: OQ-19. [P] A VM snapshot is an addition, not the backup (L119).
- [P] A scheduled host unit runs the script; a local check reports backup age (SR-01 § 7 L111; § 6.3).

### 8.2 Restore (AC-10)

[F] Order: VM and network → Docker and Compose → secrets and CA → database and uploads → services → HTTPS, mail, log and monitoring checks (SR-01 § 8 L121). [P] It reuses § 2.2 and § 3 unchanged, then restores the Caddy data volume **before** the proxy first starts, so the existing root stays valid (AC-10 "CA trust is kept"). Measured time and data loss go into the trial record. Test design is → S2.

### 8.3 Controlled update

- [P, D-25 not settled] Host: Zincati only inside the window (OQ-12); before a Fedora major rebase, check that Docker's repository serves the new release; `rpm-ostree rollback` is the way back (SR-01 § 2 L37, § 9 L125).
- [P] Images: a pin is changed by pull request, with a backup before and the affected acceptance checks re-run after (SR-01 § 9 L125; SR-08 "Change to a pinned version"). [F] Rolling an application back does not undo a database migration (SR-01 § 9 L127).
- [OQ] F-17 stays open: how a held or failed update shows on the host is unverified (SQ-12). If it is observable, one local check (§ 6.3) reports it (R-19).
- [OQ] Whether pinned Docker CE packages (P-05) hold back a host update is unknown; the update trial is where it would be seen.

## 9. Proposed changes to the core documents

For the orchestrator; this session edited none of them.

**Conflicts, reported and not resolved:**

| ID | Conflict | Sources |
|---|---|---|
| C-1 | The scope lock classes the "Compose secrets mechanism" as OPTIONAL, while the security rule makes file-based Compose secrets a required pattern and forbids inline secrets. In the sequence the mechanism is needed from D5, the first service with a credential | SR-03 scope lock; SR-07 "Forbidden" and "Secrets handling"; SR-01 § 2 L33, § 8 L115 |
| C-2 | Where versions are fixed: "enter the installation documentation" against "pinned in configuration" | SR-01 § 3 L44; SR-06 "Train" paragraph 2 (already noted in F-09) |
| C-3 | The requirement row plans "Checkmk agent and active checks"; the smallest AC-08 route in R-07 uses an active check only. AC-08 could pass while the row's agent is absent | SR-01 § 2 L31; plan-review R-07 |

**Decision log** — candidates for § 3, each awaiting the owner: P-01 (owner-run provisioning script), P-02 (lab-private values out of tracked Butane), P-03 (stack files delivered in Ignition), P-04 (install unit design; refines D-24, ordered before Zincati), P-05 (version policy), P-06 (gate on the booted engine), P-07 (systemd as the only starter; unit chain), P-08 (named volumes, fixed project name), P-09 (journal log route), P-10 (must-use mail plugin; fixed WordPress address on `mail`), P-11 (WordPress state and scripted initialisation), P-12 (Postfix image criteria and preference), P-13 (monitoring floor and agent route), P-14 (Caddy as the firewall stub), P-15 (Butane invocation before the spike), P-16 (log driver fixed before the host step).

**Open questions** — to add: S1-Q1 (where per-service configuration files live; extends D-05); S1-Q2 (the sender address the relay accepts; part of OQ-04); the restart-policy question behind SQ-10; whether a pinned layered package holds back a host update. To extend: OQ-14 with the two-way policy of P-05; OQ-09 with the statement that relabelling the journal directory is excluded.

**Core context § 11** — assumptions to add: the four in § 10 below.

**Source register** — entries that this draft needed and could not cite: Zincati configuration and update reporting; `rpm-ostree` install options; the Butane specification for local includes; each service image's documentation; the Compose reference for `--wait` and the project name; the WordPress mailer hook; Docker's `journald` driver and Alloy's journal source (SR-27 names the tutorial but it was not retrieved); SR-26 remains unretrieved.

**Rules** (through the readiness report): the SR-08 gate block gains the files-directory option if P-03 is accepted.

## 10. Completion report

| Item | Content |
|---|---|
| Session | S1, `platform-writer` |
| Baseline | `docs-baseline-r1`; plan-review r1 |
| Files created or changed | Created `docs/.prepare/delegation/s1-platform-delivery.md`. No other file created or changed |
| Evidence consulted | The delegation manifest; the five core documents; `docs/architecture.md` § 1–10; plan-review r1 (all findings and recommendations, the assigned ten in detail); the rules `product-vision`, `security-patterns`, `test-requirements`, `versioning`, `commit-format`, `branch-naming`, `output-formatting`; register entries SR-20 and SR-22 **as described in the register and quoted in the review** — the upstream pages themselves were not opened |
| Decisions proposed | P-01 … P-16 (listed in § 9; P-04 refines the still-proposed D-24). None is settled |
| Assumptions introduced | (1) each service image accepts credentials from files and offers the health signal named in § 4; (2) the pinned Butane release supports embedding local files and a local include for the SSH key; (3) a failing start condition skips a systemd unit instead of failing it, and a unit tied to Docker is re-run when Docker restarts; (4) the Checkmk agent can run as a plain script without its package. Each is marked ⟨U⟩ where used, with what would verify it |
| Open questions | Escalated to the owner, not answered: OQ-02, OQ-03, OQ-04, OQ-05, OQ-06, OQ-07 (D-24, D-25, D-32, D-33 in particular), OQ-12, OQ-14, OQ-19; new S1-Q1, S1-Q2. For the spike: SQ-01 … SQ-12. Evidence gap: OQ-25. Left open by design: F-08 (SELinux), F-11 (image), F-17 (update state) |
| Validation performed | Read-through against the packet: required structure § 1–10 present; each of the ten assigned findings has a row in § 1; each of RQ-1 … RQ-10 appears in § 7.3 and § 7.5; each of the twelve spike questions has one command and one dependent decision; no statement claims that anything is built, run or passing; no real name, address, host name or version number appears; no file under the implementation paths was created; the file is 362 lines, under the packet's limit of roughly 400. No command was run and no tool validated the fragment in § 5 |
| Limitations | Upstream behaviour is cited at second hand (register and review) or marked unverified; the unit ordering of the upstream Docker CE unit and the address mechanism of the Proxmox procedure must be read from the sources before use. S2's draft was not visible: the points marked "→ S2", and the restart-policy and rule-load ordering in § 5 in particular, need a cross-draft comparison. Effort is not estimated (OQ-01) |
| Status | **Complete** as a draft for integration and critic review. No blocker for this document; the design itself is blocked on the owner inputs and the spike listed above |
