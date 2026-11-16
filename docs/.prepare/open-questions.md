# Open Questions — CoreOS Platform Lab

| Field | Value |
|---|---|
| Document ID | PREP-04 |
| Title | Open Questions |
| Revision | r6 |
| Status | ready-for-human-review |
| Owner | Orchestrator session (author); approver: repository owner |
| Last updated | 2026-11-16 |
| Core-context revision used | r6 |
| Dependencies | [source-register.md](source-register.md) r6, [decision-log.md](decision-log.md) r8 |
| Change summary | r1: first baseline. Carries forward every unresolved question from both handoffs (SR-13, SR-14) and adds the ones found in this session. r2: OQ-06 and OQ-07 widened; OQ-26 … OQ-34 added from the two drafts and the critic's review; the spike questions now point to the merged list SP-01 … SP-20. r3: OQ-17 and OQ-23 answered by the owner and moved to § 2 as CQ-08 and CQ-07. r4 (2026-11-16, records reconciliation): OQ-07 names which IDs of its range no longer need an answer; the dependency revisions are brought up to date. No question was added, answered or closed. r5 (2026-11-16): OQ-35 added at the owner's request, for the part of D-46 that is not decided. No question was answered or closed. r6 (2026-11-16, decisions D-50 … D-53, task DOC-P): OQ-21 answered by D-52 and moved to § 2 as CQ-09; dated notes on OQ-07 (D-20 … D-23 and D-28 decided, D-33 for the GitHub work tree), OQ-22 (deferred by D-53; it stays open) and OQ-35 (not a prerequisite for the initial publication, D-50); the dependency revisions follow decision-log r8. No other question was answered or closed, and no gate opened. Status `in-review` while the independent review of this pass ran; corrected on 2026-11-16 on findings of the independent review of this pass; the status was set after that review ([readiness-report.md](readiness-report.md) § 10f) |

"Blocks" says what cannot proceed without the answer: **publication** (the publication gate), **approval** (the implementation gate), a milestone, an acceptance check, or **no**.

"Needs" says who or what can close it: the **owner**, the **spike** (a first throwaway VM), a named **evidence** source, or a **design** decision in a delegated draft that the owner then confirms.

Abbreviations for affected documents: **arch** = [docs/architecture.md](../architecture.md), **impl** = [implementation-plan.md](implementation-plan.md), **gh** = [github-project-plan.md](github-project-plan.md), **review** = [plan-review.md](plan-review.md), **rules** = `.claude/rules/`.

## 1. Open

### Owner answers needed

