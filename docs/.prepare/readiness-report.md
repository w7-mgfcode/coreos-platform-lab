# Readiness Report — CoreOS Platform Lab

| Field | Value |
|---|---|
| Document ID | PREP-10 |
| Title | Readiness Report |
| Revision | r8 |
| Status | ready-for-human-review |
| Owner | Orchestrator session (author); approver: repository owner |
| Last updated | 2026-11-16 |
| Core-context revision used | r2 (`docs-baseline-r2`) for §§ 1–10 and § 11; § 10a was added under `docs-baseline-r3`; § 10b uses r3 (`docs-baseline-r5`; its final pass `docs-baseline-r6`); § 10c uses r3 (`docs-baseline-r7`); § 10d uses r4 (`docs-baseline-r8`); § 10e uses r5 (`docs-baseline-r9`); § 10f uses r6 (`docs-baseline-r10`); § 10g uses r7 (`docs-baseline-r11`) |
| Dependencies | every document in [README.md](README.md) at the revisions listed in § 9 |
| Change summary | r1: first report, written after integration of the four delegated sessions; § 10a was added on 2026-11-14 without a new revision. r2 (2026-11-16): § 10b added, a dated reconciliation entry. r3 (2026-11-16): the final pass of § 10b — OQ-35 recorded, the counts taken again, the review of the last edits. r4 (2026-11-16): § 10c added for the owner's scheduling decision D-48. §§ 1–10, § 10a, § 10b and § 11 are unchanged and keep their dates. r5 (2026-11-16, documentation closeout DOC-1): § 10d added — what supersedes the scan of § 4 and the plan for a root `CLAUDE.md`, the counts taken again, files noticed and not decided, what was not verified. §§ 1–10c and § 11 are unchanged. r5, extended on 2026-11-16 after an independent review (DOC-1b): § 10d states what the earlier scan did not cover, records the orchestrator's preliminary scan as its observation, notes plan r6 as a draft whose review is pending, gives one time for the file count, and states that the owner's instruction was relayed. DOC-1c (2026-11-16): the plan paragraph follows r7. DOC-1d (2026-11-16): the table row placed back inside the counts table, the scan's mail wording aligned with the plan, and the plan paragraph records the confirmation of r7. r6 (2026-11-16, decision D-49, task DOC-C): § 10e added — what the owner decided on the scope of the initial publication and what it does not decide, what it supersedes in § 10d, what the orchestrator session did and observed, the commit-format hook, what is not verified, the records changed; dated notes in § 7 and § 10d point to it. §§ 1–10c and § 11 are unchanged. r6, corrected and its status set on 2026-11-16 after the independent review of the D-49 change: § 10e items 4 and 5 of "Not verified, and still open", the "Elsewhere" bullet, the count reconciliation, and the new sub-section "Review of this change". r7 (2026-11-16, decisions D-50 … D-53, task DOC-P): § 10f added — the owner's answers of 2026-11-16 to items 2 to 6 of the steward's plan § 21.8 and where they are recorded, the files changed by this pass and by whom, what is not changed, what remains open for the publication, and a placeholder for the review state; dated notes in § 1, § 6, § 7, § 10b item 9, § 10d item 4, § 10e "Not verified" item 2 and § 11 point to it. §§ 1–10e and § 11 are otherwise unchanged. Status `in-review` while the independent review of this pass ran; corrected on 2026-11-16 on findings of the independent review of this pass; the status was set after that review (§ 10f); § 10f also names the later edits of the Herdr rule and its reference (task DOC-P4) and of `AGENTS.md` and `CLAUDE.md` (task DOC-P5), same revision. r8 (2026-11-16, decisions D-54 … D-56, task DOC-R1): § 10g added — a records pass after the initial publication: what decision-log r9 records (the publication go-ahead, given once and used up; both added tree edges kept; the owner-only private-value scan waived, not run and never a pass; two dated narrow approvals of one read-only API connectivity check in § 5), from which source, what was not verified, and a marked place for the review of this pass. Dated notes at the sentences of § 1, § 6, § 10b (gate state), § 10e and § 10f that say the go-ahead has not been given or that no commit, remote or tag exists, and in § 11. §§ 1–10f and § 11 are otherwise unchanged. Status `in-review` while the independent review of this pass ran; the status was set after that review (§ 10g) |

## 1. Verdict in one paragraph

The documentation baseline is complete, internally consistent and reviewed by sessions other than its authors. It is **ready for the owner to read and decide on**. It is **not** approval to build: no approval line has been recorded, eleven owner answers are outstanding, and the plan rests on behaviour that only a first VM can confirm. Nothing has been published, committed, built or tested.

*Note of 2026-11-16 (r7, § 10f).* The count of outstanding owner answers is that of r1. Since then the owner decided items 2 to 6 of the steward's plan § 21.8 and approved several proposals ([decision-log.md](decision-log.md) r8); the publication go-ahead (item 7) has not been given, no approval line exists in decision-log § 5, and nothing is committed, published, built or tested. § 10f is the current state.

*Second note of 2026-11-16 (r8, § 10g).* The sentence "Nothing has been published, committed, built or tested" and the first note's "the publication go-ahead (item 7) has not been given … nothing is committed, published" describe the states of r1 and r7. Later on 2026-11-16 the owner's go-ahead for the initial publication was given once and used up, and the initial publication was made (D-54): `main` carries one commit, and issues, milestones and the Projects board exist. Nothing is built or tested, the implementation gate is closed, and the publication is not evidence for any requirement. § 10g is the current state.

## 2. Readiness checks

| # | Check | Result | Rationale |
|---|---|---|---|
| 1 | Intent and scope are clear | **Pass** | Fixed by the reviewer's three answers and the two tables of the architecture (D-01 … D-03; [core-context.md](core-context.md) § 4). Limit: the brief itself is not in the repository, only its summary |
| 2 | Requirements are testable | **Pass**, as designed | Every acceptance check has a run, a positive case, a control that makes a pass meaningful, and an evidence file ([implementation-plan.md](implementation-plan.md) § 5). As written in the architecture, AC-01, AC-05 and AC-07 were not testable; the design makes them so. Three checks can only be *run* with owner inputs: AC-07 (OQ-06), AC-04 (OQ-04), AC-08 (OQ-03) |
| 3 | The architecture is grounded in repository reality | **Unknown** | The repository holds no platform code, so there is no reality to ground it in yet. Tool behaviour was checked against upstream documentation for the Docker CE install, the Proxmox procedure, `DOCKER-USER` and the internal CA ([source-register.md](source-register.md) "What the cited upstream lines say"). Twenty questions about behaviour on the lab are open until the spike (implementation-plan § 4). Checkmk is unverified throughout |
| 4 | Alternatives and trade-offs are documented | **Pass** | The rejected Swarm variant ([docs/alternatives/swarm.md](../alternatives/swarm.md)); three log routes, two firewall-loading designs, four agent routes, two Postfix image routes, each with its cost (drafts S1 and S2; implementation-plan § 7) |
| 5 | Blockers are resolved or awaiting an authorised decision | **Pass** | None is resolved by an agent. Each is listed with the person who can answer it (§ 6) |
| 6 | Recommendations have transparent scores | **Pass** | Five weighted criteria, a one-line justification per score, unknowns shown as intervals, initial and final rank with the reason for every change ([plan-review.md](plan-review.md) § 7, § 9.2) |
| 7 | Agent outputs were reviewed and reconciled | **Pass** | Both drafts were reviewed by the critic and by the orchestrator; the critic's review by the orchestrator; the steward's plan by the orchestrator. Twelve contradictions between the drafts are settled or escalated (implementation-plan § 7). No session was the sole reviewer of its own work |
| 8 | Execution order is clear | **Pass**, conditional | Twelve steps D0 … D11 with an exit each and the checks each may claim (implementation-plan § 3). Conditional on the blockers of its § 2 |
| 9 | Verification criteria exist | **Pass** | Per acceptance check, per requirement row (traceability table, implementation-plan § 6), and per sub-issue ([github-project-plan.md](github-project-plan.md) § 9) |
| 10 | Open questions have owners | **Pass** | Every row of [open-questions.md](open-questions.md) names who or what closes it |
| 11 | The baseline is revisioned and consistent | **Pass** | `docs-baseline-r2`; revisions in § 9. Every relative link and image in `README.md` and `docs/` resolves (§ 5) |
| 12 | The pre-publication scan is clean | **Pass**, with decisions pending | No secret, home path, identity value, forbidden name, lab identifier or oversized file (§ 4). Four publication matters are not scan hits but need the owner: stale diagram footers, third-party tooling, licence, commit address (§ 6) |

## 3. Migration

Source paths are relative to the planning workspace, which was not modified.

| Source | New path | What changed |
|---|---|---|
| `ARCHITECTURE-COMPOSE.md` | [docs/architecture.md](../architecture.md) | Links and image paths; overview figure is now diagram 07 with diagram 01 linked as the detailed view; diagram 09 added to § 6; lab names per D-07. Section numbering, headings, the requirements table and the acceptance table are unchanged (compared line by line) |
| `ARCHITECTURE-SWARM.md` | [docs/alternatives/swarm.md](../alternatives/swarm.md) | Links; lab names; the last paragraph of § 2 and step 1 of § 10 now state the Docker CE decision. The rejected status line is kept |
| `diagrams/01`, `02`, `03`, `04`, `07`, `08`, `09` in `.excalidraw`, `.svg`, `.png` | [diagrams/](../../diagrams/) | Text formats of 01–04: the name replaced per D-07. PNGs of 01–04 re-rendered from the corrected SVGs (D-29). 07, 08, 09 copied unchanged |
| `diagrams/generate.py`, `generate_argue.py` | `diagrams/` | Absolute home paths replaced by environment variables with a fallback under the user's home; name replaced. Both parse |
| `diagrams/generate_arch.py`, `generate_firewall.py` | `diagrams/` | Copied unchanged. Both parse |
| `diagrams/SOURCES.txt` | [diagrams/SOURCES.txt](../../diagrams/SOURCES.txt) | Title; the Moby question resolved; a file list added; the note on stale footers; the environment variables |
| `HANDOFF.md` | `HANDOFF.md` (untracked, ignored) | An update section, new next steps and context for the new layout |
| two memory notes of the planning project | this project's agent memory directory (outside the repository) | Copied unchanged and indexed |

| Left behind | Why |
|---|---|
| Diagrams 05 and 06 and `generate_question.py` | Question diagrams for a clarification that is finished (D-04) |
| The zip archive, `__pycache__/` | A bundle and a cache |
| The planning workspace's `.github/` | It belongs to a different project (D-04) |
| The archived handoff of 2026-11-13 | Contains a third party's first name; read, not copied (SR-14) |

