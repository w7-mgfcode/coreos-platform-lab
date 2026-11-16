# Delegation Manifest — CoreOS Platform Lab

| Field | Value |
|---|---|
| Document ID | PREP-09 |
| Title | Delegation Manifest |
| Revision | r4 |
| Status | ready-for-human-review |
| Owner | Orchestrator session (author); approver: repository owner |
| Last updated | 2026-11-16 |
| Core-context revision used | r1 |
| Dependencies | [README.md](README.md) r1 (`docs-baseline-r1`) |
| Change summary | r1: packets for the four sessions. r2: actual outcomes of G-1, S1, S2 and S3 recorded. r3: outcome of G-2 recorded. r4 (2026-11-16, records reconciliation): one dated note after the outcome table; the packets and the recorded outcomes are unchanged |

## 1. Topology

Four Herdr sessions, each in its own tab of the orchestrator's workspace, with the repository root as working directory (D-10). No other session is created.

| Session | Tab label | Agent name | Role | Runs |
|---|---|---|---|---|
| S1 | `docs-platform` | `platform-writer` | Drafts host provisioning, Docker CE installation, Compose services, persistence, delivery sequencing | in parallel with S2 |
| S2 | `docs-security` | `security-writer` | Drafts firewall layers, network isolation, TLS and CA, secrets, relay protection, verification design for AC-01 … AC-10 | in parallel with S1 |
| S3 | `docs-critic` | `plan-critic` | Independent critic of the findings, the scores and both drafts | after S1 and S2 are complete |
| G | `github-steward` | `github-steward` | Stage 1 prime (read-only), then the project plan; waits at the publication gate | prime alongside S1 and S2; plan after integration |

Isolation is by disjoint write paths, not by worktrees: this phase makes no commit, and a worktree needs one. The orchestrator checks after each session that only the assigned path changed.

## 2. Rules common to every packet

1. **Start from `docs-baseline-r1`.** Read, in this order: [README.md](README.md), [core-context.md](core-context.md), [source-register.md](source-register.md), [decision-log.md](decision-log.md), [open-questions.md](open-questions.md). Then the sources your packet names.
2. **Write only your assigned output file.** Do not edit any other file. Propose changes to the core documents in your completion report.
3. **Class every material statement**: fact (with a reference), owner requirement, reviewer decision, proposal, assumption, open question, or conflict. An unverified claim says so and names what would verify it.
4. **References.** Repository files by relative path and section or line range; register entries by ID (`SR-01 § 6`); decisions and questions by ID (`D-24`, `OQ-09`); findings and recommendations by ID (`F-03`, `R-03`).
5. **Do not invent**: no requirement, measurement, version number, address, approval or test result that a source does not give. Nothing is built or tested; never write that something works.
6. **The fixed tables stay fixed**: the reviewer's three answers, the requirements table (architecture § 2) and the acceptance table (architecture § 10).
7. **Public file hygiene**: English; repository-relative paths; no real names, mail addresses, host names or lab addresses. Example addresses come from the documentation ranges `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`. The planning workspace's former working name must not appear.
8. **No implementation.** Do not create anything under `butane/`, `firewall/`, `scripts/`, `tests/`, and no `compose.yaml` or `Caddyfile`. Inside your document, a fragment of a few lines may illustrate a point if it is labelled "illustrative, untested". No complete configuration file.
9. **No git or GitHub writes, no contact with the lab.** No commit, branch, remote, push, issue, label, milestone or board.
10. **Tools.** Reading files is enough for S1, S2 and S3; shell commands are not needed. If a permission or question dialog appears, stop and wait: the orchestrator reads it and asks the owner.
11. **Metadata block** at the top of your file: document ID, title, revision, status (`draft`), owner (your agent name), last updated, core-context revision used, dependencies, change summary.
12. **Completion report** as the last section of your file and as your final message: session name; baseline revision; files created or changed; evidence consulted; decisions proposed; assumptions introduced; open questions; validation performed; limitations; completion or blocker status.