| ID | Question | Why it matters | Affects | Blocks | Needs | Origin | Status |
|---|---|---|---|---|---|---|---|
| OQ-01 | Is there a deadline or a time budget? | Without one, effort estimates are relative sizes only and no schedule can be drawn. None has been stated; none is invented here | impl, gh | no | owner | this session (SR-16 § 0) | open |
| OQ-02 | Does the Proxmox host have capacity for the VM, and which Proxmox version runs? What size should the VM be? | Architecture § 3 leaves CPU, RAM and disk open. Seven services on one VM need a size; AC-01 needs room for a second VM or the destruction of the first | arch § 3, impl | M1, AC-01 | owner creates a read-only auditor token (steps in SR-14 "Next Steps"); then a read-only query. The token is never printed | SR-14, SR-13 | open |
| OQ-03 | Is there an existing Checkmk instance outside the VM, or should a test instance be set up? Can its trust store and checks be changed? | AC-08 cannot be run without it. This repository integrates with Checkmk and does not operate it (SR-03) | arch § 7, impl | AC-08, M3 | owner | SR-14, SR-13 | open |
| OQ-04 | Is there a real authenticated SMTP relay on TCP 587 and a test mailbox to receive mail? | AC-04 needs a message that arrives. With only an in-lab test receiver, the architecture says the proof covers in-lab delivery only (arch § 7) | arch § 7, impl | AC-04, M2 | owner | SR-14, SR-13 | open |
| OQ-05 | With which Proxmox privileges is the VM created? | The upstream procedure runs as root on the Proxmox host: snippet storage, image import, Ignition through a cloud-init vendor snippet (SR-22 L7, L22–31, L94–124). The lab-access rule allows a read-only auditor token unless the owner agrees to more (SR-07 "Lab access") | arch § 3, impl, rules | M1, AC-01 | owner | this session | open |
| OQ-06 | What is the lab addressing plan? The VM's address (static or reserved); a source for **each test role** — the client network, the admin source, the Checkmk source, a forbidden source that can still reach the VM, and if the lab has one a second forbidden source on a routed network; **the machine the client-role tests run from** (the admin source is refused on TCP 443 unless it lies in the client network); and how `app.corelab.test` and `logs.corelab.test` resolve (DNS or hosts entries) | Every firewall rule and every negative test needs a concrete allowed and forbidden source; a forbidden source that cannot reach the VM proves a missing route, not a rule (S2 § 3.5). Architecture § 10 step 1 lists DNS as something to clarify | arch § 5, § 6, impl | AC-02, AC-07, M1 | owner. Real addresses stay out of tracked files; tests read them from variables | this session; SR-01 § 10 | open |
| OQ-07 | Does the owner confirm, amend or reject the proposals D-20 … D-43? D-30 is superseded by D-45 and needs no answer; D-26 and D-29 are proposals whose work is already done | The handoffs mark the scope list, the AC numbering, the release gate, the dropped budget arithmetic, the Docker CE additions, the Zincati policy and the firewall order as unconfirmed. Several are already written into the rules. *Note of 2026-11-16 (decision-log r8): D-20, D-21, D-22, D-23 and D-28 are decided, and D-33 for the GitHub work tree, subject to D-48 ([decision-log.md](decision-log.md) § 2); these approvals are not the publication go-ahead and open no gate. Still needing an answer: D-24 … D-27, D-29, D-31, D-32 and D-34 … D-43. D-35 is not decided, because the owner named each proposal instead; D-41 and D-42 are not approved in substance by D-51* | [decision-log.md](decision-log.md) § 3, rules | approval | owner | SR-13 "Open Questions" | open |
| OQ-12 | When is the Zincati maintenance window (days and hours)? | D-25 needs concrete values in the Butane file | arch § 2, § 9, impl | no (needed at M1) | owner | SR-14, SR-13 | open |
| OQ-19 | Is the OPTIONAL backup tier delivered, and before or after the release gate? What is the backup target, and what are the RPO and RTO targets? | AC-10 is required only if the tier is delivered (D-22). Architecture § 8 leaves RPO and RTO open and assumes an external, encrypted target | arch § 8, impl, gh | AC-10 only | owner | SR-01 § 8; SR-11 milestones | open |
| OQ-22 | Does the repository get a licence, and which? | A public repository without a licence grants no reuse rights. The reference repository has none. *Note of 2026-11-16 (D-53): the owner deferred the decision (option L2); no licence is in the bootstrap commit and no project `LICENSE` file is added now. Existing third-party licence and attribution obligations are preserved. The question stays open and blocks nothing; a licence added later is an ordinary pull request* | repository root | no | owner | this session (SR-19) | open |
| OQ-24 | How will the reviewer evaluate the work: from the repository alone, or with access to the lab or a live demonstration? | It decides how much the evidence files must carry on their own, and whether screenshots are enough | impl, `docs/evidence/` | no | owner | this session | open |

### Owner answers needed, added in r2

| ID | Question | Why it matters | Affects | Blocks | Needs | Origin | Status |
|---|---|---|---|---|---|---|---|
| OQ-26 | Is the Compose secrets mechanism part of the base build from the first service with a credential, or does it wait for the OPTIONAL tier? | The scope lock calls it OPTIONAL; the security rule requires file-based secrets and forbids inline ones. The web step needs a credential | rules (SR-03, SR-07), impl | D5 | owner. Recommended: base build | S1 C-1; critic K-01; review F-23 | open |
| OQ-27 | Where does the MUST HAVE part of Docker-network separation end and the EXTRA part begin? | AC-07 (MUST HAVE) tests from an unauthorised container; the scope lock makes network isolation EXTRA and forbids building an EXTRA item early. Splitting the networks late forces six checks to be re-run | arch § 6, rules (SR-03), impl § 7 row 4 | D4 | owner. Recommended: networks in final form from the first Compose change; only the isolation claims and egress rules wait | S2 § 4.3; review F-21 | open |
| OQ-28 | May the Checkmk source reach TCP 443? | The firewall rule line allows TCP 443 "from the client network"; the active HTTPS check comes from the Checkmk source | rules (SR-07 "Firewall and network"), arch § 6 L95 | D8, AC-08 | owner: put the Checkmk source in the client network, or amend the rule line | S2 § 3.2 | open |
| OQ-29 | On which VM is the release evidence taken? | The rebuild (AC-01) makes a second VM with a new CA; evidence records the VM build | impl § 3 D9, `docs/evidence/` | the release gate | owner. Recommended: the final acceptance run happens on the rebuilt VM | critic K-04; review F-26 | open |
| OQ-30 | Does the release need the Checkmk agent the requirement row names, or is the active check that satisfies AC-08 enough? | The row says "agent and active checks"; AC-08 asks only for an alert on a stopped service. The disk alert the log rule requires also needs an agent | arch § 2 L31, § 7 L111; impl § 7 row 6 | the release gate | owner | S1 C-3; critic K-06; review F-07, F-25 | open |
| OQ-31 | If no external relay exists, does a delivery inside the lab count as AC-04 passed? | The architecture says a test receiver proves in-lab delivery only | arch § 7 L107; impl § 5 | AC-04 | owner | S2 § 8.4 | open |
| OQ-32 | In AC-08, does "alert" mean the critical state in Checkmk or a delivered notification? | It decides what the evidence must show | impl § 5 | AC-08 | owner. Proposed: the state and its entry in the event history | S2 § 10.8 | open |
| OQ-33 | Is a WordPress without outward access acceptable? | With the networks as proposed, WordPress cannot fetch updates or plugins at run time; everything comes from the pinned image and tracked files | arch § 4 L56, § 6; impl | no | owner | S2 § 5 | open |
| OQ-34 | Where do per-service configuration files live, and which commit scope covers `scripts/validate.sh`? | The confirmed layout (D-05) has no place for the Postfix, Alloy, Loki, Grafana and WordPress files; the scope table has no row for a general script | D-05, rules (SR-04) | D2 | owner | S1-Q1; critic K-08 | open |

