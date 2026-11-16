# Core Context — CoreOS Platform Lab

| Field | Value |
|---|---|
| Document ID | PREP-01 |
| Title | Core Context |
| Revision | r7 |
| Status | ready-for-human-review |
| Owner | Orchestrator session (author); approver: repository owner |
| Last updated | 2026-11-16 |
| Core-context revision used | r7 (this document) |
| Dependencies | [source-register.md](source-register.md) r7, [decision-log.md](decision-log.md) r9, [open-questions.md](open-questions.md) r7 |
| Change summary | r1: first baseline, written from the migrated architecture, the rules and both handoffs. r2: integration of the delegated sessions — assumptions A-09 … A-14 added, A-07 widened, the list of recorded tensions extended, decision and question ranges updated. No decided fact changed. r3 (2026-11-16, records reconciliation): the language constraint carries its qualification by D-46; the decision summary of § 10 and the OQ-07 line follow decision-log r5. No assumption, scope line or requirement changed. r4 (2026-11-16, documentation closeout DOC-1): the decision summary of § 10 follows decision-log r6 (D-48); § 5 carries a dated note on what the tree holds since 2026-11-14; § 6 points the open part of D-46 to OQ-35; § 9 names the agent brief. No assumption, scope line or requirement changed. r4, corrected on 2026-11-16 after an independent review (DOC-1b): the note in § 5 no longer says anything about offline work and states only that no decision and no recorded authorization exists for the tooling set. r5 (2026-11-16, decision D-49, task DOC-C): the decision summary of § 10 follows decision-log r7 and names D-49; § 5 carries a second dated note, which corrects the DOC-1 note on the tooling set. No assumption, scope line or requirement changed. r5, status set on 2026-11-16 after the independent review of the D-49 change (readiness-report § 10e): no content change. r6 (2026-11-16, decisions D-50 … D-53, task DOC-P): the decision summary of § 10 follows decision-log r8 and names D-50 … D-53 and the approved proposals, with their limits; the OQ-07 line of § 12, the terminology row on AC-01 … AC-10, the first tension of § 9, the constraint on the git identity in § 6 and the row on preparation decisions in § 9 carry dated notes; § 5 carries a third dated note. No assumption, scope line or requirement changed, and the statement of the two gates is as it was. Status `in-review` while the independent review of this pass ran; corrected on 2026-11-16 on findings of the independent review of this pass; the status was set after that review ([readiness-report.md](readiness-report.md) § 10f). r7 (2026-11-16, decisions D-54 … D-56, task DOC-R1): the decision summary of § 10 follows decision-log r9 and names D-54 (the publication go-ahead, given once and used up), D-55 (both added tree edges kept) and D-56 (the owner-only private-value scan waived: not run, never a pass), with dated notes on its "Not decided" and D-28 lines; dated notes at the sentences of § 5 that say no commit, remote, tag or GitHub object exists, in the constraint row on publication in § 6 and in the "GitHub objects" row of § 9. No assumption, scope line or requirement changed, and neither gate changed: the implementation gate is closed. Status `in-review` while the independent review of this pass ran; the status was set after that review ([readiness-report.md](readiness-report.md) § 10g) |

This is the shared context every session starts from. It holds only what a session must know to work correctly and links to the detail. Sessions do not edit it; they propose changes in their completion report and the orchestrator integrates them.

Statement classes used across this package: **fact** (verified, with a reference), **owner requirement**, **reviewer decision**, **proposal**, **assumption**, **open question**, **conflict**.

## 1. Problem statement

A job-application homework asks for a reproducible container platform on Fedora CoreOS. The owner must show that it works and how it was built. (Owner requirement; SR-01 header, SR-03 "What CoreOS Platform Lab Is".)

The brief itself is not in the repository. It is known only through its summary in the architecture (SR-01 § 2) and through the reviewer's three scope answers. (Fact about the sources; see [source-register.md](source-register.md) limitations.)

## 2. Intended outcomes