## 3. Packets

### S1 — platform-writer

| Field | Content |
|---|---|
| Task ID | S1 |
| Role and objective | Platform engineer. Turn the architecture's host and service sections into a build-ready design and a delivery sequence, so that the implementation plan can be integrated from it |
| Core-context revision | r1 (`docs-baseline-r1`) |
| Source documents | [docs/architecture.md](../architecture.md) § 2, 3, 4, 7, 8, 9, 10; [plan-review.md](plan-review.md) r1 findings F-01, F-02, F-08, F-09, F-11, F-12, F-13, F-14, F-17, F-19 and their recommendations; `.claude/rules/product-vision.md`, `security-patterns.md`, `test-requirements.md`, `versioning.md`, `commit-format.md`; register entries SR-20 and SR-22 for upstream facts |
| Scope | (a) VM creation on Proxmox and Ignition delivery; (b) Butane structure: what it contains, what it must not; (c) Docker CE first-boot installation, version pinning, ordering against the Compose start; (d) the seven services: image selection criteria, configuration source, persistent data, health and start order; (e) log collection mechanism and the mail integration on the WordPress side; (f) Checkmk agent installation options on an image-based host; (g) delivery sequence: spike questions with the exact command that answers each, scaffold, service order, per-step files, exit condition and the acceptance checks each step feeds; (h) OPTIONAL tier in outline: backup, restore, update |
| Exclusions | Firewall rules, network isolation, TLS trust, secrets handling, relay protection and the design of the acceptance and negative tests belong to S2: name the dependency and stop there. No GitHub objects. No time estimates in hours or days (OQ-01) |
| Output path | `docs/.prepare/delegation/s1-platform-delivery.md` |
| Allowed write paths | that file only |
| Required structure | 1 Scope and inputs · 2 Host provisioning · 3 Docker CE installation · 4 Services and persistence (one table row per service) · 5 Boot-time start and ordering · 6 Log collection, mail integration, monitoring agent · 7 Delivery sequence (spike → scaffold → steps) · 8 OPTIONAL tier outline · 9 Proposed changes to the core documents · 10 Completion report |
| Required evidence references | Every upstream-behaviour statement cites a register entry with lines, or is marked unverified with the spike command or document that would verify it. Every design choice names the requirement row or rule it serves |
| Acceptance criteria | Each assigned finding is answered or explicitly left open with a reason. Each of the ten requirement rows in architecture § 2 appears in the delivery sequence. Every spike question has one command and one decision that depends on it. No statement claims something is built or tested. Under roughly 400 lines |
| Dependencies | `docs-baseline-r1`; plan-review r1. Runs in parallel with S2 and cannot read its draft |
| Questions to escalate | Anything that needs the owner (OQ-02 … OQ-06) is listed, not answered. A conflict between the architecture and a rule is reported, not resolved |
| Definition of done | The file exists with the required structure, the metadata block and the completion report; the acceptance criteria hold |

### S2 — security-writer