### Owner answers needed, added in r5

| ID | Question | Why it matters | Affects | Blocks | Needs | Origin | Status |
|---|---|---|---|---|---|---|---|
| OQ-35 | Which files need both an English and a Hungarian version, and in what form: one file that carries both languages, a separate file per language, or a summary in the other language? | D-46 makes the repository bilingual where that is needed and leaves the files open. Until the owner answers, every file stays in the language it is written in today and nothing is translated, renamed or created for this. No file has been chosen and no form is preferred here | [decision-log.md](decision-log.md) D-12 and D-46; rules (SR-03 "Language"); whichever files the answer names | no for the initial publication: the answer is not a prerequisite for it (D-50, 2026-11-16). It stays open | owner. D-46 expects a file-by-file proposal for the owner to answer; none has been drafted | D-46 (owner, 2026-11-14); recorded as a question on 2026-11-16 | open |

### Answers the spike must produce

The merged spike list is SP-01 … SP-20 in [implementation-plan.md](implementation-plan.md) § 4.

| ID | Question | Why it matters | Affects | Blocks | Needs | Origin | Status |
|---|---|---|---|---|---|---|---|
| OQ-08 | Does FCOS ship without Python, and how does the Checkmk agent run on an image-based host? Plan B: a containerised agent or local checks | The Checkmk Docker plugin is said to need Python. **Unverified against the source** (SR-26 not retrieved) | arch § 7, impl | AC-08 | spike: `command -v python3`; evidence: the Checkmk documentation | SR-14, SR-13 | open |
| OQ-09 | How are container logs collected? Proposal: Docker's `journald` log driver and Alloy's journal source, which avoids mounting the Docker socket | Either route needs a host mount into a container under enforcing SELinux; the label consequence is unknown. A label exception needs a recorded justification (SR-07) | arch § 4, § 6, impl | AC-06 | spike, then a design decision | SR-14, SR-13 | open |
| OQ-13 | Does `rpm-ostree … --install docker-ce` also bring in `docker-compose-plugin` and `docker-buildx-plugin`? | D-24 installs the Compose plugin explicitly because this is unknown | arch § 2, impl | no | spike: `rpm -q` after the install | SR-14, SR-13 | open |
| OQ-15 | Is IPv6 active on the VM and in Docker? | Architecture § 6 requires equivalent IPv6 rules or a documented statement that IPv6 is not in use | arch § 6, impl | AC-07 | spike, then a design decision | SR-01 § 6 | open |
| OQ-18 | Do the static gate commands in the test rule work as written? | `butane`, `caddy` and `shellcheck` are not installed on the workstation; none of the commands has been run | rules (SR-08 "Gates"), impl | no (needed at scaffold) | the scaffold step: run each from a pinned container | SR-13 | open |

### Design decisions to be drafted, then confirmed