1. One Fedora CoreOS VM on Proxmox running Docker CE and a Docker Compose stack: an internal HTTPS WordPress site that sends mail through a Postfix relay, with web and mail events searchable in Grafana and the system watched by an external Checkmk. (SR-01 § 1.)
2. A public GitHub repository that shows the result and the development process: versioned configuration, issues and PRs, and recorded evidence per requirement. (Owner requirement; SR-03.)
3. Every requirement is closed by an acceptance check that ran on the lab, and every blocked path by a negative test. (SR-08.)

## 3. Stakeholders

| Role | Who | Authority |
|---|---|---|
| Owner | The repository owner | Decides everything not fixed by the reviewer; the only one who approves documents, opens the two gates, and runs anything against the lab |
| Reviewer | The evaluator of the homework | Gave the three binding scope answers on 2026-11-13; not reachable from this repository |
| Intermediary | Relays messages between owner and reviewer | None over scope |
| Orchestrator session | This preparation session | Authors the core documents, integrates, proposes; approves nothing |
| Delegated sessions | platform-writer, security-writer, plan-critic, github-steward | Write to their assigned path only; propose |

No real names, mail addresses or third-party host names appear in any tracked file (SR-07 "Public repository hygiene").

## 4. Scope and non-goals

The scope is fixed by three things and none of them is reopened here:

