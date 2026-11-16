# Methodology Adaptation — AI-Native SDLC Playbook → CoreOS Platform Lab

| Field | Value |
|---|---|
| Document ID | PREP-05 |
| Title | Methodology Adaptation |
| Revision | r2 |
| Status | ready-for-human-review |
| Owner | Orchestrator session (author); approver: repository owner |
| Last updated | 2026-11-16 |
| Core-context revision used | r1 |
| Dependencies | [source-register.md](source-register.md) r1 (SR-17, SR-18), [core-context.md](core-context.md) r1; for the dated note added in r2: [source-register.md](source-register.md) r4 (SR-28, SR-29) |
| Change summary | r1: first adaptation for this project. r2 (2026-11-16, documentation closeout DOC-1): one dated note under the table, on M-06 and the root `CLAUDE.md`. No row, decision or limitation changed. r2, extended on 2026-11-16 after an independent review (DOC-1b): the Dependencies field names the source-register revision of the note |

## Source and access

- **Fetched on 2026-11-14** as raw markdown: 1,374 lines, upstream commit `4a48004` (2026-09-03), sha256 prefix `37dbc5d6c40d`. Recorded as SR-17. Line references below point into that file and were spot-checked against it in this session.
- **Limitation:** by its own header (L3–6) the file is a community transcription of a vendor course. Its fidelity to the course is unverified.
- The playbook is a **methodology source only**. Nothing in it is evidence about this project.
- The owner's earlier adaptation for another project (SR-18) was read as prior art for the shape of the table. It used the same playbook revision. Its project-specific choices (time budget, toolchain, milestones) are **not** carried over.
- **Not claimed:** the playbook does not prescribe this package's file set, the weighted rubric, the two gates or the four-session topology. Those are the owner's choices (D-09, D-10, D-13).

## Scale translation

The playbook assumes an organisation with separate product, policy, platform and release roles, a CI system and managed settings (L30–143). This project has **one person**, **no stated deadline** (OQ-01), **no remote yet**, and a deliverable that is infrastructure on a private lab rather than an application behind a pipeline. Two consequences shape every row below:

1. **Proof comes from the lab, not from CI.** The playbook's feedback loop is a test suite that runs anywhere (L711–796). Here the decisive checks need the private VM, so they run by hand and enter the repository as evidence files. CI covers only the static layer.
2. **Roles collapse into the owner.** Every approval the playbook assigns to a product owner, tech lead, policy owner or release manager is the repository owner's. Separation of duties survives only as "no agent approves its own work".

| Playbook artifact | Here |
|---|---|
| `intent.md` | [core-context.md](core-context.md) § 1–4 and [open-questions.md](open-questions.md) |
| `spec.md` | [docs/architecture.md](../architecture.md), already written; its flagged concerns are [plan-review.md](plan-review.md) |
| `plan.md` | [implementation-plan.md](implementation-plan.md), then one issue per change |
| Committed artifact as stage trigger | The owner's recorded approval line (D-09), then the first commit |
| Policy owner's skills and hooks | `.claude/rules/`, the project skills, the commit hook |

## Principles