| Field | Content |
|---|---|
| Task ID | S2 |
| Role and objective | Security and verification engineer. Turn the architecture's network, firewall, TLS, secrets and mail-protection sections into a design that can be tested, and define how each acceptance check is run and proven |
| Core-context revision | r1 (`docs-baseline-r1`) |
| Source documents | [docs/architecture.md](../architecture.md) § 2, 5, 6, 7, 8, 10; [plan-review.md](plan-review.md) r1 findings F-01, F-03, F-04, F-05, F-06, F-07, F-08, F-10, F-12, F-13, F-14, F-18, F-20 and their recommendations; `.claude/rules/security-patterns.md`, `test-requirements.md`, `product-vision.md`; register entries SR-24 and SR-25 for upstream facts |
| Scope | (a) exposure matrix: which source may reach which destination on which port; (b) the mandatory host firewall layer: mechanism, rule intent, matching after address translation, persistence across a Docker restart and a reboot, start ordering, IPv6; (c) the two EXTRA layers; (d) Docker networks: membership, which are internal, egress for the mail relay; (e) internal CA: trust distribution to the client and to Checkmk, the renewal trial; (f) secrets: delivery channel, file ownership and mode, the example file; (g) relay protection: who may relay, how the refusal is produced; (h) SELinux and container privilege constraints, including the log collector's mounts; (i) **verification design for AC-01 … AC-10**: preconditions, how it is run, positive case, negative case, the check that a negative test fails for the right reason, the evidence file it leaves, and what cannot be verified yet |
| Exclusions | Host provisioning, the Docker CE installation, image selection and the delivery order belong to S1: name the dependency and stop there. No GitHub objects. Do not weaken AC-05 or AC-07 and do not rewrite any acceptance row |
| Output path | `docs/.prepare/delegation/s2-security-verification.md` |
| Allowed write paths | that file only |
| Required structure | 1 Scope and inputs · 2 Exposure matrix · 3 Host firewall layer · 4 EXTRA layers · 5 Docker networks and egress · 6 TLS and the internal CA · 7 Secrets · 8 Mail relay protection · 9 SELinux and container privileges · 10 Verification design, one subsection per AC · 11 Proposed changes to the core documents · 12 Completion report |
| Required evidence references | As for S1. Every blocked path in the exposure matrix names its negative test. Every acceptance check names its evidence file under `docs/evidence/` and the script name it would have under `tests/`, following the conventions in `test-requirements.md` |
| Acceptance criteria | Each assigned finding is answered or left open with a reason. All ten acceptance checks have a subsection with every required element. Each negative test states its right-reason precondition. Requirement rows without an acceptance row (F-14) get a named evidence item. Under roughly 450 lines |
| Dependencies | `docs-baseline-r1`; plan-review r1. Runs in parallel with S1 and cannot read its draft |
| Questions to escalate | As for S1. In addition: any place where a rule in `security-patterns.md` cannot be met without an exception is reported with the exact rule line |
| Definition of done | As for S1 |

### S3 — plan-critic

| Field | Content |
|---|---|
| Task ID | S3 |
| Role and objective | Independent critic. Challenge the orchestrator's findings and scores and both drafts. You did not write any of them and you defend none of them |
| Core-context revision | r1 (`docs-baseline-r1`) |
| Source documents | [plan-review.md](plan-review.md) r1; [delegation/s1-platform-delivery.md](delegation/s1-platform-delivery.md); [delegation/s2-security-verification.md](delegation/s2-security-verification.md); [docs/architecture.md](../architecture.md); the rules; the register |
| Scope | (a) each finding: is the evidence reference exact, does the evidence support the severity, is anything missing or overstated; (b) each score: unsupported high scores, the same benefit counted under two criteria or two recommendations, effort bases; (c) overlapping or duplicate recommendations; (d) sequencing errors in the execution order; (e) a sensitivity test: change each weight by ±5 and each disputed score by ±1 and report whether the top five and the blocker list change; (f) the two drafts: contradictions between them, with the architecture, or with a rule; invented facts; gaps against their packets; (g) findings the review missed |
| Exclusions | Do not rewrite the review or the drafts. Do not score your own findings into the ranking; propose, and the orchestrator re-ranks. No GitHub objects |
| Output path | `docs/.prepare/delegation/s3-critic-review.md` |
| Allowed write paths | that file only |
| Required structure | 1 Scope and method · 2 Challenges to findings (by ID: uphold, adjust, reject, with reason) · 3 Challenges to scores (by recommendation and criterion) · 4 Overlaps and double counting · 5 Sequencing check · 6 Sensitivity test with its table · 7 Review of S1 · 8 Review of S2 · 9 Cross-draft contradictions · 10 Missed findings · 11 Proposed re-ranking · 12 Completion report |
| Required evidence references | Every challenge cites the line or section it rests on. A challenge without evidence is labelled an opinion |
| Acceptance criteria | Every finding and every recommendation has a verdict. The sensitivity test states plainly whether the top choices change. Disagreements between S1 and S2 are listed with both positions. If the review confirms the initial order, it says so. Under roughly 350 lines |
| Dependencies | S1 and S2 complete and accepted for review |
| Questions to escalate | Anything that needs the owner |
| Definition of done | As for S1 |