Created new: `README.md` (Hungarian), `.gitignore`, this directory. Revised in place: `.claude/agents/github-steward.md`, `.agents/plans/github-bootstrap-mission.md` ([decision-log.md](decision-log.md) § 4).

**Diagram 09**, whose final version had never been reviewed, was viewed on 2026-11-14 and renders correctly: three nested layers (Proxmox, host with `DOCKER-USER`, Docker networks), four sources on the left with ports 443, 22 and the agent, the denied source ending at the outer layer, the log arrow from Caddy to "Loki + Grafana", and the relay on the right with port 587. Nothing is cut off or overlapping. It was not regenerated.

## 4. Pre-publication scan

Run on 2026-11-14 over the list `git add -A --dry-run` produces, after all documents were written. The steward repeats it before anything is published.

| Check | Result |
|---|---|
| Files that would be tracked | 220 |
| `HANDOFF.md`, `.handoffs/`, `.claude/settings.local.json`, `*.ign`, `secrets/`, caches | none in the list; the first three are reported as ignored by `git check-ignore` |
| Files over 5 MB | none; the largest is a diagram PNG of about 0.4 MB |
| Secret patterns (private keys, GitHub and other tokens, Proxmox token strings) | none |
| Absolute paths under a home directory | none |
| The repo-local git identity (name, address and their parts, compared without printing them) | none |
| The planning workspace's former working name | none |
| Lab-private identifiers (host name, address) and the third party's first name | none |
| Mail addresses | one, a fictional example in a third-party skill's reference text (`.claude/skills/prompt-architect/references/frameworks/tidd-ec.md:172`) |
| Private-range addresses | one fictitious example range in diagram 03 and its generator, labelled as fictitious in the diagram; documentation-range examples in the security draft |
| PNG metadata | no text chunks in any of the seven PNGs |

Not detectable by a scan, found by looking: the footers of diagrams 01–04 (OQ-23).

## 5. Link check

Every relative link and image in `README.md` and under `docs/` was resolved against the working tree, including heading anchors: **no broken link**. Architecture sections 2, 6 and 10 exist under their original headings.

## 6. Remaining blockers and owner decisions

### At the publication gate

Asked for in the `github-steward` tab, together with the scan and the issue tree.

| # | Decision | Reference |
|---|---|---|
| 1 | Go-ahead to create the public repository and push | D-06, D-09 |
| 2 | Agreement to one direct push of the bootstrap commit | D-28 |
| 3 | The commit author address: publish it, or switch to a no-reply address first (the owner changes the identity) | OQ-21 |
| 4 | A licence, or none | OQ-22 |
| 5 | The structural proposals the tree makes public: scope list, AC numbering, release gate, hierarchy without budget fields, work order | D-20, D-21, D-22, D-23, D-33; D-35 |
| 6 | Diagrams 01–04: regenerate with current footers, publish with the note in `SOURCES.txt`, or hold back | OQ-23 |
| 7 | The generic toolkit: remove `analyzing-ai-repos` and the `ai-engineer-doc-architect` prompt? Publish the third-party skills? | OQ-17 |
| 8 | The steward's own open points on the tree | [github-project-plan.md](github-project-plan.md) § 15 |

*Note of 2026-11-16 (r7, § 10f).* Row 1, the go-ahead, has **not** been given. Row 2 (D-28): the owner approved the procedure and stated that this is not yet permission to create a commit or to push. Row 3 (OQ-21): answered by D-52 and closed as CQ-09; the values are written nowhere. Row 4 (OQ-22): deferred by D-53; no licence now, the question stays open. Row 5: D-20, D-21, D-22, D-23 and, for the GitHub work tree and subject to the D-48 exception, D-33 are approved by name; D-35 is not decided because it was not needed. Rows 6 and 7 were settled earlier (D-44, D-45; § 10a). Row 8: points 1, 2, 3 and 7 of the plan's § 15 are decided as the plan proposes (D-51); point 14 (two added dependency edges) and point 4 are **not** decided. The contents of the bootstrap commit are answered by D-50 and D-49. This table is otherwise left as written.

*Second note of 2026-11-16 (r8, § 10g).* Row 1: the go-ahead was given later that day, once, for the frozen 95-file set, and is used up (D-54). Row 2 (D-28): the one direct push of the bootstrap commit was made under that go-ahead; the exception is used up and every later change is a pull request. Row 8: open point 14 was answered, both added edges are kept (D-55); point 4 stays undecided. Every later commit, branch, pull request, tag and GitHub object still needs the owner.

### At the implementation gate

| # | Action | Reference |
|---|---|---|
| 1 | Confirm, amend or reject each proposal D-20 … D-43 | [decision-log.md](decision-log.md) § 3; OQ-07 |
| 2 | Decide the four tier and gate questions | OQ-26, OQ-27, OQ-29, OQ-30 |
| 3 | Write a dated "Approved by owner" line in decision-log § 5, or ask for it to be recorded | D-09 |

*Note of 2026-11-16 (r7, § 10f).* Row 1 is partly answered: D-20 … D-23 and D-28 are decided, and D-33 for the GitHub work tree, subject to D-48; D-24 … D-27, D-29, D-31, D-32 and D-34 … D-43 still need an answer. Row 3 is unchanged: decision-log § 5 reads "(no approval recorded)", and the approvals of 2026-11-16 are publication-preparation decisions that do not touch the implementation gate.

### Before the build can go far

| Input | Stops | Reference |
|---|---|---|
| Proxmox auditor token; capacity, version, VM size | the spike, the host step, the rebuild | OQ-02 |
| Who creates the VM, with which privileges | the spike, the host step | OQ-05 |
| The lab addressing plan with a source per test role | the firewall step, AC-02, AC-07 | OQ-06 |
| An authenticated relay and a test mailbox | the mail step, AC-04 | OQ-04 |
| A Checkmk instance under the owner's control | the monitoring step, AC-08 | OQ-03 |

Smaller owner answers (OQ-01, OQ-12, OQ-19, OQ-24, OQ-28, OQ-31 … OQ-34) are listed in [open-questions.md](open-questions.md); none stops the first steps.

## 7. Proposed rule changes

This package edits no rule and not the hook. Each line below is a proposal for the owner.