| # | Principle | Source (SR-17) | Decision | Application to this project | Required artifact or workflow | Verification method | Limitations |
|---|---|---|---|---|---|---|---|
| M-01 | **Capture intent in a file the originator corrects**: what is wanted, why, constraints, open questions | Stage 1, L144–240; template L181–193; "the product owner reviews and corrects" L157 | Adopt, adapted | No separate `intent.md`. The problem, outcomes, constraints and open questions are in core-context § 1–6 and in the open-questions list | core-context.md, open-questions.md | The owner reads core-context § 1–4 and corrects it; the correction or acceptance is recorded as an approval line | The intent was written by an agent from the architecture and the handoffs. The brief itself is not available (source register, "Sources that do not exist") |
| M-02 | **Requirements and design in one pass, with areas of concern flagged and worked through first** | Stage 2, L241–320; flagged concerns L256, L264 | Adopt | The architecture is the spec. The flagged concerns are the findings in plan-review.md, ranked, with the blockers separated | plan-review.md | Every requirement row of architecture § 2 maps to at least one acceptance check or a named evidence item (traceability table in implementation-plan.md) | The architecture's requirements and acceptance tables are fixed; findings can define evidence but cannot rewrite rows |
| M-03 | **An explicit plan before building**: files that change, order of work, risks, proof; good enough that someone who never saw the conversation could implement from it | Plan mode, L321–374; steps L336–341; example L349–368 | Adopt | implementation-plan.md gives the order, the files per step, the risks and, per acceptance check, how it is run and what evidence it leaves. During the build each sub-issue starts from a short plan in the issue body | implementation-plan.md; issue bodies after the publication gate | A reader with only the repository can say, for each AC, which script runs and which file proves it | Written before any spike; several steps are conditional on spike results and say so |
| M-04 | **The committed artifact is the audit trail**: who asked, what was produced, who approved | Introduction L83–85; Stage 1 governance L196 | Adopt, enforcement deferred | Until the first commit exists, traceability is manual: revisions, the baseline label, decision IDs. After the publication gate the commit history and the issue tree carry it | README baseline table, decision-log.md | Revision labels in each file match the README table; after the first commit, `git log` is the anchor | Manual labels are not immutable (source register, "How revisions work here") |
| M-05 | **One named source of truth per artifact** | Legacy systems, L381–392 | Adopt | core-context § 9 names it per subject. The architecture wins over the rules on conflict | core-context.md § 9 | No subject has two sources that disagree without a recorded conflict | One tension is recorded, not resolved: rules that already state unconfirmed proposals as policy (F-15) |
| M-06 | **Shared repository context kept short**: commands, conventions, things the agent gets wrong | CLAUDE.md, L435–519; steps L447–452 | Defer to the scaffold step | There are no commands to document yet. core-context.md is the interim shared context. A root `CLAUDE.md` is created with the scaffold, when `scripts/validate.sh` and the test commands exist | recommendation in plan-review.md; `CLAUDE.md` at scaffold | It exists, is about a page, and lists the gate commands with a healthy output | Creating it now is outside this session's write boundary and would document commands that do not exist |
| M-07 | **Skills are advisory; a policy that must always hold needs something deterministic behind it** | Skills, L520–622; governance L563; hooks L568–577 | Adopt what exists, add nothing now | `.claude/rules/` and the project skills are the advisory layer. The commit hook is the deterministic layer for commit messages. The pre-publication scan is a procedure today, not a hook | none new in this phase; a scan script under `scripts/` is a candidate for the scaffold step | `audit-rules-drift` after the scaffold; the hook's sample payloads (SR-13 "Verified Facts") | The hook runs only in an agent session and does not see squash-merge titles on GitHub (SR-10). No deterministic guard exists yet for secrets or the forbidden name |
| M-08 | **Split work into tasks that touch different files; two or three parallel sessions; the ceiling is what one person can review** | Parallel sessions, L623–710; steps L645–648 | Adopt, with a different isolation | Four Herdr sessions in named tabs. Each has a written packet, one output file, and a completion report. Worktree isolation is replaced by disjoint write paths, because worktrees need a commit and this phase makes none | delegation-manifest.md | The orchestrator checks that each session wrote only its assigned path, and reviews every output before integrating it | Disjoint paths are a convention, not an enforcement. Two writers ran in parallel; the critic and the steward's plan ran after |
| M-09 | **Give the agent a feedback loop**: one command per check, a quantified target, a failing test first for a bug, and protect the check from being weakened | Feedback loop, L711–796; steps L728–735 | Adopt, split in two layers | Static layer: one script (`scripts/validate.sh`) fixed at scaffold. Lab layer: one script per acceptance check with a final PASS or FAIL line (SR-08 conventions). AC-05 and AC-07 are load-bearing and may not be weakened | implementation-plan.md per-AC section; test scripts at build time | Each test script exits non-zero on failure; a negative test also shows the allowed path working | The lab layer cannot run in CI. Until the spike, several checks have unknown mechanics |
| M-10 | **Continuous evals in CI on agent configuration changes** | Evals, L797–891; steps L814–818 | Not applicable | The playbook's evals measure an agent's behaviour over 20–50 recorded tasks. This repository has no such task history and its deliverable is not agent behaviour | — | — | Revisit only if the agent tooling itself becomes a deliverable |
| M-11 | **Separation of duties: the agent that wrote the work cannot approve it; approval comes from a human** | PR review governance L934; approval hooks L979–1132 (L994–997) | Adopt | Only the owner approves (D-09). The critic session reviews the writers' drafts and the orchestrator's scores; the orchestrator reviews the critic and the steward's plan. No session is the sole reviewer of its own output | decision-log.md § 5; plan-review.md independent-review section; delegation-manifest.md | § 5 of the decision log holds only owner lines; every delegated output has a recorded reviewer other than its author | Branch protection cannot enforce this before a remote exists; with a single owner, a required approving review would block every PR (SR-11 § 2) |
| M-12 | **AI in the PR review loop, with a written review policy** | PR review, L892–978 | Defer | Useful once PRs exist. The PR template carries the gate checklist; a review policy file is not proposed for the first release | PR template in the steward's repo-design PR | — | No remote yet |
| M-13 | **Deployment powers are an allowlist; rollback is the most rehearsed path** | CI/CD, L1133–1215; steps L1150–1154 | Adopt the rollback idea, reject pipeline deployment | CI never deploys: a hosted runner must not reach the private lab (SR-11 § 4). The rehearsed way back for the host is `rpm-ostree rollback` (D-25); for the VM it is the rebuild (AC-01) | implementation-plan.md: rebuild and rollback steps | AC-01 run log; a rollback trial recorded if the OPTIONAL update tier is delivered | The update trial is OPTIONAL tier and may not be delivered |
| M-14 | **Close the loop on production metrics** | Metrics, L1216–1315 | Not applicable as a loop | No production service and no on-call. The nearest equivalent is the required monitoring: Checkmk alerts when a service stops (AC-08) | — | AC-08 | A lab, not a production system |

*Note of 2026-11-16 (DOC-1).* Row M-06 defers a root `CLAUDE.md` to the scaffold step, and item 3 below repeats it. A root `CLAUDE.md` and a root `AGENTS.md` exist since 2026-11-16, added outside this package ([source-register.md](source-register.md) SR-28, SR-29). The deferral stands for what only the scaffold can supply, the gate commands and their healthy output; `AGENTS.md` says it is updated in the same change in which `scripts/validate.sh` lands. The row is kept as written.

## Workflow that follows

1. **Now:** the owner reviews this package. Corrections come back as changes to the core documents; approval is a dated line in the decision log (M-01, M-02, M-11).
2. **Publication gate:** the steward shows the scan and the issue tree; after the go-ahead it creates the repository, the first commit and the tree (M-04).
3. **Implementation gate:** after the approval line, the spike, then the scaffold with the one-command static gate and the root `CLAUDE.md` (M-06, M-09).
4. **Each sub-issue:** short plan in the issue → branch → change → static gate → acceptance script on the lab → evidence file → PR (M-03, M-09).
5. **Release gate:** AC-01 … AC-09 passed with evidence since the last relevant change (SR-06).