### G-1 — github-steward, Stage 1 prime

| Field | Content |
|---|---|
| Task ID | G-1 |
| Role and objective | Steward. Stage 1a of `.agents/plans/github-bootstrap-mission.md`: read-only prime |
| Core-context revision | r1 (`docs-baseline-r1`) |
| Source documents | your agent definition; the mission; the rules; [docs/architecture.md](../architecture.md) § 2, 6, 10; the five core documents; the GitHub references named in the mission |
| Scope | Read; study the references with read-only `gh` queries; confirm the repository name is free and the token scopes are present |
| Exclusions | **Write nothing**, not even the plan. Nothing on github.com is created or changed |
| Output path | none; report in the session |
| Allowed write paths | none |
| Required structure | The report format of your agent definition |
| Required evidence references | The `gh` command behind each reference observation |
| Acceptance criteria | The report states: token scopes; name availability; what you will mirror from each reference and what you will not; anything in your agent definition or the mission that you find wrong or unclear |
| Dependencies | the agent definition and mission as revised on 2026-11-14 (D-26) |
| Questions to escalate | A missing token scope: report the exact error; do not work around it |
| Definition of done | The report is given and the session is idle |

### G-2 — github-steward, Stage 1 plan and gate

| Field | Content |
|---|---|
| Task ID | G-2 |
| Role and objective | Steward. Stage 1b and 1c of the mission: draft the project plan from the integrated baseline, then present the scan and the tree and wait |
| Core-context revision | the revision named in [README.md](README.md) at the time of the prompt |
| Source documents | [implementation-plan.md](implementation-plan.md); [plan-review.md](plan-review.md); the core documents; [docs/architecture.md](../architecture.md) § 2 and § 10 |
| Scope | Milestones mirroring architecture § 10; one umbrella; the epics; every sub-issue with title in commit grammar, labels, tier, the acceptance checks it proves, dependencies, files in scope and verifiable acceptance criteria; anything waiting on the owner marked blocked with the decision or question ID; repository settings, labels and board fields; the Stage 2 bootstrap sequence |
| Exclusions | Nothing on github.com. No file other than the plan |
| Output path | `docs/.prepare/github-project-plan.md` |
| Allowed write paths | that file only |
| Required structure | As listed in the mission, Stage 1b |
| Required evidence references | Each sub-issue cites the implementation-plan step and the architecture section it comes from |
| Acceptance criteria | Every MUST HAVE requirement row and every acceptance check AC-01 … AC-09 is covered by at least one sub-issue; AC-10 only under the OPTIONAL epic. No sub-issue for an EXCLUDED item. No estimate or due date. Every blocked item names what it waits on |
| Dependencies | integration of S1, S2 and S3 |
| Questions to escalate | The owner decisions listed in the mission under "Owner decisions at the publication gate" |
| Definition of done | The plan is written and reviewed by the orchestrator; the scan and the tree are shown in the steward's tab; the session waits for the owner's go-ahead |

## 4. Outcomes

What each session actually did, taken from its pane, its file and the working tree. No session committed, pushed, branched, added a remote or touched github.com; `git status` showed no commit after each one.