| ID | Question | Why it matters | Affects | Blocks | Needs | Origin | Status |
|---|---|---|---|---|---|---|---|
| OQ-10 | How does WordPress send mail, and how narrow is Postfix's trusted network? | The official WordPress image is said to have no working `mail()`, so an SMTP plugin or a small must-use plugin is needed (unverified here). Postfix needs a fixed address or subnet for the allowed client | arch § 4, § 7, impl | AC-04, AC-05 | design (security-writer and platform-writer drafts) | SR-14, SR-13 | open |
| OQ-11 | Which Postfix image? | There is no official one. The choice decides pinning, configuration, where logs go (arch § 4 says this must not be assumed) and how the relay credentials are read | arch § 4, impl | AC-04, AC-06 | design, checked with `upstream-claim-verify` | this session | open |
| OQ-14 | Which FCOS stream and version is pinned, and is the Docker CE version pinned or "latest at build time"? | The versioning rule says components are pinned in configuration (SR-06). An unpinned install makes two rebuilds differ | arch § 3, impl | AC-01 | design | this session | open |
| OQ-16 | By which protected channel do secrets reach the VM? | Architecture § 3 says "protected transfer" without naming it. Ignition must not carry secrets (SR-07) | arch § 3, § 8, impl | M2 | design | SR-01 § 3 | open |
| OQ-20 | What Loki retention and what disk alert threshold? | Architecture § 7 ties both to capacity | arch § 7, impl | no | design, after OQ-02 | SR-01 § 7 | open |

### Evidence gaps

| ID | Question | Why it matters | Affects | Blocks | Needs | Origin | Status |
|---|---|---|---|---|---|---|---|
| OQ-25 | What does the Checkmk documentation actually require of the agent and the Docker plugin? | The one retrieval attempt failed (SR-26). Every Checkmk statement in this package is unverified against the source | review F-07, impl | no | evidence: read the page linked in arch § 7, or run `upstream-claim-verify` | this session | open |

## 2. Closed

Kept so that a later session does not reopen them.

| ID | Question | Answer | Closed by | Date |
|---|---|---|---|---|
| CQ-01 | May the planning workspace's working name appear in the public repository? | No. Replaced everywhere — D-07 | owner | 2026-11-14 |
| CQ-02 | Public or private repository? | Public — D-06 | owner | 2026-11-14 |
| CQ-03 | Are the migration defaults right (diagrams 01–04 and 07–09 with generators, 05 and 06 left out, the Swarm document under `docs/alternatives/`)? | Yes; the owner's mission specified exactly this set — D-04 | owner | 2026-11-14 |
| CQ-04 | What happens to the Swarm diagrams in the final repository? | 02, 04 and 08 are kept as background of the rejected alternative; 06 is left behind — D-04 | owner | 2026-11-14 |
| CQ-05 | Has the final render of diagram 09 been viewed since the log arrow was added? | Yes. It renders correctly: three nested layers, four sources on the left, the log arrow from Caddy to "Loki + Grafana", the relay on the right. Nothing overlaps or is cut off | orchestrator, by viewing the PNG | 2026-11-14 |
| CQ-06 | Repository hygiene: the rules and `.github/` described a different project | The rules were rewritten for this project on 2026-11-14 (SR-13); the other project's `.github/` was not copied — D-04 | agent session; owner | 2026-11-14 |
| CQ-07 | OQ-23: diagrams 01–04 carried text from before the scope decisions. Regenerate, publish with a note, or hold back? | Regenerated before publication from the corrected generators and re-rendered at the original pixel sizes. 01 and 03 now say chosen variant, Docker CE and mandatory host firewall; 02 and 04 say rejected alternative; the footers cite the current file names — D-44 | owner | 2026-11-14 |
| CQ-08 | OQ-17: should the `analyzing-ai-repos` skill and the `ai-engineer-doc-architect` prompt be removed, and which third-party skills may be published? | Not removed, but excluded from the repository through `.gitignore`, together with the other generic and third-party skills. Four project skills and `excalidraw-diagram` stay tracked; `excalidraw-diagram` states no origin or licence — D-45 | owner | 2026-11-14 |
| CQ-09 | OQ-21: may the commit author address become public with the first push, or should a no-reply address be used? | Yes: the repo-local name and address appear in public commit metadata as they are (option I1). They are configured for this repository only, never globally, and a GitHub no-reply address is not required. **The values are written in no tracked file, issue, pull-request text or board text.** The account's privacy settings are not changed; if a setting rejects the push, the specific blocker is reported — D-52. Not answered by this: the identity of squash merges made on GitHub (D-52; [github-project-plan.md](github-project-plan.md) § 15, point 6) | owner | 2026-11-16 |
