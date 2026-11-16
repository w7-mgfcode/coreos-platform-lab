# AGENTS.md

> Universal agent brief for **CoreOS Platform Lab**: the shared, cross-tool source of truth for
> any AI coding agent working in this repository. It points to the governing documents instead
> of repeating them. Where this file and those documents disagree, the documents win.

## Project Overview

A reproducible, single-VM container platform built as a job-application homework. One Fedora
CoreOS VM on Proxmox runs Docker CE and a Docker Compose stack: WordPress over internal HTTPS,
mail through a Postfix relay, web and mail events searchable in Grafana, and an external Checkmk
watching the system. The deliverable is a public repository that shows the result and the
process. The defining constraint: a requirement counts as done only when evidence from the lab
shows it working.

## Current State

Read this before acting. It describes how to find the state, because the state changes.

- **Planned, not built.** If `compose.yaml`, `butane/`, `Caddyfile`, `firewall/`, `scripts/`,
  `tests/` and `docs/evidence/` do not exist, nothing is built or tested. Never describe a
  requirement as built, tested or passed without committed evidence.
- **Two owner gates** (decision D-09). The publication gate holds back every commit, push,
  remote, tag and GitHub object. The implementation gate holds back all platform configuration
  and any contact with the lab. The implementation gate is open only when
  `docs/.prepare/decision-log.md` § 5 carries a dated approval line; the publication gate only
  when the owner says so. An issue, an agent report or a review opens neither.
- **Proposals are not decisions.** Everything under `docs/.prepare/` is a proposal unless the
  decision log marks it `decided`. Read the status before relying on a line.
- **A local `HANDOFF.md` may exist.** It is untracked and private. The session that leads the
  work reads it first if it is there. A worker or reviewer that was given a task packet reads
  only what the packet names, and not the handoff. Never track it, quote it in a tracked file,
  or copy its private content.
- **Other sessions may write in this checkout.** Look for unexpected files before counting,
  scanning or reviewing, and never assume a tree-wide check is still current.

## Tech Stack

All of it is planned; only the documentation and the agent tooling exist today.

- **Host**: Fedora CoreOS on Proxmox VE, from Butane/Ignition; Docker CE from Docker's
  repository in place of the built-in Moby engine; the Compose plugin
- **Services**: Caddy (TLS from its internal CA), WordPress, MariaDB, Postfix, Alloy, Loki,
  Grafana, all on one VM
- **Consumed, not operated here**: the Proxmox host, an authenticated external SMTP relay, an
  external Checkmk
- **In the repository today**: Markdown documents, Python diagram generators under `diagrams/`,
  agent tooling under `.claude/` and `.agents/`
- **CI/CD**: none yet. Planned: static checks only. CI never reaches the lab. Releases are
  tagged by hand

## Setup

There is nothing to install or start for the platform yet. Do not install tools to make a
check run: the planned static gates use pinned container images, and `butane`, `caddy` and
`shellcheck` are not assumed to be on the workstation.

## Build & Test Commands

No runnable build or test command exists for the platform. The planned gate commands are in
`.claude/rules/test-requirements.md` ("Gates"); the files they check do not exist and the
commands have never been run. Once the scaffold lands, `scripts/validate.sh` is the gate and
this section is updated in the same change.

## Validation Gates

- **Documentation changes** (the only kind possible today): every relative link and heading
  anchor resolves, Markdown tables keep their column counts, revision fields and the baseline
  index in `docs/.prepare/README.md` agree, and no private data enters a tracked file.
- **Platform changes** (after the implementation gate): the static gates, then the acceptance
  checks on the lab. Do not commit on red. A check that was not run is recorded as not run.

## Architecture & Conventions

- **Source of truth**: `docs/architecture.md`. Its requirements table (§ 2) and acceptance
  table (§ 10) are not changed without the owner.
- **Binding scope**: Docker Compose on one VM, no cluster; Docker CE, not Moby; the host
  firewall layer is mandatory. Swarm, Kubernetes and high availability are excluded.
- **Least exposure**: only Caddy publishes a port (TCP 443). The database, SMTP, Loki, Grafana
  and the Docker API are never published.
- **Firewall**: rules for published container ports live in the `DOCKER-USER` chain, and every
  blocked path has a negative test.