- the reviewer's three scope answers — [decision-log.md](decision-log.md) D-01, D-02, D-03;
- the requirements table — [architecture § 2](../architecture.md#2-követelmények-és-döntések);
- the acceptance table — [architecture § 10](../architecture.md#10-megvalósítás-és-átvételi-ellenőrzés).

Tiers (SR-03 scope lock): nine MUST HAVE rows, two EXTRA rows (Proxmox firewall, Docker-network isolation), three OPTIONAL rows (backup and restore, Compose secrets mechanism, controlled update procedure). Order of work is MUST HAVE, then EXTRA, then OPTIONAL.

Non-goals (SR-03 negative guardrails): no cluster, no high availability, no Moby engine, no configuration-management layer, no public exposure, no WordPress content work beyond the demo, no operation of the Checkmk server.

## 5. Verified current state (2026-11-14)

| Statement | Evidence |
|---|---|
| The repository holds tooling (`.claude/`, `.agents/`), the migrated architecture, the rejected Swarm alternative, seven diagrams with four generators, `README.md`, `.gitignore` and this package | directory listing after migration, SR-21 |
| Git is initialised on `main` with a repo-local identity. There is no commit, no remote, no tag | `git status`, SR-21 |
| **Nothing is built or tested.** There is no Butane file, no `compose.yaml`, no `Caddyfile`, no firewall rule, no script, no test, no CI workflow and no evidence file | directory listing, SR-21 |
| No GitHub repository, issue, label, milestone or board exists for this project | `gh repo view` returns "not found", SR-19 |
| The static gate tools `butane`, `caddy` and `shellcheck` are not installed on the workstation; `docker`, `jq` and `gh` are | `command -v`, SR-21 |
| No Proxmox API token has been created, so the host's capacity and version are unconfirmed | SR-13 "Verified Facts"; token directory absent, SR-21 |
| The lab VM does not exist | follows from the rows above; no session has contacted the lab |

*Note of 2026-11-16 (DOC-1).* The table above is the state of 2026-11-14 and is kept as written. What the tree holds on 2026-11-16, observed by listing it: `AGENTS.md` and `CLAUDE.md` at the repository root (the shared agent brief, [source-register.md](source-register.md) SR-28, SR-29); the Herdr rule and reference under `.claude/` (SR-30); and a lab-administration tooling set, `lab-agent/` with `.mcp.json`, one agent definition, one hook and two plan files (SR-31). The paths of the platform layout of D-05 (`butane/`, `compose.yaml`, `Caddyfile`, `firewall/`, `scripts/`, `tests/`, `docs/evidence/`) still do not exist, so nothing in the platform is built or tested. The tooling set is recorded by no decision, and no authorization for it is recorded in this package (`AGENTS.md` "Safety": present but not authorized); what it reports about itself is not evidence here. The rows on the Proxmox token and on the workstation tools were **not re-observed** on 2026-11-16.

*Note of 2026-11-16 (D-49).* This corrects the DOC-1 note above, which says that the tooling set is recorded by no decision. The tooling set named there (`lab-agent/`, `.mcp.json`, one agent definition, one hook and two plan files, [source-register.md](source-register.md) SR-31) is **excluded from the initial publication** by owner decision D-49 ([decision-log.md](decision-log.md) r7). The six paths are listed in `.gitignore` and stay on disk as local, untracked files, so they are not part of the repository. `AGENTS.md` no longer names them: its "Safety" section says that lab-access tooling is excluded from the initial publication and is not authorized. **No authorization for the tooling is recorded, and the exclusion records none**: D-49 decides the scope of the initial publication only, opens neither gate and accepts no result of the workstream. A later inclusion needs a separate owner decision and a separate pull request.

*Note of 2026-11-16 (D-50 … D-53).* The table above and the two notes are kept as written. Since then the owner answered items 2 to 6 of the steward's plan § 21.8 ([decision-log.md](decision-log.md) r8). The 28 command and agent files under `.claude/` are kept, `docs/.prepare/` is included in the initial publication, and OQ-35 is not a prerequisite for the initial publication; the 95-path candidate set is the starting point, subject to the final manifest (D-50). The author identity is the repo-local one as it is, and its values are written nowhere (D-52). No licence file is added now (D-53). **None of this is the publication go-ahead, which the owner has not given, and none of it opens either gate:** no commit, branch, remote, tag or GitHub object exists, [decision-log.md](decision-log.md) § 5 still records no approval, and nothing is built or tested.

*Note of 2026-11-16 (D-54 … D-56).* This corrects the sentences above that say no commit, remote, tag or GitHub object exists: the table of 2026-11-14 and the three notes before this one are kept as written and describe the states of their dates. Later on 2026-11-16 the initial publication was made, once, under the owner's go-ahead for the frozen candidate set, recorded as D-54 ([decision-log.md](decision-log.md) r9); that go-ahead is used up. Facts the decision log states: the repository is public; `main` carries one commit, the bootstrap commit; issues #1 … #34, six milestones and the Projects board exist; no tag exists; no pull request had been opened before the one that carries these records. The owner-only private-value scan was waived for the initial publication and is **not run**; it is not a pass (D-56). **The implementation gate is closed.** [decision-log.md](decision-log.md) § 5 carries two dated narrow approvals of one read-only API connectivity check each; they are not the approval of the implementation gate, they are used up, and the check they allowed is not evidence for any requirement. The platform layout of D-05 still does not exist, and nothing is built or tested. The lab-administration tooling set stays excluded and local (D-49).

## 6. Confirmed constraints

| Constraint | Class | Source |
|---|---|---|
| Docker Compose on one VM; no cluster | reviewer decision | D-01 |
| Docker CE, not the Moby engine FCOS ships | reviewer decision | D-02 |
| Host firewall layer mandatory; Proxmox firewall and Docker-network isolation are welcome extras | reviewer decision | D-03 |
| Public repository; every tracked file, issue, PR and board item is public | owner requirement | D-06 |
| Lab names are `app.corelab.test`, `logs.corelab.test`, `/var/lib/corelab`; the planning workspace's former working name appears nowhere | owner requirement | D-07 |
| Repo-local git identity; never written into a tracked file or a GitHub object. *Note of 2026-11-16 (D-52): the owner approved the repo-local name and address appearing in public commit metadata as they are, once published; the values still appear in no file, issue, pull-request text or board text, and no no-reply address is required* | owner requirement | D-08, D-52 |
| Nothing is published before the publication gate; nothing is built before the implementation gate. *Note of 2026-11-16 (D-54): the one go-ahead that was given covered the initial publication only and is used up; every later publication step still needs the owner* | owner requirement | D-09, D-54 |
| Secrets, rendered Ignition, handoffs and local settings stay out of git | rule | SR-07 |
| SELinux enforcing, TLS verification on, firewall on — never disabled to make something pass | rule | SR-03 "Hard No", SR-07 |
| Only Caddy publishes a port; the database, SMTP, Loki, Grafana and the Docker API are never published | rule | SR-03 principle 6, SR-07 |
| Hungarian for `README.md`, `docs/architecture.md`, `docs/alternatives/`; English for `docs/.prepare/`, `.claude/`, `.agents/`, commits and identifiers. The repository is to be bilingual where that is needed; which files need both languages is not decided (OQ-35), and until it is every file stays in the language it is written in today and nothing is translated | owner requirement | D-12, qualified by D-46 |
| No deadline or time budget has been stated | fact about the sources; open question | OQ-01 |

## 7. Architectural boundaries

- **One VM** (`app-01`) built from Butane; Ignition runs once and is not a configuration manager (SR-01 § 3).
- **Seven services**: Caddy, WordPress, MariaDB, Postfix, Alloy, Loki, Grafana (SR-01 § 4).
- **Five Docker networks**: `web`, `database`, `mail`, `logs`, `grafana-proxy` (SR-01 § 6).
- **External dependencies**: the client, an authenticated SMTP relay, Checkmk, a backup target, the Proxmox host (SR-01 § 1, § 9). None of them is confirmed to exist in the needed form — OQ-02, OQ-03, OQ-04, OQ-05.
- **Three firewall layers**: Proxmox (extra), host with `DOCKER-USER` (mandatory), Docker networks (extra) (SR-01 § 6).
- **Single points of failure**: the VM, its storage, the Proxmox host. This is not a high-availability system (SR-01 § 9).

## 8. Terminology

| Term | Meaning |
|---|---|
| the lab | The owner's private Proxmox environment where the VM will run. Its address and host name are lab-private and are not written in tracked files |
| the planning workspace | The read-only directory the architecture and diagrams were migrated from |
| reviewer / intermediary / owner | See § 3. The Hungarian documents say "kolléga" for the reviewer |
| AC-01 … AC-10 | The rows of the acceptance table in architecture § 10, numbered in table order by SR-08. The numbering was a proposal (D-21); *note of 2026-11-16: the owner approved the identifiers in that order, and the acceptance table itself is unchanged* |
| MUST HAVE / EXTRA / OPTIONAL | The tiers of the scope lock in SR-03 |
| static gates | Checks that need no VM: Butane, Compose, Caddyfile, shellcheck (SR-08) |
| acceptance check / negative test / evidence | SR-08 "What tests mean here" |
| spike | A throwaway first VM that answers open technical questions before anything depends on them |
| scaffold | The first change that creates the platform file layout and fixes the static gate commands |
| publication gate / implementation gate | D-09 |
| baseline | A labelled set of document revisions, see [README.md](README.md) |

## 9. Sources of truth

| Subject | Source of truth | Note |
|---|---|---|
| Scope, requirements, acceptance conditions | `docs/architecture.md` plus the reviewer's answers | SR-03 says the architecture wins over the rules on conflict |
| Policy: commits, branches, versions, security, tests, output | `.claude/rules/` | Not edited by this package; changes are proposed in the readiness report |
| Steward behaviour | `.claude/agents/github-steward.md` | Revised this session, D-26 |
| Shared agent brief | `AGENTS.md`, and `CLAUDE.md` for Claude Code | Points to the governing documents instead of repeating them; where it and they disagree, the documents win (its own header). Added on 2026-11-16 outside this package |
| Preparation decisions, questions, plan | this directory | **Proposals until the owner approves them.** *Note of 2026-11-16 (r8): a row is a decision only where [decision-log.md](decision-log.md) marks it `decided`; D-50 … D-53 and the approved proposals of § 10 are such rows* |
| GitHub objects | none yet. *Note of 2026-11-16 (D-54): the issues #1 … #34, six milestones and the Projects board exist since the initial publication* | After the publication gate, the issue tree becomes the work record |

Known tensions, recorded rather than resolved:

- Several rules already state as policy what the handoffs mark as unconfirmed proposals: the commit scope list, the AC numbering, the release gate, the Docker CE install additions, the Zincati policy ([plan-review.md](plan-review.md) F-15). *Note of 2026-11-16 (decision-log r8): the owner approved the scope list (D-20), the AC numbering (D-21) and the release gate (D-22); the Docker CE install additions (D-24) and the Zincati policy (D-25) are still proposals.*
- The scope lock calls the Compose secrets mechanism OPTIONAL; the security rule requires it (F-23, OQ-26).
- The scope lock makes Docker-network isolation EXTRA; AC-07, a MUST HAVE check, tests from an unauthorised container (F-21, OQ-27).
- The firewall rule line allows TCP 443 from the client network; the monitoring check comes from the Checkmk source (OQ-28).
- The monitoring requirement row names an agent; AC-08 can pass without one (OQ-30).

## 10. Decisions and their status

Full records are in [decision-log.md](decision-log.md). Summary:

- **Decided by the reviewer:** D-01, D-02, D-03.
- **Decided by the owner:** D-04 … D-13 and D-44 … D-56. D-47 is a relayed answer recorded after the fact; D-48 settles the order of future work for one sub-issue and approves nothing else; D-49 decides the scope of the initial publication only (the lab-administration tooling is excluded from it) and opens neither gate. D-50 … D-53 record the owner's answers of 2026-11-16 to items 2 to 6 of the steward's plan § 21.8: D-50 the contents of the bootstrap commit (the 28 command and agent files kept, `docs/.prepare/` included in the initial publication, OQ-35 not a prerequisite, the 95-path candidate set as the starting point); D-51 four points of the proposed issue tree (points 1, 2, 3 and 7 of the plan's § 15), for the issue tree only; D-52 the commit identity (the repo-local name and address as they are, the values written nowhere); D-53 the licence (deferred; no project `LICENSE` now, OQ-22 stays open). Each is a decision about preparation or about the publication's content; **none opens a gate, none is the publication go-ahead, and § 5 of the log is unchanged.** *Note of 2026-11-16 (r7): that sentence describes decision-log r8. D-54 … D-56, recorded in r9, are three further owner statements of the same day, each recorded after the fact at the owner's request:* **D-54** *is the go-ahead for the initial publication of the frozen 95-file candidate set, given once and used up, with the limitations the owner accepted; it is a record of what was allowed and done, not a standing authority, and the implementation gate is not touched.* **D-55** *keeps both added dependency edges of point 14 (S5.3 on S2.3, S4.2 on S4.1), for the issue tree only.* **D-56** *waives the owner-only private-value scan for the initial publication: its state is NOT RUN, it is not a pass and has no result, and no document may call the published set scan-clean or verified. Since r9, § 5 of the log carries two dated narrow approvals of one read-only API connectivity check; they are not the approval of the implementation gate and are used up.*
- **Proposals the owner approved on 2026-11-16** (decision-log r8, § 2): D-20 (the 15 commit scopes), D-21 (AC-01 … AC-10 in the row order of architecture § 10), D-22 (AC-01 … AC-09 gate v0.1.0), D-23 (the umbrella → epic → sub-issue hierarchy and the Projects board, without time-budget arithmetic), D-28 (one direct push of the bootstrap commit under the bootstrap issue, then pull requests; the owner stated that approving the procedure is not yet permission to create a commit or to push; *note of 2026-11-16 (r7): the go-ahead was given later that day and the one push was made, so the exception is used up, D-54*) and D-33 **for the GitHub work tree only**, subject to the exception of D-48. *Note of 2026-11-16 (r7): D-33 now includes the two edges of point 14 (D-55).* Their rows stay in § 3 of the log with the new status.
- **Not decided:** point 14 of the steward's plan § 15 (the two added dependency edges, S5.3 on S2.3 and S4.2 on S4.1; *note of 2026-11-16 (r7): decided later that day, both edges are kept, D-55*) and point 4 (still undecided); the identity that squash merges made on GitHub carry (not decided by D-52; [github-project-plan.md](github-project-plan.md) § 15, point 6); D-35; the technical substance of D-41 and D-42 (D-51 approves only that they do not prevent the platform sub-issues from being prepared).
- **Superseded:** D-30, by D-45.
- **Proposed, awaiting the owner:** D-24 … D-27, D-29, D-31, D-32 and D-34 … D-43; D-30 is superseded, and D-20 … D-23, D-28 and D-33 are approved as above. D-26 and D-29 are proposals whose work is already done. None of these may be treated as settled.

## 11. Assumptions

Each is a working assumption, not a fact. A session that depends on one says so.

| ID | Assumption | What would verify it |
|---|---|---|
| A-01 | The Proxmox host has capacity for one VM of the size the stack needs | OQ-02: a read-only query with an auditor token |
| A-02 | Docker on the chosen FCOS release uses the iptables firewall backend, so the `DOCKER-USER` chain exists | the spike: `docker info`, `iptables -S DOCKER-USER` |
| A-03 | The package set named in the FCOS Docker CE procedure matches the FCOS release that will be used | the spike: `rpm -qa` before the override, `rpm-ostree status` after |
| A-04 | FCOS ships without Python, so the Checkmk Docker plugin cannot run on the host as is | the spike: `command -v python3` |
| A-05 | An external SMTP relay with authentication on TCP 587 and a test mailbox will be available | OQ-04: the owner's answer |
| A-06 | A Checkmk instance outside the VM will be available and the owner can change its trust store and its checks | OQ-03: the owner's answer |
| A-07 | The lab network can provide a source for each test role: client, admin, Checkmk, and a forbidden source that can still reach the VM (widened in r2; a second, routed forbidden source is optional) | OQ-06: the owner's addressing plan |
| A-08 | The owner can run root commands on the Proxmox host, which the FCOS provisioning procedure requires | OQ-05: the owner's answer |
| A-09 | Containers are SELinux-confined under Docker CE, or can be made so with a daemon setting | spike SP-11 |
| A-10 | Docker keeps a `DOCKER-USER` chain that was created and filled before it started | spike SP-07 |
| A-11 | A container attached only to internal networks cannot publish a port | spike SP-12 |
| A-12 | A file-backed Compose secret takes the host file's ownership and needs a label a confined container may read | spike SP-14 |
| A-13 | Each service image accepts credentials from files and offers a health signal | each image's documentation, when it is pinned |
| A-14 | The pinned Butane release can embed local files, and a systemd start condition skips a unit rather than failing it | the static gate at the scaffold; the spike |

## 12. Major open questions

The ones that block planning or building; the full list is in [open-questions.md](open-questions.md).

- OQ-01 deadline or time budget
- OQ-02 Proxmox capacity and version
- OQ-03 Checkmk instance
- OQ-04 SMTP relay and test mailbox
- OQ-05 Proxmox privileges for creating the VM
- OQ-06 lab addressing plan and name resolution
- OQ-07 confirmation of the proposals D-20 … D-43 (D-30 is superseded and needs none). *Note of 2026-11-16: D-20 … D-23 and D-28 are decided, and D-33 for the GitHub work tree; D-24 … D-27, D-29, D-31, D-32 and D-34 … D-43 still need an answer*
- OQ-26, OQ-27 where two tier lines run (secrets; network isolation)
- OQ-29, OQ-30 what the release gate needs (which VM; the monitoring agent)

## 13. Readiness principles

1. **Planned is not done.** No document, issue or report describes a requirement as built, tested or passed without committed evidence (SR-03 principle 1, SR-08).
2. **A proposal is not a decision.** Only a recorded owner decision changes a status to decided or a document to approved.
3. **Uncertainty stays visible.** An unverified claim is marked unverified and names what would verify it.
4. **The fixed tables stay fixed.** Findings may recommend how to prove a row; they never rewrite the requirements table or the acceptance table.
5. **Security tests are not weakened.** AC-05 and AC-07 define the security boundary (SR-08 "Load-bearing tests").
6. **Smallest sufficient set.** No document, service, check or issue is added to look thorough.