| Rule or file | Proposed change | Why |
|---|---|---|
| `.claude/settings.json` | Call the commit hook by a path that does not depend on the shell's working directory | Observed on 2026-11-14 in the steward's pane: with the shell outside the repository root the hook was "not found" and the call went through unchecked. *Note of 2026-11-16 (D-49).* The tracked file now calls the hook in a project-directory form that does not depend on the working directory. The owner approved retaining that form on 2026-11-16; who made the edit is unknown, and no decision ID or § 5 line records it ([§ 10e](#10e-publication-scope-decision-d-49-2026-11-16)) |
| `.claude/hooks/check-commit-format.sh` | Make the scope optional only for `docs` and `release` | The hook accepts a missing scope for every type; `commit-format.md` allows it only for those two (steward prime) |
| `commit-format.md` | State that a squash merge is given an explicit subject in the commit grammar | GitHub can append the pull-request number; the hook does not see merges (D-34) |
| `commit-format.md`, scope table | Name the scope for `scripts/validate.sh` and for the provisioning script | No row covers a general script (OQ-34) |
| `product-vision.md`, scope lock | Say that file-based Compose secrets are part of the base build | The scope lock calls the mechanism OPTIONAL; `security-patterns.md` requires it (OQ-26) |
| `product-vision.md`, scope lock and "Hard No" | Say where the MUST HAVE part of network separation ends | AC-07 tests from an unauthorised container while network isolation is EXTRA (OQ-27) |
| `security-patterns.md`, "Firewall and network" | Add the monitoring source to the TCP 443 allow line, or state that it lies in the client network | The active HTTPS check comes from the Checkmk source (OQ-28) |
| `test-requirements.md`, "Gates" | Update the Butane command when the scaffold fixes it; add a control that fails on any option disabling certificate verification in `tests/` or `scripts/` | Already foreseen by the rule; the control is the security draft's proposal |
| `test-requirements.md`, "Conventions" | Name the tests that are not read-only beyond `restore` and `restart`: probe containers, a sent test message, a stopped service, a written post | Several designed tests write to the lab |
| `test-requirements.md`, AC-01 proof | Add the Docker CE proof block | The acceptance table has no row for a reviewer decision (D-32) |
| `versioning.md`, `commit-format.md`, `test-requirements.md`, `product-vision.md` | Nothing to change if the owner confirms D-20 … D-25; otherwise they follow the owner's amendment | They already state those proposals as policy (F-15) |
| repository root | Add a short `CLAUDE.md` at the scaffold step | Methodology M-06; R-21 |

*Note of 2026-11-16 (r7, § 10f).* The row on `versioning.md`, `commit-format.md`, `test-requirements.md` and `product-vision.md` says "nothing to change if the owner confirms D-20 … D-25". The owner approved D-20, D-21, D-22 and D-23 on 2026-11-16; D-24 and D-25 are still proposals, so that row is not yet fully answered. No rule was edited by this pass.

Not a rule, noted for the owner: `.claude/settings.local.json` (ignored by git) pre-approves `gh issue *` and `gh pr *` for agent sessions on this machine. The publication gate is therefore held by the steward's instructions, not by a permission prompt.

## 8. The open tooling question

Carried forward unanswered (OQ-17): whether to remove the `analyzing-ai-repos` skill and the `ai-engineer-doc-architect` prompt, both written for AI repositories. This session widened the question: the toolkit under `.claude/skills/` also holds third-party skills — one ships a licence file, one declares a licence in its header, others state no origin — and all of it would be published with the first commit. Nothing was removed.

## 9. Document status

| Document | Revision | Status | Reviewed by |
|---|---|---|---|
| [README.md](README.md) | r2 | ready-for-human-review | plan-critic (as input), orchestrator |
| [core-context.md](core-context.md) | r2 | ready-for-human-review | plan-critic (as input), orchestrator |
| [source-register.md](source-register.md) | r2 | ready-for-human-review | plan-critic (as input), orchestrator |
| [decision-log.md](decision-log.md) | r2 | ready-for-human-review | plan-critic (as input), github-steward (as input) |
| [open-questions.md](open-questions.md) | r2 | ready-for-human-review | plan-critic (as input), github-steward (as input) |
| [methodology-adaptation.md](methodology-adaptation.md) | r1 | ready-for-human-review | plan-critic (as input; one gap found and closed as R-21) |
| [plan-review.md](plan-review.md) | r2 | ready-for-human-review | plan-critic (full review of r1) |
| [implementation-plan.md](implementation-plan.md) | r1 | ready-for-human-review | built from drafts the plan-critic reviewed; the integration itself was reviewed only by its author — the one document here without an independent review of its final text |
| [github-project-plan.md](github-project-plan.md) | r2 | ready-for-human-review | orchestrator |
| [delegation-manifest.md](delegation-manifest.md) | r3 | ready-for-human-review | — (a record) |
| [delegation/s1-platform-delivery.md](delegation/s1-platform-delivery.md) | r1 | draft, as its author left it; accepted as an input with corrections (implementation-plan § 7) | plan-critic, orchestrator |
| [delegation/s2-security-verification.md](delegation/s2-security-verification.md) | r1 | draft, as its author left it; accepted as an input with corrections (implementation-plan § 7) | plan-critic, orchestrator |
| [delegation/s3-critic-review.md](delegation/s3-critic-review.md) | r1 | draft, as its author left it; accepted as an input (plan-review § 9.1) | orchestrator |
| this report | r1 | ready-for-human-review | — |

No document is `approved`. Only the owner's recorded decision can make one so.

## 10. Limits of this report

- **Nothing was observed on the lab.** Every statement about how the platform will behave is a design or an assumption.
- **Upstream facts cover four sources.** Everything else about tools is marked unverified where it appears; Checkmk entirely.
- **The reviewer's answers are known through a pasted copy**, not the original message.
- **The scores are a decision aid.** The critic showed that the order from fourth to eleventh place is not meaningful between neighbours.
- **The revisions are manual labels**, not commit hashes.

## 10a. After this report (2026-11-14)

Two owner decisions were carried out after r1 was written; the sections above are left as they were.

- **Diagrams 01–04** were regenerated with current text ([decision-log.md](decision-log.md) D-44). Row 6 of § 6 and the note on footers in § 4 no longer apply.
- **The generic toolkit** is excluded from the repository through `.gitignore` (D-45). Row 7 of § 6 and § 8 no longer apply, and the file count of § 4 falls from 220 to 91. The steward repeats the scan before anything is published.
- [README.md](README.md), [open-questions.md](open-questions.md), [decision-log.md](decision-log.md) and [github-project-plan.md](github-project-plan.md) are at r3 and the baseline label is `docs-baseline-r3`; the revisions in § 9 show the earlier state.

## 10b. Reconciliation of 2026-11-16

Written by the orchestrator session at the owner's request to reconcile the records. It corrects records and references. **No proposal changed status, no document was approved, and both gates stay closed.** Nothing was committed, published, built or tested, and the lab was not contacted.

The sections above are left as written: §§ 1–10 describe the state at r1, and § 10a the state on 2026-11-14 after D-44 and D-45. Where they differ from this section, this section is the current one. The scan of § 4, the link check of § 5 and the reviews of § 9 are results of 2026-11-14 and are not repeated here unless a line below says so.

### What happened after § 10a

- **D-46** was recorded on 2026-11-14: the repository is bilingual where that is needed; which files need both languages is not decided. That made `docs-baseline-r4`.
- **The steward's plan went to r4** on 2026-11-14: sub-issue S2.2 was split at the owner's relayed answer. § 10a still says r3.
- **Two policy files were added on 2026-11-16**, outside this package: `.claude/rules/herdr-orchestration.md` and `.claude/references/herdr-orchestration.md`. With them `git add -A --dry-run` listed 93 files.
- **A plan file appeared on 2026-11-16 while this section was being written**: `.agents/plans/proxmox-admin-agent-plan.md`, written by another session at the owner's request. It is no part of this reconciliation and was not reviewed here. With it the list has **94 files** (counted on 2026-11-16 after the edits below). The figures 220 (§ 4) and 91 (§ 10a) are the counts of 2026-11-14.

### Records corrected on 2026-11-16

| File | Now | What changed |
|---|---|---|
| [decision-log.md](decision-log.md) | r5 | **D-47** records the owner's answer of 2026-11-14 on the split of S2.2, which stood only in the project plan. A note under § 2 records the changed drop label of diagram 03 as a completed correction without a decision record. Dated notes on D-12, D-29 and D-46. § 3 statuses and § 5 are untouched |
| `.claude/rules/product-vision.md` | — | The "Language" paragraph states D-46 and its open part. No file is named as bilingual; no other paragraph changed |
| [open-questions.md](open-questions.md) | r5 | r4: OQ-07 says that D-30 needs no answer and that D-26 and D-29 are proposals whose work is done. r5, in the final pass below: OQ-35 added. No question answered or closed |
| [core-context.md](core-context.md) | r3 | The language constraint carries its qualification by D-46; the decision summary follows decision-log r5 |
| [source-register.md](source-register.md) | r3 | A dated note on SR-15: its remark on the diagram footers describes the diagrams as migrated |
| [plan-review.md](plan-review.md) | r3 | A dated note under F-16. No finding, score or rank changed |
| [delegation-manifest.md](delegation-manifest.md) | r4 | A dated note after the outcome table: plan r3 and r4 came after the recorded review |
| [README.md](README.md) | r6 | r5: baseline `docs-baseline-r5`; the index says which plan revision was reviewed. r6, in the final pass below: baseline `docs-baseline-r6` for OQ-35 |

Left unchanged on purpose: [github-project-plan.md](github-project-plan.md) is the steward's file. Its header and § 17 name `docs-baseline-r2` and decision-log r3, and § 7 says the decision-log record of the split "is the orchestrator's to write". Those lines are records of when the plan was written; a later steward revision can cite D-47. [implementation-plan.md](implementation-plan.md) needs no change for the split: both halves stay in step D6.

### Review state

Listing a revision here says what is on disk. It does not say that the revision was reviewed.

| Document | Revision | What an independent review covers |
|---|---|---|
| [github-project-plan.md](github-project-plan.md) | r4 | r1, reviewed by the orchestrator on 2026-11-14 and accepted as r2 (its § 16). **r3 and r4 are not reviewed**, and that includes the three things r4 adds beyond the owner's answer: the criterion on the message the allowed client queues, the AC-05 re-run in S2.3, and the move of S3.1's dependency to S2.3 |
| [implementation-plan.md](implementation-plan.md) | r1 | As in § 9: the integration was reviewed only by its author |
| this report | r3 | §§ 1–10a: none, as in § 9. § 10b: see the next line and the final pass |
| the seven package files and the rule file of the table above | as listed | **The edits of 2026-11-16 only**, by a session other than their author; the outcome is the last line of this section. The documents as wholes keep the review state of § 9 |

### Verified on 2026-11-16

| Check | Result | How |
|---|---|---|
| Does `diagrams/04-swarm-argue-dark.png` (2026-11-14 13:34) still match its SVG (rewritten 14:44)? | **Matches. Nothing was regenerated** | A worker session rendered the current SVG with headless Chromium (the headless shell already installed on the workstation; nothing was installed) at the PNG's size, 2341 × 1407: the result is byte-identical to the tracked PNG (sha256 begins `937cf565333e283d`). Control: the same method on diagram 03, whose PNG and SVG come from one run, is also byte-identical (`af283fd03d9389b6`). Sensitivity: a copy of the SVG with one changed label gave a measurable pixel difference. The generator uses counters for ids and seeds, so a re-run with unchanged source rewrites the same text with a new modification time. The orchestrator re-checked the checksums. What the 04 text files held before 14:44 cannot be shown: no earlier copy exists |
| Relative links and heading anchors | **No broken link** | Checked after the edits of this section. `README.md` and `docs/`: 17 Markdown files, 240 relative links and images. `.claude/rules/`, `.claude/references/`, `.claude/agents/` and the mission: 14 files, 26 relative links. § 5 reports the check of 2026-11-14 |
| Private data in the files that would be tracked | **Nothing found** | The orchestrator's check over the 94 paths, after the edits of this section and including the new plan file: no handoff, local settings, rendered Ignition or secrets file in the list; no file over 5 MB; no secret pattern, absolute home path, former working name, repo-local git identity value or lab identifier (the last two compared without printing them); the only mail address is the no-reply address that the commit rule and its skill quote as forbidden. **This is not the steward's Stage 2 scan**, which is still to be repeated before anything is published |
| Gate state | **Both closed** | [decision-log.md](decision-log.md) § 5 reads "(no approval recorded)"; the branch has no commit, no remote and no tag. *Note of 2026-11-16 (r8, § 10g): that is the state of that pass. The initial publication was made later the same day (D-54): `main` carries one commit and no tag exists; the implementation gate is closed* |

### Not verified, and still open

1. **Plan r3 and r4** have no review. The merits of the steward's three additions were not examined here.
2. **D-47 rests on a second-hand record**: the steward wrote down an answer relayed by the orchestrating side. The owner's own wording is not in the repository.
3. **The diagram 03 label** has no recorded author or authority. The change itself is verified; who decided it is not.
4. **The open part of D-46** (which files need both languages, and in what form) had no row in [open-questions.md](open-questions.md). The owner asked for one; it is OQ-35, added in the final pass below. The question is open: no file was chosen and nothing was translated.
5. **Two questions the steward proposed** (the Proxmox role its S6.1 needs; who creates board views) are in the plan's § 11 and § 17 and not in open-questions.
6. **The status label of the plan.** [README.md](README.md) defines `ready-for-human-review` as "passed its agent review"; plan r4 carries it without a review of r3 and r4. The label is the steward's to change.
7. **Counts in §§ 1–9 are those of r1.** § 1 says eleven owner answers were outstanding; on 2026-11-16 open-questions § 1 listed 21 rows under its two "owner answers needed" headings and 32 open rows in all; with OQ-35 it lists 22 under three such headings and 33 in all. § 6 asks for an answer on "D-20 … D-43": D-30 is superseded by D-45 and needs none.
8. **The two Herdr policy files and the new plan file** were not part of any earlier scan or review of this package. They passed the check above; they have not been through the steward's scan, and the plan file's content was not reviewed.
9. **The mission** (`.agents/plans/github-bootstrap-mission.md`, "Current state") describes an earlier scan than § 4 of this report. The mission is the steward's to update. *Note of 2026-11-16 (r7, § 10f): its "Current state" section was corrected on 2026-11-16 by the orchestrator session and no longer says this.*
10. **Noticed in the records and not examined:** the decision IDs jump from D-13 to D-20 with no note; § 2 row 7 and the manifest speak of twelve contradictions settled in implementation-plan § 7, whose table has seven rows; the "Proposed by" cells of D-35 … D-43 carry no date.
11. Everything in § 6 and § 7 that this section does not name is as it was: the publication-gate decisions, the implementation-gate decisions, the build inputs, and the proposed rule changes, including the hook and the local settings.

**Independent review of these edits:** done on 2026-11-16 by a worker session that did not write them (task REV-1, read-only). It is a technical review, not an approval. No blocking finding. Six findings on wording were raised as should-fix and all six were applied: three in the correction note of decision-log § 2, one in the evidence of D-47, one in the note on SR-15, and item 9 of the list above. Of seven minor findings six were applied; the optional restructuring of the long D-47 cell was not. The reviewer then re-checked the changed cells (REV-1b) and found them correct. That re-check raised three more points, all applied: the plan file that appeared meanwhile and the count it changes (94 files), the link count (240), and the wording of this paragraph. Not reproduced by the reviewer: the render of diagram 04, which is the diagram worker's result, and the scan for the former working name, which is the orchestrator's.

### Final pass, later on 2026-11-16

The owner asked for a narrow closing pass: record the open part of D-46, check the edits made after the review above, and take the counts again. It authorizes nothing else: no publication, no platform work, no lab contact, no approval.

**Changed in this pass.** [open-questions.md](open-questions.md) r5 has a new row, **OQ-35**: which files need both an English and a Hungarian version, and in what form. No equivalent row existed. It names no file and prefers no form. [README.md](README.md) r6 carries `docs-baseline-r6` for it. This report is r3: its header; the open-questions, README and "this report" rows above; the counts, item 8 and the review paragraph updated after REV-1b; items 4 and 7; and this subsection. No other tracked file was edited: [decision-log.md](decision-log.md) stays r5, and [core-context.md](core-context.md) r3 still names open-questions r4 as the revision it was written against, because nothing in it depends on OQ-35.

**Counts, taken again from the tree after the last edit of this pass** (2026-11-16, about 04:22 local time). A file that changes later is not covered by them.

| Count | Value | Scope |
|---|---|---|
| Files that would be tracked | 94 | every path `git add -A --dry-run` lists: the whole working tree minus what `.gitignore` excludes. It includes `.agents/plans/proxmox-admin-agent-plan.md` |
| Relative links and images | 247, none broken | `README.md` and every Markdown file under `docs/` (17 files); heading anchors resolved. The figure of 240 above was taken before this pass; the difference is the links this pass added |
| Relative links | 26, none broken | the Markdown files of `.claude/rules/`, `.claude/references/`, `.claude/agents/` and `.agents/plans/` (15 files). The earlier figure of 14 files left out the new plan file |
| Open questions | 33, of which 22 are owner answers | rows of open-questions § 1; "owner answers" are the rows under its three "owner answers needed" headings (12, 9 and 1) |
| Decisions | 17 decided, 23 proposed, 1 superseded | rows of the decision log: D-01 … D-13 and D-44 … D-47 decided; D-30 superseded; the proposed rows include D-26 and D-29, whose work is done |

**Publication hygiene, same tree.** The mechanical check of the table "Verified on 2026-11-16" was run again over all 94 paths with the same result: nothing found. For `.agents/plans/proxmox-admin-agent-plan.md` that is a pattern scan only. Its content was not reviewed, it was not edited, and passing the scan says nothing about whether it belongs in the repository or may be published. The steward's Stage 2 scan remains to be done.

**What this pass did not touch.** The provenance of the diagram 03 label is as uncertain as above. D-47 still rests on the steward's record of a relayed answer; its wording is with the owner. Plan r3 and r4 are still not reviewed. [decision-log.md](decision-log.md) § 5 still reads "(no approval recorded)", and both gates are closed.

**Independent review of the final pass:** done on 2026-11-16 by two worker sessions that did not write the edits, both read-only. One read the text changed since the review above (task REV-2): the edits made after REV-1b, OQ-35 and the references to it. The other took the counts and the hygiene check again with its own tools (task CNT-1). CNT-1 found no mismatch with the table above. REV-2 raised five minor findings on wording and none that was blocking or should-fix; all five were applied: three in this section, one in the README, and the first wording of this paragraph, which was written before the reviews ended and said that neither had raised a finding. The reviewer then checked the applied wording (REV-2b) and confirmed it; no edit followed that check. A technical review is not an approval.

## 10c. Scheduling decision D-48 (2026-11-16)

Written by the orchestrator session after the owner decided one question about the order of future work. **It is a documentation change only. Both gates stay closed, no proposal other than the one question was decided, and nothing was committed, published, built or tested.** § 10b is left as written; where it says that plan r3 and r4 have no review, the next paragraph is the later state.

### What led to it

On 2026-11-16, after § 10b, two worker sessions reviewed [github-project-plan.md](github-project-plan.md) r3 and r4 read-only, at the owner's request: the split of S2.2 and the three things the steward added in r4. A second read-only pass checked the assumptions of that review against the official Postfix, Caddy and Docker Compose documentation. Both were reported to the owner in the session and are not repository documents. Their recommendations are **proposals**; the owner decided one of them.

### What the owner decided

**D-48** ([decision-log.md](decision-log.md) § 2): the logs sub-issue S3.1 may be integrated and accepted after S2.2, without waiting for S2.3, provided its own prerequisites and acceptance conditions are satisfied. It answers § 15 point 9 of the steward's plan.

- S3.1's other prerequisites still apply, and so does the implementation gate.
- **AC-04 stays mandatory for the release.** S2.3 still has to be done before the release gate.
- It is one exception to the exit rule of [implementation-plan.md](implementation-plan.md) § 3. D-33 as a whole is still a proposal.
- The owner's conditions are in the D-48 row: one designated writer at a time for shared files; S2.3 deployed outside the renewal-trial window while the described deployment procedure restarts Caddy; re-runs for checks a later change actually affects; the release evidence also shows the search for a Postfix queue ID; no unconditional dependency on S2.3 for S3.2 or S5.1.

### Records changed

| File | Now | What changed |
|---|---|---|
| [decision-log.md](decision-log.md) | r6 | Row D-48; a dated note on D-33, whose status is unchanged. § 3 statuses and § 5 untouched |
| [implementation-plan.md](implementation-plan.md) | r2 | Rule 5 under the table of § 3. The table, the exits and the "May claim" column are unchanged |
| [github-project-plan.md](github-project-plan.md) | r5 | By the steward, its designated writer: S3.1 depends on S2.2 instead of S2.3; the notes that follow from D-48; § 15 point 9 answered |
| [README.md](README.md) | r7 | Baseline `docs-baseline-r7`; the index points here for the plan's review state |
| this report | r4 | This section |

Not changed: [docs/architecture.md](../architecture.md), its requirements table and its acceptance table; `.claude/rules/`; [open-questions.md](open-questions.md), because the decision answers an open point of the steward's plan and no numbered question; [delegation-manifest.md](delegation-manifest.md), which records the preparation sessions of 2026-11-14 and not the order of future work; [core-context.md](core-context.md) r3, whose summary of owner decisions therefore ends at D-47.

### Review state of the steward's plan

| Revision | State |
|---|---|
| r1 | Reviewed by the orchestrator on 2026-11-14 and accepted as r2 (its § 16) |
| r3, r4 | Reviewed read-only on 2026-11-16 by two worker sessions, with findings. The findings are proposals and are **not** applied, except the one question D-48 decides. The review does not approve r3 or r4 |
| r5 | The D-48 changes only. Reviewed as part of the review recorded at the end of this section |

### Left pending on purpose

1. **The mail-test proposals of the review**: how the AC-05 test message is kept from being delivered and how it is removed, queue clean-up criteria, exact Postfix settings, further test conditions for S2.2 and S2.3. None is in the plan; each waits for the owner.
2. **The proposed rewording of the renewal-trial criterion** in S3.2 (Caddy undisturbed instead of "no merge to `Caddyfile` or `compose.yaml`"). The existing criterion stands.
3. **Which sub-issue attaches the Postfix egress network**, with D-36.
4. **D-47** is as recorded in § 10b: a relayed answer, not confirmed anew.
5. Everything else that § 10b lists as open, except its item 1 as far as the paragraph above goes.

### Review of this change

**Independent review:** done on 2026-11-16 by a worker session that wrote none of the edits (task REV-3, read-only). It compared the five files of the table above with their previous versions by content and checked the dependency lines of the steward's plan with its own tool: no cycle, and AC-04 is still required for the release by the E2 epic, the E5 table and the final acceptance pass. No blocking finding.

- **Two should-fix findings.** The plan's scheduling notes covered the deployment of S2.3 but not its merge, which the standing S3.2 criterion on `compose.yaml` merges also catches; the steward added that to its notes, with no new dependency and no changed criterion. And the r5 row of the table above pointed to this paragraph before it existed; this paragraph settles it.
- **Four minor findings** on wording and references, all applied: one in the D-48 row, three in the steward's plan.
- **Checked by the orchestrator as well:** decision-log, implementation-plan, README and this report are byte-identical to their previous revisions once the edits listed above are reversed. The reviewer's own comparison covered decision-log and implementation-plan against their exact previous revisions; its copies of README and this report were older, so for those two the orchestrator's check is the one that counts.
- **Outside this review:** the documentation pass on Caddy and Docker Compose named under "What led to it" was another worker's; files that other sessions added to the working tree during this change are no part of it and were not opened.

The reviewer then checked the applied corrections (REV-3b) and confirmed them, with one minor finding on the wording of the bullet above, which was applied. It confirmed that wording in a last check (REV-3c); no file of the table above was edited after that check. A technical review is not an approval, and both gates are closed.

## 10d. Documentation closeout DOC-1 (2026-11-16)

Written by the documentation worker of task DOC-1, on the owner's instruction of 2026-11-16 for local documentation preparation and corrections (relayed to DOC-1 by the orchestrator session; not recorded in this package). **It corrects records and references. No decision was recorded or changed, no proposal changed status, no document was approved, and both gates stay closed.** Nothing was committed, published, built or tested, and the lab was not contacted. The baseline label is `docs-baseline-r8`. §§ 1–10c are left as written; where they differ from this section, this section is the current one.

### What this section supersedes

- **The pre-publication scan** of § 4, the "scan is clean" check 12 of § 2, and the hygiene checks of § 10b describe trees of 220 files (2026-11-14), 91 (after D-45) and 94 (2026-11-16, earlier). On 2026-11-16 between 06:14 and 06:17 local time (the same count at both times), the list of files that `.gitignore` leaves visible holds **154** (listing only; nothing was staged). The difference of 60 from 94 is the lab-administration tooling set (54 files under `lab-agent/`, `.mcp.json`, one agent definition, one hook, one governance diff; [source-register.md](source-register.md) SR-31) and the two agent briefs (SR-28, SR-29). **No earlier scan covered those files, nor the current content of files changed after the count of § 10b (about 04:22), among them `.claude/settings.json` and `.agents/plans/proxmox-admin-agent-plan.md`.** The orchestrator session then ran a preliminary pattern scan (below). The steward's Stage 2 scan is still to be done before anything is published. *Note of 2026-11-16 (D-49).* The count of 154 and the difference of 60 are superseded by [§ 10e](#10e-publication-scope-decision-d-49-2026-11-16): the lab-administration tooling set is excluded from the initial publication and the listing is 95 paths.
- **The preliminary scan of 2026-11-16, as observed by the orchestrator session and not by DOC-1.** It ran at 06:10 over the 154 candidate files (content snapshot `24e3d0981e7c3d9c`; 147 text files scanned, 7 PNG files not text-scanned). It found no hit for never-publish files, mail addresses outside the scan's allow-list, which § 22.1 of that plan lists as the orchestrator stated it, absolute home paths, the local user and host name, the repo-local git identity or the former working name; the pattern hits were triaged as rule text, redaction patterns, placeholders and test fixtures. It was taken on a changing tree and is **not publication evidence**: the final scan is still required after the contents are settled ([github-project-plan.md](github-project-plan.md) § 22).
- **The plan for a root `CLAUDE.md`** at the scaffold step (R-21; row "repository root" of § 7; step D2): a root `CLAUDE.md` and a root `AGENTS.md` exist since 2026-11-16, added outside this package. The rows are kept as written; dated notes in [core-context.md](core-context.md) § 5, [implementation-plan.md](implementation-plan.md) § 3, [methodology-adaptation.md](methodology-adaptation.md) and [plan-review.md](plan-review.md) § 6 say so, and [source-register.md](source-register.md) lists both files.
- **The counts of the final pass of § 10b**, taken again from the tables of the records:

| Count | Value | Scope |
|---|---|---|
| Decisions | 18 decided, 23 proposed, 1 superseded | rows of the decision log: D-01 … D-13 and D-44 … D-48 decided; D-30 superseded; the proposed rows include D-26 and D-29, whose work is done. The "17 decided" of § 10b was taken before D-48 |
| Open questions | 33, of which 22 are owner answers | unchanged from § 10b: OQ-01 … OQ-35 less the two closed (OQ-17, OQ-23) |
| Relative links and images | 330, none broken | `README.md`, `AGENTS.md`, `CLAUDE.md` and the 16 Markdown files under `docs/`, the steward's plan at r6 (`394cf796e1954ab9`) included; heading anchors resolved. Taken after the last edit of DOC-1b; a file that changes later is not covered. Of the 330, 281 are in `README.md` and the 15 files other than the steward's plan |
| Table column counts | no mismatch | every table of the 19 Markdown files (`README.md`, `AGENTS.md`, `CLAUDE.md`, 16 under `docs/`) |
| The steward's plan | resolves at r6 | during the first checks of this pass its link list at line 21 pointed to five sections numbered 18 … 22 that did not exist yet, so five anchors did not resolve. With r6 on disk they do, and the count above includes the file |
| Paths named in the two agent briefs | as expected | `AGENTS.md` and `CLAUDE.md` hold no Markdown link. Of the paths in their code spans, the only ones missing are the planned platform layout and `docs/_base/`, which both briefs say do not exist |

**The steward's plan, r6.** On 2026-11-16 [github-project-plan.md](github-project-plan.md) exists as r6, status `draft`, 1091 lines, sha256 prefix `394cf796e1954ab9`, with sections 18 to 22 added (completeness, identifier mapping, dependency check, outstanding publication decisions, publication hygiene). **Plan r6 received a final independent read-only review on 2026-11-16, by a reviewer session other than its author, with no blocking finding, six should-fix and seven minor findings (as reported by the orchestrator session, not observed by DOC-1).** The plan is now **r7**, status `draft`, 1097 lines, sha256 prefix `f4e8f0130a36b2a7`, which carries the corrections. **Plan r7 was confirmed by that reviewer on 2026-11-16 with no blocking finding.** Two minor wording points and the status field were then changed by the steward (status now `ready-for-human-review`, sha256 prefix `9f4cdc17542bdcd9`, 1097 lines); those last changes, like the changes of this DOC-1d step, were checked by the orchestrator by diff and not by the reviewer. A technical review is not an owner approval, and both gates stay closed. The documentation corrections of this section were themselves reviewed twice by sessions other than their author (first review: one blocking, three should-fix and five minor findings, all applied; final review: no blocking finding). DOC-1 did not edit the plan.

### Settled by a record that existed

- **"Twelve contradictions" against a table of seven rows** (§ 10b, item 10). The twelve are the critic's table in [delegation/s3-critic-review.md](delegation/s3-critic-review.md) § 9. [implementation-plan.md](implementation-plan.md) § 7 settles or escalates them in three places: its seven-row table, the table of corrections taken from the critic's review, and the exits and spike questions of §§ 3–4 (the order of AC-02 and of the restart checks; the SELinux precondition SP-11). Each of the twelve was matched to one of them on 2026-11-16. This resolves the counting mismatch only; the settlements remain proposals.

### Noticed in the files and not decided

Each is listed so that the owner or the file's own writer can act. None was changed here, because the files are outside DOC-1's ownership or the choice is the owner's.

1. **The lab-administration tooling is recorded by no decision** and is not covered by `.gitignore`, so it would be published with the first commit. `AGENTS.md` "Safety" says it is present and not authorized. Whether it is published, excluded or kept elsewhere is the owner's decision. Its own reports of tests and behaviour are not verified here. *Note of 2026-11-16 (D-49).* Superseded by [§ 10e](#10e-publication-scope-decision-d-49-2026-11-16): the owner decided that the set is excluded from the initial publication, and it is covered by `.gitignore`. It is still recorded by no authorization, and its own reports are still not verified.
2. **A decision-ID collision.** The lab-administration plan and its governance diff, under `.agents/plans/`, propose decisions D-48, D-49 and D-50. **D-48 is recorded in decision-log r6 for a different decision** (the order of S3.1). An ID is never reused. Left to the plan's author and the owner. *Note of 2026-11-16 (D-49).* D-49 is now recorded for a different decision, so both the plan's numbering and the unapplied renumbering proposal collide with the log; see [§ 10e](#10e-publication-scope-decision-d-49-2026-11-16).
3. **Local settings.** `.claude/settings.json` lists the lab server's tools under `allow`, while `AGENTS.md` says not to use that server until the owner has recorded the authorization. The same kind of arrangement as the pre-approved `gh` commands noted at the end of § 7: the gate is held by instruction, not by a prompt. The commit hook is still called by a path relative to the working directory (first row of § 7); that row stands. *Note of 2026-11-16 (D-49).* Superseded by [§ 10e](#10e-publication-scope-decision-d-49-2026-11-16): the lab server's entries, the guard hook registration and two read-deny entries left the tracked `.claude/settings.json` for the untracked local settings, and the commit hook is called in a project-directory form. Whether `mcp__pve__*` is allowed for every session is still the owner's open decision.
4. **Generic toolkit outside D-45.** The 26 files under `.claude/commands/` and two agent definitions named for PRP work are visible to `git` and not named by D-45 or CQ-08. They were not reviewed by DOC-1. *Note of 2026-11-16 (r7, § 10f): the owner decided that these 28 files are kept (D-50); they stay in the candidate set, subject to the final manifest.*
5. **Unnumbered gap and undated cells in the decision log.** D-14 … D-19 never appear, and the "Proposed by" cells of D-35 … D-43 carry no date (§ 10b, item 10). The decision log is the orchestrator's; proposed wording is in DOC-1's report.

### Not verified

- **No file under `lab-agent/` was read.** A search of it for decision-ID strings listed three file names and showed no content. The plan, the agent definition, the hook's header, `.mcp.json` and the settings were read; the code, its tests and its documents were not.
- **The reference file** `.claude/references/herdr-orchestration.md` was not read by DOC-1.
- **The rows of [core-context.md](core-context.md) § 5 on the Proxmox token and on the workstation tools** are the state of 2026-11-14 and were not observed again.
- **Other sessions write in this checkout.** The counts above are those of the time named and cover no file changed later.
- **Review of these edits.** An independent reader reviewed the first version of this pass and raised nine findings; all nine were applied on 2026-11-16 (DOC-1b). The corrected edits have not been reviewed again. A technical review is not an approval.

### Records changed

| File | Now | What changed |
|---|---|---|
| [README.md](README.md) | r8 | Baseline `docs-baseline-r8`; the Purpose names the tree outside the platform layout; the index points here for the state of 2026-11-16 |
| [core-context.md](core-context.md) | r4 | § 10 follows decision-log r6 (D-48); § 5 note; § 6 points to OQ-35; § 9 names the agent brief |
| [source-register.md](source-register.md) | r4 | SR-28 … SR-31 |
| [methodology-adaptation.md](methodology-adaptation.md) | r2 | A dated note on M-06 |
| [plan-review.md](plan-review.md) | r4 | A dated note on R-21 |
| [implementation-plan.md](implementation-plan.md) | r3 | A dated note under the table of § 3 |
| this report | r5 | This section |

Not changed: [decision-log.md](decision-log.md) r6 and every decision, approval line and ID; [open-questions.md](open-questions.md) r5; [delegation-manifest.md](delegation-manifest.md) r4; [github-project-plan.md](github-project-plan.md), the steward's file; `docs/architecture.md` and its two tables; the Hungarian root `README.md`, whose status, scope list, documentation table and image link match the tree; `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.agents/`, `.gitignore`, `lab-agent/`.

## 10e. Publication scope decision D-49 (2026-11-16)

Written by the documentation worker of task DOC-C, on the instruction of the orchestrator session, after the owner decided one question about the scope of the initial publication. **It corrects records and references. Both gates stay closed, no proposal changed status, no document was approved, and nothing was committed, published, built or tested. The lab was not contacted.** The baseline label is `docs-baseline-r9`. §§ 1–10d are left as written, except for the dated notes that point here from § 7 and § 10d; where they differ from this section, this section is the current one. The facts below about changes to files outside this package were **observed by the orchestrator session** and given to DOC-C in its packet; DOC-C did not observe them unless a line says so.

### What the owner decided, and what it does not decide

**D-49** ([decision-log.md](decision-log.md) § 2, decision-log r7): the lab-administration tooling in the working tree — `lab-agent/`, `.mcp.json`, `.claude/agents/pve-lab.md`, `.claude/hooks/pve-guard.py`, `.agents/plans/proxmox-admin-agent-plan.md` and `.agents/plans/proxmox-admin-agent-governance.diff` — is **excluded from the initial publication**. Including it later requires a separate owner decision and a separate pull request. It is option C of [github-project-plan.md](github-project-plan.md) § 21.4 and answers item 1 of its § 21.8.

It is a decision about the scope of the initial publication only. It does **not**:

- open the publication gate or the implementation gate; [decision-log.md](decision-log.md) § 5 still reads "(no approval recorded)", and no approval line was added;
- authorize the lab-administration workstream or any contact with the lab, or accept any result of the workstream;
- set a condition for a later inclusion, which belongs to the later decision;
- amend D-20, the proposed scope list;
- settle items 2 to 7 of [github-project-plan.md](github-project-plan.md) § 21.8, which stay open.

### What this section supersedes

- **In § 10d, "What this section supersedes", first bullet:** the count of **154** visible files and its explanation of the difference of 60 from 94. After D-49 the listing is 95 paths (below). The 154 was a listing taken at 06:14–06:17 on a tree that was still changing; the arithmetic that relates it to the later figures is given under "What was done".
- **In § 10d, "Noticed in the files and not decided", item 1:** the statement that the tooling "is not covered by `.gitignore`, so it would be published with the first commit", and that whether it is published is the owner's decision. It is covered by `.gitignore` since 2026-11-16, and the owner decided: D-49. The same item's remark that no decision records the tooling is superseded as far as publication goes; no decision authorizes the workstream.
- **In § 10d, item 3 (local settings):** the statement that `.claude/settings.json` lists the lab server's tools under `allow`. Those entries are no longer in the tracked file (below). The remark that the commit hook is called by a path relative to the working directory is superseded by the section on the commit-format hook below.
- **Elsewhere:** no row of § 6 and no other section of this report lists the tooling as an open publication-gate decision, so nothing else needed a note. [github-project-plan.md](github-project-plan.md) § 21.4 and § 21.8 are the steward's file; the plan is at r8 and `ready-for-human-review`, and DOC-C did not edit it. § 10b still counts `.agents/plans/proxmox-admin-agent-plan.md` among the 94 files that would be tracked; that was true at its time (about 04:22) and is superseded by this section.

### What was done (observed by the orchestrator session, 2026-11-16, 08:07–08:13 local time)

- **`.gitignore`** (sha256 prefix `e5c801073cba0c63`): the six exact paths were added, with no wildcard for the two plan files, and the local-only agent instruction file of this checkout. The files stay on disk.
- **The listing.** `git ls-files -o --exclude-standard` lists **95** paths; it listed 161 before. The excluded group was 66 paths: 61 under `lab-agent/` (55 regular files and 6 symlinks under `lab-agent/tests/stubs/`) and the 5 other paths. **This is a listing, not the Stage 2 manifest.** DOC-C ran the same command at 08:17 local time and it printed 95. The figures 154 and 54 of § 10d and the figures 161 and 61 here come from different times. The orchestrator session's arithmetic: both listings have 95 paths outside the excluded group (154 − 59 and 161 − 66), so the difference of 7 lies entirely inside the excluded group, which grew from 59 to 66 paths between the two listings. DOC-C did not take either listing and reports this arithmetic as given.
- **The settings separation.** `.claude/settings.json` (tracked, sha256 prefix `b845c8ae2fe3d5b0`) now holds only the commit-format hook. The guard hook registration, every `mcp__pve__*` permission entry and the two read-deny entries for private paths outside the repository were moved, verbatim, to the untracked `.claude/settings.local.json`. Nothing was expanded. Whether `mcp__pve__*` is allowed for every session (SET-1 in the tooling's own closeout notes) is still the owner's open decision; the move decided nothing.
- **How the move was checked**, by the orchestrator session, with local harness checks and no lab operation: (a) the official Claude Code documentation states that hooks merge across user, project and local settings and that deny rules from any scope apply; (b) an isolated synthetic project on Claude Code 2.1.325, started with no MCP server, showed a hook registered only in local settings firing together with the project one, its deny blocking, a local deny rule applying and a local instruction file being loaded; (c) a fresh session in this checkout, with no MCP server, had the same harmless probe command blocked by the guard hook before and after the move. In isolation it also observed that `onFailure: "block"` blocks when a hook exits 1 and the same hook without it does not, and that a hook whose script file is missing blocks every shell command either way; a clone that kept the old tracked registration without the guard script would have met that. DOC-C reproduced none of these checks. The assumption that the plan's § 21.4 called unverified is therefore checked by the orchestrator session only.
- **`AGENTS.md`** (`aa480ff2883fc910`), "Safety": the two lab bullets now say that lab-access tooling is excluded from the initial publication (D-49) and is not in the repository, that a working copy may hold it as local untracked files, and that it is not authorized; and that a guard hook may run on shell commands in a local Claude Code session. **`CLAUDE.md`** (`491b3246ea9f8b21`): its guard-hook bullet is generic as well. No excluded path and no launcher name is named in either. The exact former wording is kept locally in an ignored file and is not quoted here. DOC-C matched the prefixes of `.gitignore`, `.claude/settings.json`, `AGENTS.md` and `CLAUDE.md` against the files on disk at 08:16 local time.

### The commit-format hook

The tracked `.claude/settings.json` calls the commit-format hook in the project-directory form (`bash "${CLAUDE_PROJECT_DIR}/.claude/hooks/check-commit-format.sh"`), which does not depend on the shell's working directory; DOC-C read the file and found that form. **The owner approved retaining that form on 2026-11-16.** Who made the edit of 07:17:48 local time, which the orchestrator session associates with this form, is **still unknown**. This is **not a decision-log entry and not a § 5 line**, and no decision ID was assigned. The first row of § 7 proposes calling the hook by a path that does not depend on the working directory; a dated note on that row says that the file now has such a form. The proposal itself, as a change of the owner's files, is still the owner's to record.

### Not verified, and still open

1. **The Stage 2 final scan** of [github-project-plan.md](github-project-plan.md) § 22.3, on a frozen manifest, is still to be run. The listing of 95 paths is a listing. DOC-C ran no secret or hygiene scan over those 95 paths; this pass edited four documentation files and checked links, tables and the listing count. *Note of 2026-11-16 (r8, § 10g): the decision log states that a pattern scan of the frozen set was run for the publication and reported 17 hits (D-54); the owner-only part of the scan was waived and is not run (D-56). The results of the checks are in the orchestrating session's private record and not in the repository.*
2. **Items 2 to 7 of § 21.8** of the plan (the contents of the bootstrap commit, the structural proposals, the commit author address, the licence, the first-commit procedure, the go-ahead) are open. *Note of 2026-11-16 (r7, § 10f): items 2 to 6 were answered later the same day (D-50 … D-53 and the approved proposals); item 7, the go-ahead, has not been given; point 14 of the plan's § 15 is not decided. Second note (r8, § 10g): the go-ahead was given later the same day and is used up (D-54); point 14 was answered, both edges are kept (D-55).*
3. **The tooling's own tests and reports** are not verified by this package. No file under `lab-agent/` was read by DOC-1 or DOC-C. D-49 accepts no result of the workstream.
4. **The decision-ID collision of § 10d, item 2, is wider now.** The excluded plan numbers its three proposed decisions D-48, D-49 and D-50; an unapplied renumbering proposal kept with the tooling uses D-49, D-50 and D-51. D-48 and D-49 are now recorded for different decisions, so **both numberings collide with the log**. Nothing was renumbered, applied or recorded; the proposals take whatever IDs are free if and when the owner records them. DOC-C did not read the unapplied proposal; this is as the D-49 row and the orchestrator's packet state it.
5. **The settings separation** was verified by the orchestrator session only, on one Claude Code version (2.1.325). A different version could merge settings differently. The guard registration and the deny rules now exist only in the untracked local settings of this one checkout. Whether they apply in a git worktree, a second clone or a session started without the local settings source was not tested; in those places the private files that the two read-deny entries protect are still on the workstation. The fresh-session probe exercised one trigger only, a shell command naming an owner-only tool. It did not exercise the MCP branch of the matcher, the deny rules or `onFailure` in this checkout, and no session with the MCP server running was tested.
6. **The author of the edit of 07:17:48** and the status of the commit-hook form are as described above.
7. **SET-1**, whether `mcp__pve__*` is allowed for every session, is open.
8. **Counts of §§ 10b and 10d** (94 and 154 files, 330 links) are those of their times and were not taken again, except the listing of 95. A file that another session changes later is not covered. DOC-C checked the links and tables of the four files it edited; the result is in its report, not repeated here.
9. **Review of these edits.** See "Review of this change" at the end of this section. A technical review is not an owner approval.
10. **§ 9 of this report** lists the revisions of r1 and is left as it was; its date and the "Reviewed by" column say so. The revisions that are current are in [README.md](README.md) and in the table below.

### Records changed

| File | Now | What changed |
|---|---|---|
| [decision-log.md](decision-log.md) | r7 | By the orchestrator session: row D-49; status `ready-for-human-review`. § 3 statuses and § 5 untouched |
| [README.md](README.md) | r9 | Baseline `docs-baseline-r9`; the Purpose describes the tooling set as excluded from the initial publication; the `docs-baseline-r9` column and bullet; the row of the plan; status `ready-for-human-review` |
| [core-context.md](core-context.md) | r5 | § 10 follows decision-log r7 and names D-49; a second dated note in § 5; status `ready-for-human-review` |
| [source-register.md](source-register.md) | r5 | SR-31 carries a dated note and no longer calls publication the owner's open decision; dated notes on SR-28 and SR-29; status `ready-for-human-review` |
| [github-project-plan.md](github-project-plan.md) | r8 | By the steward, its designated writer, in parallel with this pass; follows D-49; status `ready-for-human-review`. Not edited or reviewed by DOC-C |
| this report | r6 | This section; dated notes in § 7 and § 10d; status `ready-for-human-review` |

Outside this package, by the orchestrator session: `.gitignore`, `.claude/settings.json` (and the untracked local settings), `AGENTS.md` and `CLAUDE.md`, as described above.

Not changed: [open-questions.md](open-questions.md) r5, [methodology-adaptation.md](methodology-adaptation.md) r2, [implementation-plan.md](implementation-plan.md) r3, [plan-review.md](plan-review.md) r4 and [delegation-manifest.md](delegation-manifest.md) r4; `docs/architecture.md` and its two tables; `.claude/rules/` and the hooks; every decision other than D-49, every approval line and every ID.

### Review of this change

**Independent review:** done on 2026-11-16 by a session that wrote none of the changes (Claude Fable 5.2, read-only), in two parts, covering the whole option-C change. It ended at 08:40 local time with no blocking finding.

- **Three should-fix findings in the first part:** a wrong pointer in the plan's § 21.4, a dangling reference in SR-31, and the unrecorded checkout scope of the moved safeguards. They and three of the six minor findings were corrected by the files' writers before the second part, which judged those corrections adequate. Of the other three, one was a reminder acted on afterwards and two are observations left unchanged.
- **One should-fix finding in the second part.** It concerns a note in the excluded tooling's own documents and no tracked file.
- **Edits after 08:40:** the remaining minor corrections, this sub-section and the status fields. They were not part of either part. The review result and the file hashes it is tied to are kept in the orchestrator session's record.

A technical review is not an owner approval. Both gates stay closed.

## 10f. Publication preparation, owner answers of 2026-11-16 (D-50 … D-53)

Written by the documentation worker of task DOC-P, on the instruction of the orchestrator session, after the owner answered items 2 to 6 of [github-project-plan.md](github-project-plan.md) § 21.8 and authorized the **local** preparation of the publication. **It corrects records and references. Both gates stay closed, the owner's final go-ahead has not been given, no approval line was added to decision-log § 5, and nothing was committed, published, built or tested. The lab was not contacted.** The baseline label is `docs-baseline-r10`. §§ 1–10e are left as written, except for the dated notes that point here; where they differ from this section, this section is the current one. The facts below about files outside DOC-P's ownership were **observed by the orchestrator session** and given to DOC-P in its packet; DOC-P did not observe them unless a line says so.

*Note of 2026-11-16 (r8, § 10g).* The statements of this section that the go-ahead "has not been given", that nothing was staged, committed or pushed, that no GitHub object exists, that point 14 is undecided and that the scan on the frozen manifest is "not yet run" describe the state of `docs-baseline-r10`. Later the same day the go-ahead was given once and used up (D-54), the initial publication was made, point 14 was answered (D-55) and the owner-only part of the scan was waived and not run (D-56). Each is marked again at its place below; § 10g is the current state.

### What the owner decided, and what it does not decide

Recorded in [decision-log.md](decision-log.md) r8, § 2 (rows D-50 … D-53 and the subsection "Proposals of § 3 approved by the owner on 2026-11-16"):

- **D-50**, the contents of the bootstrap commit: the 28 command and agent files under `.claude/` are kept; `docs/.prepare/` is included in the initial publication; OQ-35 is not a prerequisite for it. The 95-path candidate set is the starting point, subject to the corrections the owner authorized and to the verification of the final manifest. Option C (D-49) is preserved. References to the repository's owner and name may stand in the five candidate files identified on 2026-11-16 (D-06); there is no exception for personal or lab-private data.
- **D-51**, points 1, 2, 3 and 7 of the issue tree ([github-project-plan.md](github-project-plan.md) § 15): scaffold and CI sit under E1; E6 keeps M1; D-41 and D-42 do not prevent the platform sub-issues from being prepared; the implementation of S0.3 … S0.7 belongs to the owner or to a session the owner assigns. For the issue tree only.
- **D-52**, the commit identity (OQ-21): the repo-local name and address appear in public commit metadata as they are, configured for this repository only; a GitHub no-reply address is not required. **The values are written in no tracked file, issue, pull-request text, board text or handoff.** The account's privacy settings are not changed; if a setting blocks the push, the specific blocker is reported. **Not decided: which identity squash merges made on GitHub carry** (D-52; [github-project-plan.md](github-project-plan.md) § 15, point 6).
- **D-53**, the licence (OQ-22): deferred. No project `LICENSE` file now; existing third-party licence and attribution obligations are preserved. OQ-22 stays open.
- **Approved proposals:** D-20, D-21, D-22, D-23, D-28 and, for the GitHub work tree and subject to the exception of D-48, D-33. For D-28 the owner stated that approving the procedure is not yet permission to create a commit or to push.

It does **not**:

- open the publication gate or the implementation gate; [decision-log.md](decision-log.md) § 5 still reads "(no approval recorded)";
- give the final go-ahead (item 7 of § 21.8), which is one separate decision of the owner, made after seeing the final manifest and the issue-tree summary; it has not been given. Until then nothing is staged, committed or pushed, and no GitHub object exists; *[note of 2026-11-16 (r8, § 10g): given later that day, once, and used up (D-54)]*;
- decide **point 14** of the plan's § 15 (the two added dependency edges, S5.3 on S2.3 and S4.2 on S4.1) or point 4: the owner said not to claim approval of an item whose content had not been presented. Point 14 is put to the owner with the go-ahead request *[note of 2026-11-16 (r8, § 10g): answered, both edges kept, D-55]*; point 4 stays open and, by the plan's § 21.6, is a question for the implementation gate;
- decide D-35 (the owner named each proposal instead), or approve the technical substance of D-41 or D-42, or any other proposal of § 3 (D-24 … D-27, D-29, D-31, D-32, D-34 … D-43);
- authorize the lab-administration tooling, which stays excluded and local (D-49), or any contact with the lab.

### What this section supersedes

- **In § 6, "At the publication gate" and "At the implementation gate":** rows 2 to 5 and 8 of the first table, and row 1 of the second, as the notes under those tables say. The tables are left as written.
- **In § 1 and in § 10b, item 7:** the counts of outstanding owner answers and of open questions are those of r1 and of the earlier passes of 2026-11-16; open-questions r6 has one open question fewer (OQ-21 is closed as CQ-09). The counts of this report are not taken again in this pass.
- **In § 10b, item 9; § 10d, item 4; § 10e, "Not verified", item 2:** dated notes say what changed. The remaining items of those lists are as they were.
- **In § 10e, the fourth bullet of "It does not":** "settle items 2 to 7 of [github-project-plan.md](github-project-plan.md) § 21.8, which stay open" describes the state when D-49 was recorded. Items 2 to 6 were answered later on 2026-11-16 (D-50 … D-53 and the approved proposals); item 7, the go-ahead, has not been given.
- **In § 7:** the row that says "nothing to change if the owner confirms D-20 … D-25" is partly answered, as the note under the table says.

### What was done

Written outside this report by the orchestrator session, and observed by it (2026-11-16, 09:08–09:18 local time): decision-log r8 (status `in-review` when written; `ready-for-human-review` since the lead set it after the review) and the "Current state" section of `.agents/plans/github-bootstrap-mission.md`, which now names the earlier scans as such, the D-45 and D-49 exclusions and the root briefs, and points to decision-log § 2; a dated note was later added to its "Owner decisions at the publication gate" section. The repo-local git identity was compared with the owner's values by hash, without printing them: it matches, and no global identity is set; nothing was changed. The candidate list of 09:05 held 95 paths, unchanged against the listing of 08:51.

Written by task DOC-P (this pass): [README.md](README.md) r10, [core-context.md](core-context.md) r6, [open-questions.md](open-questions.md) r6, [source-register.md](source-register.md) r6 and this report r7. In the same period the steward, its designated writer, produced [github-project-plan.md](github-project-plan.md) r9 following D-50 … D-53; DOC-P did not edit or review it. DOC-P ran `git ls-files -o --exclude-standard` read-only at the end of the pass; it listed 95 paths. This is a listing, not the Stage 2 manifest.

### What is not changed

- Both gates, and decision-log § 5 ("(no approval recorded)").
- Rows D-47, D-48 and D-49 of the decision log, and every decision other than D-50 … D-53 and the status changes of § 3 recorded in r8.
- `docs/architecture.md`, its requirements table (§ 2) and its acceptance table (§ 10); `.claude/rules/`, except the Herdr orchestration rule (see the paragraph under "Records changed"), the hooks and the settings files; `AGENTS.md` and `CLAUDE.md`, except for the refresh described under "Records changed"; `.gitignore`.
- The excluded lab-administration tooling and the governance diff: not read, applied, renumbered or started.
- [methodology-adaptation.md](methodology-adaptation.md) r2, [implementation-plan.md](implementation-plan.md) r3, [plan-review.md](plan-review.md) r4, [delegation-manifest.md](delegation-manifest.md) r4 and `delegation/*`.

### Not verified, and still open for the publication

1. **Point 14** of the plan's § 15 is not decided and is put to the owner with the go-ahead request; point 4 is not decided either. *Note of 2026-11-16 (r8, § 10g): point 14 was answered later that day, both edges are kept (D-55); point 4 stays undecided.*
2. **The go-ahead** (item 7 of § 21.8) has not been given. *Note of 2026-11-16 (r8, § 10g): given later that day, once, and used up (D-54).*
3. **The Stage 2 scan on the frozen manifest** ([github-project-plan.md](github-project-plan.md) § 22.3) is not yet run. The listing of 95 paths is a listing, not the manifest, and DOC-P ran no secret or hygiene scan; this pass checked links, anchors, table column counts and the listing count. *Note of 2026-11-16 (r8, § 10g): the decision log states that a pattern scan of the frozen set was run for the publication (D-54); its results are in the orchestrating session's private record and are not in the repository.*
4. **The two parts of checks 4 and 7** of that scan that the owner runs themselves are not done. *Note of 2026-11-16 (r8, § 10g): the owner waived them for the initial publication; their state is NOT RUN, and it is not a pass (D-56).*
5. **Checks 10 and 11** of that scan (the text of every body before it is posted; the commit identity of the commit step) exist only at Stage 2 and cannot be run before then.
6. **Every document changed by this pass is `ready-for-human-review`**, a status set after the review recorded below. A technical review is not an owner approval.
7. **Counts of §§ 10b, 10d and 10e** (94, 154, 330 links) are those of their times and were not taken again in this section; a file that another session changes later is not covered.
8. **Where the go-ahead itself is recorded** — in the decision log before the first commit (the manifest is then frozen and scanned again), or by the first pull request after the bootstrap (the scanned manifest stays unchanged) — is put to the owner with the go-ahead request. *Note of 2026-11-16 (r8, § 10g): the go-ahead is recorded, together with the answer of D-55, in the first pull request after the initial publication, as the owner chose (D-54, D-55).*

### Records changed

| File | Now | What changed |
|---|---|---|
| [decision-log.md](decision-log.md) | r8 | By the orchestrator session: rows D-50 … D-53; the subsection on approved proposals; Status cells and a note in § 3; status `in-review`. § 5 untouched |
| [github-project-plan.md](github-project-plan.md) | r9 | By the steward, its designated writer, in parallel with this pass; follows D-50 … D-53. Not edited or reviewed by DOC-P |
| [README.md](README.md) | r10 | Baseline `docs-baseline-r10`; the "Current label" paragraph, the baseline table, a new bullet, the row of the steward's plan, the reading order; status `ready-for-human-review` |
| [core-context.md](core-context.md) | r6 | § 10 follows decision-log r8; dated notes in §§ 5, 6, 8, 9, 12; status `ready-for-human-review` |
| [open-questions.md](open-questions.md) | r6 | OQ-21 closed as CQ-09; dated notes on OQ-07, OQ-22, OQ-35; dependencies follow decision-log r8; status `ready-for-human-review` |
| [source-register.md](source-register.md) | r6 | A dated note on SR-12; status `ready-for-human-review` |
| this report | r7 | This section; dated notes in §§ 1, 6, 7, 10b, 10d, 10e and 11; status `ready-for-human-review` |

Outside this package, by the orchestrator session: `.agents/plans/github-bootstrap-mission.md` ("Current state", and a dated note in "Owner decisions at the publication gate"); and, after the review of this pass, `.claude/rules/herdr-orchestration.md` with its linked reference `.claude/references/herdr-orchestration.md`, edited by the lead on the owner's separate instruction of 2026-11-16 (a model-selection, parallel-work and review policy). Also after that review, and after the manifest freeze of that day, the lead refreshed the root `AGENTS.md` and `CLAUDE.md` on the owner's choice: the handoff bullet (the session that leads the work reads the handoff; a worker or reviewer with a task packet reads only what the packet names), the one-time direct bootstrap push named in "Git & PR Conventions" (D-28, which still needs the owner's go-ahead), the policy line of "Deep-Dive Docs", and three lines under "Learnings" in `CLAUDE.md`. Neither edit is a publication decision, opens a gate or gets a decision ID.

Not changed: see "What is not changed" above.

### Review of this change

The documents changed by this pass were reviewed on 2026-11-16 by a session other than their authors, read-only, against the owner's instruction. In the documents it found no blocking defect, six should-fix findings and ten minor ones; all were corrected, as were four minor residues of its closing pass. The review is tied to the content of that day; a later change is not covered. It is a technical review: it is not an owner approval and opens no gate, it did not compare real names or the literal identity values, it did not run the final scan of the project plan's § 22.3 on a frozen manifest, and it made no GitHub query.

## 10g. Records pass after the initial publication (D-54 … D-56)

Written by the documentation worker of task DOC-R1, on the instruction of the orchestrator session, after the initial publication of 2026-11-16 and at the owner's request that three of the owner's statements of that day be recorded. **It corrects records and references only. It adds no decision and no approval, changes neither gate, and contacts neither the lab nor GitHub. The implementation gate is closed.** The baseline label is `docs-baseline-r11`. §§ 1–10f are left as written, except for the dated notes that point here; where they differ from this section, this section is the current one.

### What was recorded, and from which source

The rows and notes below were written by the orchestrator session into [decision-log.md](decision-log.md) r9; DOC-R1 did not edit that file and took the content from it. The rows D-54 … D-56 are that session's summary of its private record of 2026-11-16; **the owner's own wording is not in the repository.**

- **D-54**, the publication go-ahead: given once, on 2026-11-16, for the frozen 95-file candidate set within the scope and order of the orchestrator's request, with the limitations the owner accepted (the owner-only private-value scan waived and not a pass, D-56; a pattern scan whose 17 hits the request classified as rule text or pattern lists, a quoted path pattern, a default tool path in the diagram notes, or the fictional address block of diagram 03). **The go-ahead is used up and is not a standing authority.** Every later commit, branch, pull request, tag and GitHub object still needs the owner (D-09). It did not cover step 12 of the plan's § 12, the pull request that records these answers, any change to the account's privacy settings, or any platform or lab work.
- **D-55**, open point 14 of the plan's § 15: both added dependency edges are kept, S5.3 on S2.3 and S4.2 on S4.1. For the issue tree only; it opens no gate and changes no acceptance condition. Point 4 stays undecided.
- **D-56**, the owner-only comparisons of the plan's § 22.3 (check 4, the names of third parties; check 7, the real host name and addresses of the lab): **waived for the initial publication. Their state is NOT RUN. It is not a pass and it has no result.** No document may say "scan clean", "scan passed" or "publication verified" for the published set. The waiver covers the initial publication only; each later commit or pull request is scanned on its own and has its own owner-only part.
- **Dated notes** in the decision log on D-28 (the one direct bootstrap push was made; the exception is used up), on D-33 and D-51 (point 14 answered), and on the ID note: the next free ID is D-57.
- **§ 5 of the decision log** carries two dated narrow approvals of one read-only API connectivity check, each recorded at the owner's request before the connection it covers, and its placeholder reads "(no approval of the implementation gate recorded)". **Neither line is the approval of the implementation gate, both are used up, and the check they allowed is not evidence for any requirement.** The decision log does not record the outcome of the check, and this section does not claim one.

Facts the records state or that the orchestrator session gave DOC-R1 in its packet, **not observed by DOC-R1**: the repository is public; `main` carries the one bootstrap commit; issues #1 … #34, six milestones and the Projects board exist; no tag exists; no pull request had been opened before the one that carries these records. The decision log adds that one board field was named `Work Type` because GitHub rejected `Type`.

### What this section supersedes

- **In § 1, § 6 (rows 1, 2 and 8 of "At the publication gate"), § 10b ("Gate state"), § 10e ("Not verified", items 1 and 2) and § 10f** (the intro paragraph, "It does not" bullets 2 and 3, "Not verified" items 1 to 4 and 8): every statement that the go-ahead has not been given, that no commit, remote, tag or GitHub object exists, that point 14 is undecided, or that the owner-only part of the scan is still to be done. Each carries a dated note. The sentences themselves are kept as written; they describe the states of their dates.
- **In § 11:** the dated note under the verdict.

### Not verified, and still open

1. **The owner-only comparisons** (checks 4 and 7 of the plan's § 22.3) were never run, by anyone, and are waived for the initial publication. A private value found in the public commit later could not be withdrawn without rewriting public history, which needs the owner (D-56).
2. **The state of the published repository** was not queried in this pass: no `git` history query, no GitHub query, no comparison of the published blob hashes with the frozen manifest. The facts above are those of the decision log and of the orchestrator session's packet.
3. **Parent links, dependencies and board field values** of the published issue tree were not checked one by one after the publication run, and this pass did not check them either.
4. **The pattern scan of the frozen set** and the classification of its 17 hits are in the orchestrating session's private record and are not in the repository; they are not reproduced or checked here. The decision log's wording of the classification is the orchestrator's.
5. **The owner's wording** of the three statements is not in the repository; the rows are a summary of a private record.
6. **The read-only API connectivity check** of § 5: its outcome is not recorded in the decision log, and it is not evidence for any requirement or acceptance check. No part of it is verified here.
7. **The independent review of this pass** is recorded in "Review of this change" below, with the limits the reviewer stated. The status edit made after it was not reviewed again.
8. **Counts of §§ 10b, 10d, 10e and 10f** (94, 154, 330 links, 95 paths) are those of their times and were not taken again; a file that another session changes later is not covered.
9. **Everything in § 6, § 7 and § 10b to § 10f that this section and its notes do not name** is as it was, including the proposed rule changes and the open build inputs.

### What is not changed

- Both owner gates and [decision-log.md](decision-log.md) (written by the orchestrator session, not by DOC-R1), including its § 5.
- [github-project-plan.md](github-project-plan.md), which is the steward's; `AGENTS.md` and `CLAUDE.md`; `docs/architecture.md` and its two tables; `.claude/rules/`, hooks and settings; `lab-agent/` and the rest of the excluded tooling (D-49), which was not read, run or applied.
- [methodology-adaptation.md](methodology-adaptation.md) r2, [implementation-plan.md](implementation-plan.md) r3, [plan-review.md](plan-review.md) r4, [delegation-manifest.md](delegation-manifest.md) r4 and `delegation/*`.
- No open question was answered or closed.

### Records changed

| File | Now | What changed |
|---|---|---|
| [decision-log.md](decision-log.md) | r9 | By the orchestrator session: rows D-54 … D-56, dated notes on D-28, D-33, D-51 and the ID note, § 5. Not edited by DOC-R1 |
| [github-project-plan.md](github-project-plan.md) | r10 | By the steward, its designated writer, in parallel with this pass. Not edited or reviewed by DOC-R1 |
| [README.md](README.md) | r11 | Baseline `docs-baseline-r11`; the "Current label" paragraph, the Purpose (a dated note), the baseline table (new column), a new bullet, the row of the steward's plan, the reading order, the table "The two gates" (a dated note); status `ready-for-human-review` |
| [core-context.md](core-context.md) | r7 | § 10 follows decision-log r9; dated notes in §§ 5, 6, 9 and 10; status `ready-for-human-review` |
| [open-questions.md](open-questions.md) | r7 | A second dated note on OQ-07 (D-55); dependency revisions; status `ready-for-human-review` |
| [source-register.md](source-register.md) | r7 | Dated notes on the first bullet of "How revisions work here", on SR-12 and on SR-28; status `ready-for-human-review` |
| this report | r8 | This section; dated notes in §§ 1, 6, 10b, 10e, 10f and 11; status `ready-for-human-review` |

### Review of this change

Independent review: a separate Codex session (started with model `gpt-6.1-sol` and reasoning effort medium, read-only, without network) reviewed the uncommitted change of the eight files of this pass against the bootstrap commit on 2026-11-16, with the orchestrating session's private record of the publication day as the evidence for rows D-54 … D-56. First round: one blocking finding (a note in the steward's plan anticipated a decision that this pass does not record), one should-fix (the status fields of the changed documents disagreed) and one minor (a start time in D-54 that the record does not support). All three were corrected. Delta recheck of the two corrected passages: no blocking finding. The reviewer confirmed that § 5 of the decision log is byte-identical to its state before the pass. Limits the reviewer stated: it checked no live GitHub state, no published blob, no scan result and no result of the API check. The status fields were set after the review and that edit was not reviewed again.

A technical review is not an owner approval, and it opens no gate.

## 11. Verdict

**READY FOR HUMAN REVIEW**

*Note of 2026-11-16 (r7, § 10f).* This verdict is that of r1 and of the reviews recorded up to § 10e. This report's own status at r7 is `ready-for-human-review`, set after the review recorded in the last sub-section of § 10f; the verdict above is not repeated for the documents changed by the `docs-baseline-r10` step. The publication go-ahead has not been given, and both gates are closed.

*Second note of 2026-11-16 (r8, § 10g).* The verdict above is unchanged and is that of r1 and of the reviews recorded up to § 10e. This report's status at r8 is `ready-for-human-review`, set after the independent review recorded in § 10g. The publication go-ahead of 2026-11-16 was given once and is used up (D-54); the implementation gate is closed.