- **Acceptance checks** AC-01 … AC-10. AC-05 (relay refusal) and AC-07 (firewall) are
  load-bearing: never weaken them or narrow their sources to make a change pass.
- **Decision records**: decisions, proposals and open questions live in `docs/.prepare/` with
  IDs (`D-nn`, `OQ-nn`). Never reuse an ID, and never turn a proposal into a decision.
- **Shared files** (`compose.yaml`, the Butane file, `Caddyfile`, the secrets example file)
  have one designated writer at a time. Operations that change the lab are serialized.
- **Language**: `README.md`, `docs/architecture.md` and `docs/alternatives/` are Hungarian;
  everything else is English. Nothing is translated or duplicated until the owner decides which
  files need both languages (D-46).

## Testing Requirements

- A new service, port, firewall rule, first-boot unit or pinned-version change needs the checks
  listed in `.claude/rules/test-requirements.md` ("When new tests are required").
- A negative test must fail for the right reason: the service answers an allowed source in the
  same run, and the forbidden source is refused.
- Evidence records the date, the VM build and the versions, and never contains secrets or
  third-party data.

## Safety

**Hard rules: never violate.**

- No secret in git, in a Butane or Ignition file, in `compose.yaml`, in an image layer, or in
  issue or PR text. Rendered `*.ign` is never committed.
- Never disable TLS verification, SELinux or the firewall to make something work or pass.
- No `ports:` on any service but Caddy; no unpinned image.
- No real name, mail address, lab address or host name, absolute home path or token in any
  tracked file, issue, PR or board item. Lab-private values come from variables.
- Do not contact the lab VM or the Proxmox host, and do not read credential files, unless the
  implementation gate is open and the task says so.
- **Lab-access tooling is excluded from the initial publication** (decision D-49) and is not
  in this repository. A working copy may still hold it as local, untracked files: scripts, an
  agent definition, an MCP server entry, proposed governance changes. It is not authorized. Do
  not run, start, apply or repair any of it, and do not contact the lab with it, until the
  owner has recorded the authorization.
- **A guard hook may run on shell commands in a local Claude Code session.** It can deny
  commands whose text names an owner-only tool or key, and it blocks the call if the hook
  itself fails. If shell commands start failing with a hook block, stop and report; do not
  work around it. If a local MCP server fails at startup, report it; do not install anything
  to repair it.

**Stop and ask the owner before:**

- any commit, branch, tag, push, remote or GitHub object;
- anything that touches the lab, a credential or a privileged operation;
- editing `.claude/rules/`, hooks or settings, or the two tables of the architecture;
- recording a decision or an approval, or renumbering decision IDs;
- deleting or overwriting files you did not create, including handoffs.

## Git & PR Conventions

- **Branches**: `<type>/<scope-slug>`, cut from an up-to-date `main`, one per issue
  (`.claude/rules/branch-naming.md`).
- **Commits**: `type(scope): description (#issue)` with a scope from the allow-list and an open
  issue (`.claude/rules/commit-format.md`). No AI co-author or "Generated with" line, ever.
- **Flow**: issue → branch → pull request → `main`. No `dev` branch. The one exception is the
  bootstrap commit: a single direct push to `main` under the bootstrap issue (decision D-28),
  which still needs the owner's go-ahead. One SemVer train, tagged by
  hand after the release gate; ask the owner before any tag (`.claude/rules/versioning.md`).
- **GitHub work** belongs to the `github-steward` role, and its publishing stage starts only
  after the publication gate.

## Deep-Dive Docs

Load only what the current task touches.

- Architecture, requirements, acceptance table: `docs/architecture.md`
- What is decided, proposed, open: `docs/.prepare/decision-log.md`,
  `docs/.prepare/open-questions.md`
- Order of work and how each check is proven: `docs/.prepare/implementation-plan.md`
- Issue tree and dependencies: `docs/.prepare/github-project-plan.md`
- Readiness, gate decisions, what remains unverified: `docs/.prepare/readiness-report.md`
- Index and revision baseline of the preparation package: `docs/.prepare/README.md`
- Policy: `.claude/rules/` (vision and scope lock, security patterns, test requirements, commit
  format, branch naming, versioning, output formatting, and Herdr orchestration, which also sets
  the worker models and how independent review is done)
- Rejected alternative, background only: `docs/alternatives/swarm.md`
