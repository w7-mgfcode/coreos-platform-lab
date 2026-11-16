# Product Vision Alignment

Before creating issues, planning features, or starting work, check that the proposed work aligns with CoreOS Platform Lab's core identity. The source of truth is `docs/architecture.md` (the single-VM Compose architecture) together with the reviewer's scope answers of 2026-11-13, recorded below. When this file and the architecture document conflict, the architecture document wins. The Swarm variant is a rejected alternative and is background only, never an execution instruction.

## What CoreOS Platform Lab Is

A reproducible, single-VM container platform built as a job-application homework. One Fedora CoreOS VM on Proxmox runs Docker CE and a Docker Compose stack: an internal HTTPS WordPress site that sends mail through a Postfix relay, with web and mail events searchable in Grafana and the system watched by an external Checkmk.

It is an operations portfolio project. The deliverable is a public GitHub repository that shows both the result and the development process: versioned configuration, issues and PRs, and recorded evidence that each requirement works.

## Binding scope decisions (reviewer, 2026-11-13)

1. **Docker Compose on one VM**, as one or more Compose projects. No cluster.
2. **Docker CE, not the Moby engine** that Fedora CoreOS ships.
3. **The host firewall layer is mandatory.** The Proxmox firewall and Docker-network isolation are welcome extras.

These came from the evaluator. They override earlier recommendations and are not reopened without the owner.

## Core Principles

1. **Meet the brief, prove it with evidence.** A requirement is done only when a command output, test result or screenshot shows it working on the lab. Planned is not done; never describe an untested item as complete.
2. **One VM, one Compose stack.** Start with a single Compose project. Splitting into an application project and a logging project is allowed later, with the shared networks documented.
3. **Docker CE by the official FCOS method.** A first-boot systemd unit replaces the base packages with `rpm-ostree override remove … --install docker-ce`, installs the Compose plugin explicitly, and reboots. The repo definition ships in Butane, not fetched at boot.
4. **Reproducible from version control.** Butane is the versioned source and Ignition delivers only the initial machine configuration. A new VM must be buildable from the repository and its documented sources.
5. **Host firewall first, proven by negative tests.** Rules for published container ports live in the `DOCKER-USER` chain. Every blocked path has a test showing the connection is refused.
6. **Least exposure.** Only Caddy is reachable from the client network. The database, SMTP, Loki and the Docker API are never published.
7. **Trust without exceptions.** Internal TLS comes from Caddy's internal CA and the root certificate is distributed to clients. Verification is never switched off to make a check pass.
8. **Honest limits.** The VM, its storage and the Proxmox host are single points of failure. This is not a high-availability system; the docs say so and do not imply otherwise.
9. **Controlled updates.** Zincati reboots only in a maintenance window, container images are pinned, and a Fedora major rebase is checked against the Docker repository first.

## Scope Lock

| Requirement | Tier | Decision |
|-------------|------|----------|
| Fedora CoreOS VM on Proxmox | MUST HAVE | One VM from Butane/Ignition |
| Docker CE environment | MUST HAVE | Docker CE from Docker's repository, replacing Moby |
| Web service | MUST HAVE | WordPress and MariaDB |
| HTTPS reverse proxy | MUST HAVE | Caddy |
| Internal CA with automation | MUST HAVE | Caddy `tls internal`, automatic issue and renewal |
| SMTP container | MUST HAVE | Postfix relay to an authenticated external relay |
| Searchable logs | MUST HAVE | Alloy, Loki, Grafana |
| External monitoring | MUST HAVE | Checkmk agent and active checks |
| Host firewall | MUST HAVE | `DOCKER-USER` rules with positive and negative tests |
| Proxmox firewall | EXTRA | Welcome by the reviewer; built after the host layer |
| Docker-network isolation | EXTRA | Welcome by the reviewer; built after the host layer |
| Backup and restore | OPTIONAL | Optional in the brief; planned in the architecture |
| Compose secrets mechanism | OPTIONAL | Optional in the brief; keeping secrets out of git is not optional |
| Controlled update procedure | OPTIONAL | Optional in the brief; planned in the architecture |
| Docker Swarm or any multi-node cluster | EXCLUDED | Rejected by the reviewer |
| Moby engine as the Docker runtime | EXCLUDED | The brief asks for Docker CE |
| Kubernetes, high availability, multi-host storage | EXCLUDED | Outside a single-VM homework |
| Public internet exposure, public ACME certificates | EXCLUDED | Internal lab only |

**Order of work:** every MUST HAVE row first, then EXTRA, then OPTIONAL. An EXTRA or OPTIONAL item never delays a MUST HAVE row.

## What CoreOS Platform Lab Is Not (Negative Guardrails)

Identity-level constraints. If a feature pushes the repo toward any of these, flag it.

- **Not a cluster.** No Swarm, no Kubernetes, no second node, no shared storage.
- **Not a high-availability system.** A host reboot is an outage; say so.
- **Not a Moby deployment.** The built-in engine is replaced, not reused.
- **Not a configuration-management showcase.** Ignition runs once. No Ansible, Terraform or similar layer unless the owner asks for it.
- **Not a public service.** No public DNS, no public certificates, no internet-facing ports.
- **Not a WordPress project.** WordPress is the demo workload. Themes, content and plugin work beyond what mail and the demo need are out of scope.
- **Not a monitoring server build.** Checkmk is external; this repo integrates with it and does not operate it.

## Out of Scope (Hard No)

Do not propose or build:
- Swarm, Kubernetes, or any multi-VM topology
- Replacing a chosen component (Caddy, WordPress, MariaDB, Postfix, Alloy, Loki, Grafana, Checkmk) without an owner decision
- Disabling SELinux, TLS verification or the firewall to make something work
- Published ports for the database, SMTP, Loki, Grafana or the Docker API
- Any EXTRA or OPTIONAL item while a MUST HAVE row is unproven

## The Litmus Test

When evaluating an idea, ask:
1. Is it a row in the scope lock, or does it fix a correctness, security or demonstration-blocking problem?
2. Does it run on one FCOS VM with Docker CE and Compose?
3. Is it reproducible from the repository on a fresh VM?
4. Does it keep exposure to Caddy on 443 and keep every other service unpublished?
5. Does it keep secrets and lab-private data out of the public repository?
6. Can it be proven with a command, a test or a screenshot, including a negative test where it blocks something?
7. Does it pass the static gates and its acceptance check in `test-requirements.md`?

If any answer is "no" or "unclear", flag the concern before proceeding.

## When Ideas Don't Align

- Don't silently proceed. Raise the concern directly.
- Cite the specific principle or scope-lock row it conflicts with.
- Suggest an alternative that fits the single-VM architecture.
- If the user wants to proceed despite the concern: go ahead, but note the vision tension in the issue or PR description.

## When Ideas Are Ambiguous

- Ask which scope-lock row and which tier the work belongs to.
- Ask which commit scope owns it (`commit-format.md`).
- Check whether it adds a service, a published port or an external dependency.
- Default to deferring rather than guessing.

## Language

The repository is bilingual, English and Hungarian, where that is needed (owner decision of 2026-11-14, D-46 in `docs/.prepare/decision-log.md`). Which files need both languages is not decided yet.

Until the owner decides that, every file stays in the language it is written in today. The architecture and delivery documents are written in Hungarian, the reviewer's language. Commit messages, branch names, identifiers and the files under `.claude/` are in English. Nothing is translated, renamed or created for this until then.