| Session | Tab / pane | Baseline | Files written | Outcome | Reviewed by | Accepted |
|---|---|---|---|---|---|---|
| G, task G-1 | `github-steward` · `w3:t3` / `w3:p3` | `docs-baseline-r1` | none (verified: nothing changed on disk, no remote) | **Complete.** Token has the `repo`, `project` and `workflow` scopes; the repository name is free; the local commit address is not a no-reply address. It listed what it will and will not mirror from each reference and found six points wrong or unclear in its own definition and mission | orchestrator | yes; the six points were applied to the definition and mission (decision-log § 4 rows 19–25) |
| S1 | `docs-platform` · `w3:t4` / `w3:p4` | `docs-baseline-r1` | `delegation/s1-platform-delivery.md` (362 lines) | **Complete.** All ten assigned findings answered or left open with a reason; sixteen proposals; twelve spike questions; three conflicts between sources reported (C-1 … C-3). It did not open the upstream sources and says so | plan-critic; orchestrator | yes, with nine corrections (implementation-plan § 7) |
| S2 | `docs-security` · `w3:t5` / `w3:p5` | `docs-baseline-r1` | `delegation/s2-security-verification.md` (449 lines) | **Complete.** All thirteen assigned findings answered or left open with a reason; an exposure matrix with a named test for every blocked path; all ten acceptance checks designed with a right-reason control; twelve spike questions; two conflicts reported. It did not open the upstream sources and says so | plan-critic; orchestrator | yes, with eight corrections (implementation-plan § 7) |
| S3 | `docs-critic` · `w3:t6` / `w3:p6` | `docs-baseline-r1` | `delegation/s3-critic-review.md` (290 lines) | **Complete.** No finding rejected: 12 upheld, 9 adjusted, 3 severities changed; all 19 score sums confirmed, 12 single scores disputed; a sensitivity test over 10 weight cases and 21 score cases; 12 cross-draft contradictions; 12 missed findings; the first three ranks and the blocker list confirmed, the order below them not. It could not check upstream quotations and says so | orchestrator | yes; every challenge has a recorded response (plan-review § 9.1). One proposal not taken: restoring R-03's B score to 5 |
| G, task G-2 | `github-steward` · `w3:t3` / `w3:p3` | `docs-baseline-r2` | `github-project-plan.md` (r2 after review) | **Complete; waiting at the publication gate.** The plan holds the repository settings, 35 labels, the board fields, six milestones, one umbrella, seven epics and 25 sub-issues mapped to steps D0 … D11, each with files, dependencies and verifiable criteria; what waits on the owner by ID; the Stage 2 sequence; five reported differences from the mission. It then ran its own read-only pre-publication scan (reported in its tab as passed with three warnings), showed the tree and fifteen numbered decisions for the owner, and stopped. Verified afterwards: no commit, no remote, no repository on github.com | orchestrator | yes, with three notes recorded in the plan |

*Note of 2026-11-16; the table above is left as recorded.* After the G-2 outcome the steward revised [github-project-plan.md](github-project-plan.md) twice on 2026-11-14, each time at an owner answer relayed to it: r3 dropped the conditional sub-issues S0.C1 and S0.C2 (D-44, D-45), and r4 split S2.2 into S2.2 and S2.3, which makes 26 sub-issues (D-47). Neither revision was reviewed by the orchestrator: "Reviewed by" and "Accepted" in the G-2 row refer to r1 and its acceptance as r2.

Observations on the delegation itself:

- **Disjoint write paths held.** After each session the only new or changed file was its assigned one.
- **No permission dialog blocked a session.** The sessions ran with the owner's default settings; no flag was passed to any of them beyond `--agent github-steward` for G.
- **Parallel writers could not see each other**, as intended. The cost was twelve contradictions between the drafts, which the critic listed and the integration settled or escalated.
- **Both writers and the critic worked from the register's paraphrases of the upstream sources**, because the retrieved files were outside the repository. The critic named this a single point of trust; the source register now carries the cited lines' content.
- **Packet defect:** packet G-1 named five core documents while the baseline lists six; the steward did not read the methodology adaptation in its prime. It read it for G-2.
- **Tooling defect seen in a pane:** the commit hook is called by a relative path, so a shell outside the repository root reported it missing and the call went through unchecked. Listed as a proposed change in [readiness-report.md](readiness-report.md) § 7.
- **Not designed here:** who writes the clarification pull requests that edit `docs/.prepare/` after publication (the steward's bounds exclude it). The steward put this to the owner.
