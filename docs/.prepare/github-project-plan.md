# GitHub Project Plan — CoreOS Platform Lab

| Field | Value |
|---|---|
| Document ID | PREP-08 |
| Title | GitHub Project Plan |
| Revision | r9 |
| Status | ready-for-human-review |
| Owner | github-steward (author); reviewer: orchestrator session; approver: repository owner |
| Last updated | 2026-11-16 |
| Core-context revision used | r2 (`docs-baseline-r2`) |
| Dependencies | [implementation-plan.md](implementation-plan.md) r1, [plan-review.md](plan-review.md) r2, [decision-log.md](decision-log.md) r3, [open-questions.md](open-questions.md) r3, [core-context.md](core-context.md) r2, [methodology-adaptation.md](methodology-adaptation.md) r1, [docs/architecture.md](../architecture.md) § 2 and § 10, `.claude/agents/github-steward.md` and `.agents/plans/github-bootstrap-mission.md` as revised on 2026-11-14 (decision-log § 4 rows 19–25); for r5: [decision-log.md](decision-log.md) r6, row D-48, and [implementation-plan.md](implementation-plan.md) r2, § 3 rule 5; for r6: [open-questions.md](open-questions.md) r5 (OQ-21, OQ-22, OQ-34, OQ-35), [readiness-report.md](readiness-report.md) r4 (§ 6, § 10c), the root `AGENTS.md` and `CLAUDE.md`, and the working-tree state observed on 2026-11-16 (baseline `docs-baseline-r7` per the [index](README.md); the index and [core-context.md](core-context.md) were not re-read in full). Written against implementation-plan r2 and readiness-report r4; other sessions changed [implementation-plan.md](implementation-plan.md) (now r3), the readiness report, the index and four more files of `docs/.prepare/` while r6 was being written, and those changes were not re-read; for r8: [decision-log.md](decision-log.md) r7, row D-49, and the working-tree state reported by the orchestrator session on 2026-11-16 (08:07–08:13 CET); for r9: [decision-log.md](decision-log.md) r8 (rows D-50 … D-53 and the subsection "Proposals of § 3 approved by the owner on 2026-11-16"), the owner's answers to items 2 to 6 of § 21.8 as carried by that revision, and read-only checks of the installed `gh` and of github.com on 2026-11-16 (§ 15) |
| Change summary | r1: first draft of the repository settings, labels, board, milestones, issue tree and the Stage 2 bootstrap sequence. r2: reviewed by the orchestrator on 2026-11-14, accepted with three notes. r3: conditional sub-issues S0.C1 and S0.C2 dropped after the owner settled D-44 and D-45; made at the owner's relayed request and not re-reviewed. r4: S2.2 split into S2.2 (AC-05) and S2.3 (AC-04) after the owner answered gate item 13 on 2026-11-14; the tree has 26 sub-issues; not re-reviewed. r5 (2026-11-16): S3.1 depends on S2.2 instead of S2.3, after the owner's scheduling decision D-48; the conditions of D-48 are carried as notes and one criterion in S5.3; counts, labels, milestones and statuses unchanged. r6 (2026-11-16, task GH-6, local Stage 1 completion; both gates closed): completeness pass over the whole package (§ 18); one identifier-to-GitHub-object mapping table (§ 19); a dependency check with its method (§ 20); the outstanding publication decisions with options and one recommendation each, including whether the Proxmox lab-agent workstream is published (§ 21); a publication-hygiene section that separates a preliminary scan, the files changed since earlier scans and the final Stage 2 scan, and claims no readiness (§ 22). Edits to existing sections, all listed in § 16: the status workflow (§ 5), milestone scope (§ 6), a conditional sub-issue S0.C4 (§ 7), the criteria of S0.1 and S1.2 because `AGENTS.md` and `CLAUDE.md` now exist at the root, explicit `Depends on` lines for S0.3 … S0.7, S4.1 and S4.2, **two added dependency edges, S5.3 depends on S2.3 and S4.2 depends on S4.1** (§ 20), two steps in § 12, and open points 10 … 15 in § 15. Counts of issues, labels, milestones and the statuses at creation are unchanged. Status set to `draft`: r3, r4, r5 and r6 have not been reviewed by a session other than the author as a whole (readiness-report § 10b, § 10c). GH-6b (same revision): § 22.1 now records the orchestrator's preliminary scan of 2026-11-16 06:10 as reported by it (154 paths, snapshot aggregate `24e3d0981e7c3d9c`, no real secret found by the patterns, not publication evidence); nothing else changed in substance. r7: corrections after the final review of r6 (task GH-6c): the conditional S0.C4 is not created in the Stage 2 bootstrap, so the tree is 1 + 7 + 26 under every option; S0.1 gains a criterion on dangling references and § 22.3 a twelfth check, with `CLAUDE.md` named wherever `AGENTS.md` is named for rewording, and the options B, C and D named in the S0.1 line; the zero-hit wording of S0.1 and step 1 is aligned with § 22.4; the number pass expands ranges and defines its tokens; § 18 gains two body rules and the board README is composed in Stage 2 and shown to the owner before it is posted; step 0 asks that no `[provisional]` marker remains; two added dependency edges are written as "depends on"; two statements about the workstream's authorization now say that no authorization for it is recorded in this package; § 22.1 states the allow-list behind its mail-address result, as reported by the orchestrator; minor corrections to a stale note on D-47, the list of edits in § 16, the marking of the S4.2 edge and the qualifier on the S5.3 edges, the label rule for the second `area:` label, the handoff-name check of § 22.3 and decision 7 of § 21.8. Status remains `draft`. r8 (2026-11-16, task GH-C; both gates closed, nothing created on GitHub, no `gh` command run): the owner's answer to § 21.8 item 1 is carried: option C of § 21.4, recorded as D-49 ([decision-log.md](decision-log.md) r7). The lab-administration tooling is excluded from the initial publication; a later inclusion needs a separate owner decision and a separate pull request. Changed: § 21.4 (the answer at its top; the options and the recommendation stay as the record; the consequence box notes that it was carried out), § 21.8 (row 1 answered; rows 2 to 7 open), § 21.3 (the listing after the change: 95 paths, the group is out), § 7 (condition of S0.C4), § 9 (the two S0.1 criteria on the workstream), § 12 (preconditions), § 15 (open points 10 and 11 and the line on S0.C4), § 19 (row S0.C4), § 21.6 (D-20), § 21.7, § 22 (§ 22.2 counts, § 22.3 check 12, § 22.4), § 17 (a paragraph), and the sentences that spoke of the question as open. Issue tree (1 + 7 + 26), labels (35), milestones (6), statuses at creation and the Stage 2 order are unchanged. Publication readiness is still not established. Corrected after an independent review on 2026-11-16 (the pointer and the marker in § 21.4, the note on row C, the count note in § 21.3); the review state is recorded in [readiness-report.md](readiness-report.md) § 10e; a technical review is not an owner approval. Status `ready-for-human-review`. **r9 (2026-11-16, task GH-P; both gates closed, nothing created on GitHub, no git mutation; only read-only `gh` queries were run):** the owner's answers to items 2 to 6 of § 21.8 are carried, as recorded in [decision-log.md](decision-log.md) r8: D-50 (the 28 files and `docs/.prepare/` are in; OQ-35 is not a prerequisite), the approved proposals D-20, D-21, D-22, D-23, D-28 and D-33 (for the tree, subject to D-48), D-51 (open points 1, 2, 3 and 7), D-52 (first-commit identity: option I1; the steward's recommendation I2 was not adopted) and D-53 (licence deferred, L2). Row 7 of § 21.8 (the go-ahead) is open. **Open point 14 (the two added dependency edges) is not decided and is put to the owner with the go-ahead request; open point 4 is not decided; D-35 is not decided; the identity of squash commits is not decided.** Changed: this header, § 2 point 3, § 3 (licence row), § 5 (the views limitation corrected after a read-only check of the GraphQL schema), § 7 (the S0.C3 row), § 9 (two criteria of S0.1; the `Depends on` lines of S5.3 and S4.2, which now say that the edge is proposed and undecided), § 12 (preconditions, step 0, the commit-identity paragraph), § 15 (a dated read-only verification block, one corrected assumption, the Open list), § 16 (a paragraph), § 19 (two cells marked as proposed edges), § 20 (a paragraph on what dropping each point-14 edge would change), § 21 (introduction and a dated note on each of § 21.1, § 21.2, § 21.3, § 21.4, § 21.5, § 21.6, § 21.7, § 21.8) and § 22.2 (one row). The option tables stay as the record of the questions. The tree (1 + 7 + 26), the labels (35), the milestones (6), the statuses at creation and the Stage 2 order are unchanged. Publication readiness is not established. After GH-P2 and GH-P3 the text was corrected on findings of the independent review of this pass; the status was set to `ready-for-human-review` after that review ([readiness-report.md](readiness-report.md) § 10f). |

## 1. What this plan is

A **proposal** for everything the steward would create on github.com after the publication gate. **Nothing in it exists**: no repository, label, milestone, issue, board or pull request has been created, and nothing is built or tested. The orchestrator reviewed it on 2026-11-14 and accepted it for the owner's review with three notes ([§ 16](#16-orchestrator-review-2026-11-14)). It is still a proposal: only the owner approves.

Statement classes follow [core-context.md](core-context.md): unless a line says otherwise, §§ 3–13 are **proposals**. Facts with their evidence, assumptions and open points are separated in § 15.

What Stage 2 needs from this file, in one place (r6): [§ 18](#18-completeness-of-the-stage-1-package) says which parts are complete and which are still proposals; [§ 19](#19-identifier-mapping-to-github-objects) maps every plan identifier to the object Stage 2 creates; [§ 20](#20-dependency-check) shows the dependency check; [§ 21](#21-outstanding-publication-decisions) lists the publication decisions with options and recommendations, ending in the smallest list the owner must answer; [§ 22](#22-publication-hygiene) states what has and has not been scanned. **Nothing here claims that the tree is ready to publish.**

How to read the tree: [§ 7](#7-issue-tree) is the one-screen overview. [§ 9](#9-epics-and-sub-issues) gives each sub-issue its source, dependencies, files and acceptance criteria. [§ 11](#11-what-waits-on-the-owner) lists what waits on the owner, by ID.

## 2. Rules applied in this plan

1. **Hierarchy** (D-23, structural): one umbrella without a milestone; epics with exactly one milestone; sub-issues with their epic's milestone, each sized for one branch and one pull request (`.claude/rules/branch-naming.md`).
2. **Titles** use the commit grammar without the issue suffix; scopes come from the allow-list (D-20, structural). The board `Area` is the first scope of the title.
3. **Structural proposals** D-20, D-21, D-22, D-23 and D-33 are settled for the tree by the owner's go-ahead at the publication gate (D-35). They do not block an issue. If the owner changes one, this plan is changed before anything is created. *Note of 2026-11-16 (r9; D-20 … D-23, D-33, D-35):* the owner approved D-20, D-21, D-22, D-23 and D-33 (for the GitHub work tree, subject to the D-48 exception) by name, in the answer recorded in [decision-log.md](decision-log.md) r8, § 2. They therefore no longer wait for the go-ahead. D-35, the rule that one go-ahead settles them together, was not needed and is **not decided**; the go-ahead itself has not been given.
4. **`status:blocked` at creation** is given only to an issue that waits on the owner: an unanswered question, or a non-structural proposal that one of its acceptance criteria encodes. The issue body names the IDs. An issue that only waits for another issue is `Backlog`, with the order in its `Dependencies`.
5. **The implementation gate is not a label.** Every issue is created while that gate is closed. No sub-issue that produces platform configuration moves to `In Progress` before a dated approval line exists in [decision-log.md](decision-log.md) § 5 (mission § 2.3).
6. **`gate:` labels mark a claim, not a contribution.** A sub-issue carries `gate:ac-NN` only if its pull request is allowed to mark that check passed (the "May claim" column of [implementation-plan.md](implementation-plan.md) § 3). A partial run is named in the body and recorded as partial in the evidence file; it gets no label.
7. **Clarification items**: a docs pull request for a non-private outcome; a checkbox on the epic, with proof `owner answer, <date>`, for a purely lab-private answer.
8. **Authors.** The steward writes `.github/**`, the CI workflow and the release paperwork. Platform configuration, test scripts and evidence are written by an implementing session and run on the lab by the owner. Each sub-issue below names its author class.
9. **No estimates, no due dates** (OQ-01).

## 3. Repository settings

| Setting | Value | How it is set |
|---|---|---|
| Name, visibility | `w7-mgfcode/coreos-platform-lab`, public (D-06) | `gh repo create … --public` without `--source` and without `--push` |
| Default branch | `main`, created by the first push of the bootstrap commit; the local branch is already `main` and unborn | after step 6 of § 12: `gh repo view --json defaultBranchRef` reports `main`; if it does not, stop and ask |
| Description | "Reproducible single-VM container platform on Fedora CoreOS and Proxmox: Docker CE and Compose with Caddy, WordPress, Postfix, Loki, Grafana and Checkmk. Plan and process; not built yet." | `gh repo create --description` |
| Topics | `fedora-coreos`, `proxmox`, `docker`, `docker-compose`, `butane`, `ignition`, `caddy`, `wordpress`, `postfix`, `loki`, `grafana`, `checkmk`, `firewall`, `homelab`, `portfolio` | `gh repo edit --add-topic` |
| Issues on; wiki off; discussions off | — | `gh repo edit --enable-issues --enable-wiki=false --enable-discussions=false` |
| Merge methods | squash only; merge commits and rebase merges off | `gh repo edit --enable-squash-merge --enable-merge-commit=false --enable-rebase-merge=false` |
| Squash commit title and body | `squash_merge_commit_title=PR_TITLE`, `squash_merge_commit_message=BLANK` | `gh api -X PATCH repos/w7-mgfcode/coreos-platform-lab` (the installed `gh` 2.46.0 has no flag for it) |
| Head branches | deleted on merge | `gh repo edit --delete-branch-on-merge` |
| Secret scanning and push protection | both enabled | `gh api -X PATCH …` with `security_and_analysis` |
| Licence | none until the owner chooses (OQ-22). *(r9: the owner deferred it, option L2, D-53 on 2026-11-16: no project `LICENSE` file now; OQ-22 stays open.)* | not set by the steward |
| Branch protection on `main` | not part of the bootstrap. Proposed to the owner after the first CI run exists: require a pull request, require the CI check, linear history, no force-push, no deletion, zero required approvals | owner confirmation first |

**Merges** (D-34, proposed): every merge is proposed to the owner with an explicit subject, `gh pr merge <n> --squash --subject "type(scope): description (#issue)" --body ""`, so that `main` carries exactly one reference, the issue. The steward checks the pull-request title against the grammar before proposing a merge and never merges without the owner's word.

## 4. Labels

One colour per family, a description on every label, created with `gh label create <name> --color <hex> --description <text> --force`. GitHub's default labels are kept. 35 labels:

| Family (colour) | Label | Description |
|---|---|---|
| `type:` (`1D76DB`) | `type:umbrella` | One deliverable outcome; spans milestones and owns the scope |
| | `type:epic` | One delivery surface under the umbrella; carries one milestone |
| | `type:sub-issue` | One branch and one pull request under an epic |
| `area:` (`BFD4F2`) | `area:host` | Butane, Ignition, systemd units, Docker CE install, VM provisioning |
| | `area:compose` | compose.yaml: services, networks, volumes, secrets, image pins |
| | `area:proxy` | Caddyfile: internal TLS, reverse-proxy routes, access log |
| | `area:web` | WordPress and MariaDB, including the mail hand-over in WordPress |
| | `area:mail` | Postfix relay configuration |
| | `area:logs` | Alloy, Loki and Grafana configuration |
| | `area:monitoring` | Checkmk agent, local checks and active checks |
| | `area:firewall` | Host DOCKER-USER rules, Proxmox firewall, network isolation |
| | `area:backup` | Backup, restore and update procedures |
| | `area:tests` | Acceptance and negative checks under tests/ |
| | `area:docs` | docs/, README, CHANGELOG and evidence files |
| | `area:diagrams` | Excalidraw sources, rendered images and generators |
| | `area:ci` | GitHub Actions workflows |
| | `area:repo` | Repository hygiene: .gitignore, .claude/, .agents/, .github/ templates |
| | `area:release` | Version cuts and tags |
| `gate:` (`0E8A16`) | `gate:ac-01` | Claims AC-01 Rebuild: the environment is created on a new VM |
| | `gate:ac-02` | Claims AC-02 HTTPS: correct name and trusted chain, verification on |
| | `gate:ac-03` | Claims AC-03 Certificate lifecycle: automatic renewal in a trial |
| | `gate:ac-04` | Claims AC-04 Mail: a WordPress mail arrives and is traced by queue ID |
| | `gate:ac-05` | Claims AC-05 Relay protection: an unauthorised relay attempt is refused |
| | `gate:ac-06` | Claims AC-06 Log search: an HTTP error and an SMTP event found in Grafana |
| | `gate:ac-07` | Claims AC-07 Firewall: forbidden connections fail from outside and inside |
| | `gate:ac-08` | Claims AC-08 Monitoring: a stopped service alerts, recovery clears it |
| | `gate:ac-09` | Claims AC-09 Restart: services and rules work after VM and Docker restart |
| | `gate:ac-10` | Claims AC-10 Restore (OPTIONAL tier): data restored, CA trust kept |
| `priority:` (`D93F0B`) | `priority:p0` | Blocks the v0.1.0 release gate |
| | `priority:p1` | Needed for a clean delivery; does not block the release gate |
| | `priority:p2` | EXTRA or OPTIONAL tier |
| `tier:` (`5319E7`) | `tier:must-have` | MUST HAVE row of the scope lock, or work a MUST HAVE row needs |
| | `tier:extra` | EXTRA: welcome by the reviewer; built after the mandatory layer |
| | `tier:optional` | OPTIONAL in the brief; never delays a MUST HAVE row |
| `status:` (`B60205`) | `status:blocked` | Waits on a named owner decision, open question or dependency |

The `area:` values are the 15 commit scopes (D-20) and the `gate:` values the ten acceptance checks (D-21). Both become public with the labels.

**How labels are applied** (r6; the rule behind the mapping of § 19):

| Family | Rule | Who sets it |
|---|---|---|
| `type:` | exactly one on every issue | the steward at creation |
| `area:` | one or two: the title's scopes in order, then at most one further area the work touches, as listed in § 7; the first is the board Area. An issue whose title has no scope (S0.1) takes its first `area:` label as the board Area | the steward at creation |
| `gate:` | only on the sub-issue whose pull request may mark that check passed (§ 2 point 6); never on an epic or the umbrella | the steward at creation |
| `priority:` | exactly one; `p0` only for MUST HAVE work that blocks the release gate; EXTRA and OPTIONAL items are `p2` | the steward at creation |
| `tier:` | exactly one | the steward at creation |
| `status:blocked` | present while a named owner decision or question is open (§ 11); removed when every ID in the issue's row is answered | the steward, on the owner's answer |

GitHub's default labels are kept. `bug` is the one the bug-report template pre-applies; the others (`documentation`, `enhancement`, `question`, …) are not used by this tree and are not removed. A colour per family is the proposal; the 35 descriptions above are each under 100 characters.

## 5. Projects v2 board

**`CoreOS Platform Lab Delivery`**, owner `w7-mgfcode`, public, linked to the repository.

| Field | Type | Options |
|---|---|---|
| Status | single select (built-in, options replaced) | `Backlog`, `Ready`, `In Progress`, `In Review`, `Blocked`, `Done` |
| Type | single select | `Umbrella`, `Epic`, `Sub-issue` |
| Area | single select | `Host`, `Compose`, `Proxy`, `Web`, `Mail`, `Logs`, `Monitoring`, `Firewall`, `Backup`, `Tests`, `Docs`, `Diagrams`, `CI`, `Repo`, `Release` |
| Priority | single select | `P0`, `P1`, `P2` |
| Tier | single select | `Must-have`, `Extra`, `Optional` |
| Gate | text | the `gate:` labels of the issue, e.g. `AC-04, AC-05`; empty when the issue claims no check |

Built-in `Milestone`, `Parent issue`, `Sub-issues progress` and `Linked pull requests` are used as they are. No estimate, score or phase field (D-23).

- **Short description:** "Delivery board of CoreOS Platform Lab: milestones, umbrella, epics and sub-issues from the requirement to the evidence."
- **README outline** (the text is composed in Stage 2 from this outline, shown to the owner and scanned before it is posted; it contains only README text): purpose · hierarchy and the milestone rule · what each field means · the status rule of § 2 points 4 and 5 · the close rules (proof on every ticked box; an epic closes after its sub-issues; the umbrella closes last) · "planned is not done".
- **Status at creation:** `Done` for S0.1 once closed; `Ready` for S0.2 (`In Review` once its pull request is open); `In Progress` for U1 and E0 after the bootstrap commit; `Blocked` for every issue marked in § 7; `Backlog` for the rest.
- **Views** [assumption, to verify in Stage 2]: `gh` 2.46.0 has no command for views. *(r9, read-only check of the GraphQL schema on 2026-11-16: the schema has the mutations `createProjectV2View` and `updateProjectV2View`. `createProjectV2View` takes a name, a layout (`TABLE_LAYOUT`, `BOARD_LAYOUT` or `ROADMAP_LAYOUT`) and the visible fields; `updateProjectV2View` also takes a `filter` string. Neither takes a grouping or a sort. No view was created. The default table view is used as created; of the three views below, "Flow" (a board layout) and "Blocked" (a table with a filter) may be creatable through `gh api graphql`, and "Roadmap", which is grouped by `Milestone`, cannot be fully set that way. Stage 2 tries them only where the owner wants them and reports an exact failure; see the Stage 2 package for the calls.)* Three views are proposed for the owner to add in the browser if wanted: "Roadmap" (table grouped by `Milestone`, showing `Parent issue`, `Sub-issues progress`, `Tier`, `Gate`), "Flow" (board by `Status`), "Blocked" (table filtered on `Status: Blocked`).

**Status workflow and manual rollup** (r6; a proposal, the board is set by hand):

| Status | Meaning | Moves there when |
|---|---|---|
| `Backlog` | created, waiting only for other issues | at creation, for an issue with no `status:blocked` label that is not yet startable |
| `Ready` | startable: every dependency closed, no `status:blocked`, and, for an issue that produces platform configuration, a dated approval line in [decision-log.md](decision-log.md) § 5 | the steward, after the merge that closes the last dependency or the owner's answer that removes `status:blocked` |
| `In Progress` | a branch exists | the author of the work; never for platform configuration before the approval line (§ 2 point 5) |
| `In Review` | the pull request is open | the steward, when it is opened or seen |
| `Blocked` | the issue carries `status:blocked`; the two always agree | at creation and whenever the label changes |
| `Done` | the pull request is merged, the issue closed, and every criterion ticked with proof | the steward, in the rollup pass below |

The rollup pass after every merge is the list of § 13: board status to `Done`; the parent's line ticked with the pull request as proof; `Sub-issues progress` checked; the next unblocked sub-issue to `Ready`. Nothing sets these automatically: no workflow is created and no auto-add is relied on.

**Built-in project workflows** [assumption, to verify in Stage 2]: a new Projects v2 board may ship with default workflows (for example, setting `Done` when an issue is closed or a pull request is merged). Whether the installed tooling can list or change them is not known. Stage 2 observes the board after creation, and if a default workflow moves a status, either keeps it where it agrees with the rule above or reports it to the owner; it does not add a workflow of its own (§ 13).

## 6. Milestones

Six milestones, mirroring [architecture § 10](../architecture.md#10-megvalósítás-és-átvételi-ellenőrzés). No due dates. A milestone is closed when its exit is met and every issue in it is closed.

| Milestone | Source | Description text (states the exit) | Plan steps |
|---|---|---|---|
| `M0 - Preparation` | § 10 step 1 | Done when the owner inputs of docs/architecture.md § 10 step 1 are answered or explicitly deferred (Proxmox capacity, DNS, SMTP relay, Checkmk access), the repository is bootstrapped, and the owner's pass over the proposals and the implementation gate are recorded. Planning only: nothing is built here. | D0 |
| `M1 - Host & Firewall` | § 10 step 2 | Done when one Fedora CoreOS VM is built from Butane with Docker CE and Compose, the stack starts at boot, and the host firewall is loaded and shown blocking in a partial negative run (docs/architecture.md § 10 step 2). AC-07 is claimed later, at the release gate. The EXTRA firewall layers are tracked here too; they are built after the release gate and never delay this exit. | D1–D4, D10 |
| `M2 - Web & Mail` | § 10 step 3 | Done when WordPress, MariaDB and Caddy answer over trusted HTTPS, a mail from WordPress is traced by its queue ID (AC-04) and an unauthorised relay attempt is refused (AC-05) (docs/architecture.md § 10 step 3). | D5–D6 |
| `M3 - Logs & Monitoring` | § 10 step 4 | Done when a web error and a mail event are found in Grafana (AC-06), HTTPS is proven for both names (AC-02), the renewal trial is recorded (AC-03) and Checkmk alerts on a stopped service (AC-08) (docs/architecture.md § 10 step 4). | D7–D8 |
| `M4 - Backup, Restore & Update` | § 10 step 5 | OPTIONAL tier. Done when a restore trial with measured times (AC-10) and an update trial are recorded (docs/architecture.md § 10 step 5). Built only after the release gate unless the owner decides otherwise. | D11 |
| `v0.1.0 - Release Gate` | `.claude/rules/versioning.md` | Done when AC-01 … AC-09 have passed on the lab with evidence committed since the last relevant change (acceptance table, docs/architecture.md § 10), CHANGELOG.md has its 0.1.0 section and the tag v0.1.0 is pushed. | D9 |

**What each milestone holds** (r6; derived from § 7, counted by the check of § 20; the umbrella has no milestone):

| Milestone | Epics | Sub-issues | Issues in all | Exit decided by |
|---|---|---|---|---|
| `M0 - Preparation` | E0 | S0.1 … S0.7 (and S0.C3, S0.C4 if created) | 8 | the description above; a conditional sub-issue created later keeps it open until closed or closed as "not planned" |
| `M1 - Host & Firewall` | E1, E6 | S1.1 … S1.5; S6.1, S6.2 | 9 | the MUST HAVE part (E1) as described; E6 is EXTRA, runs after the release gate, and holds the milestone open until it is delivered or closed as "not planned" with a recorded owner decision (§ 14 row 2, § 15 point 2) |
| `M2 - Web & Mail` | E2 | S2.1 … S2.3 | 4 | the description above |
| `M3 - Logs & Monitoring` | E3 | S3.1 … S3.3 | 4 | the description above |
| `M4 - Backup, Restore & Update` | E4 | S4.1, S4.2 | 3 | the description above; closed as "not planned" if the owner drops the tier (OQ-19) |
| `v0.1.0 - Release Gate` | E5 | S5.1 … S5.4 | 5 | the description above |

No due date is set on any milestone (OQ-01). The 34 issues of § 7 are 33 in milestones and the umbrella outside them.

## 7. Issue tree

IDs (`U1`, `E0`, `S1.4`) are plan IDs; GitHub numbers are assigned in Stage 2 and replace them in the issue bodies. Every issue also carries its `type:` label. **B** in the last column means `status:blocked` at creation; the IDs it waits on are in [§ 11](#11-what-waits-on-the-owner).

| ID | Title | Milestone | `area:` | `gate:` | Tier | Pri | Step | Status |
|---|---|---|---|---|---|---|---|---|
| **U1** | `feat(repo): coreos platform lab v0.1.0 — single-vm compose stack with proven acceptance checks` | none | repo | — | must-have | p0 | all | In Progress |
| **E0** | `chore(repo): preparation — owner inputs, repository bootstrap and github scaffold` | M0 | repo, docs | — | must-have | p0 | D0 | In Progress |
| S0.1 | `docs: add architecture, diagrams, preparation package and agent tooling` (issue #1) | M0 | docs, repo | — | must-have | p1 | bootstrap | Done |
| S0.2 | `chore(repo): add issue and pr templates, codeowners and dependabot` | M0 | repo | — | must-have | p1 | bootstrap | Ready |
| S0.3 | `docs(docs): record the proxmox capacity, vm size and provisioning path` | M0 | docs | — | must-have | p0 | D0 | **B** |
| S0.4 | `docs(docs): record the lab test roles and the name resolution scheme` | M0 | docs | — | must-have | p0 | D0 | **B** |
| S0.5 | `docs(docs): record the mail relay and test mailbox decision` | M0 | docs | — | must-have | p0 | D0 | **B** |
| S0.6 | `docs(docs): record the checkmk instance and the monitoring scope` | M0 | docs | — | must-have | p0 | D0 | **B** |
| S0.7 | `docs(docs): record the owner's pass over the proposals and the implementation gate` | M0 | docs | — | must-have | p0 | D0 | **B** |
| **E1** | `feat(host): host and firewall — fcos vm with docker ce, boot-time start and the host firewall` | M1 | host, firewall | — | must-have | p0 | D1–D4 | Backlog |
| S1.1 | `chore(host): answer the spike questions sp-01 to sp-20 on a throwaway vm` | M1 | host, docs | — | must-have | p0 | D1 | **B** |
| S1.2 | `chore(repo): add the platform file layout and the static gate script` | M1 | repo, tests | — | must-have | p0 | D2 | **B** |
| S1.3 | `chore(ci): run the static gates and a pr title check on every pull request` | M1 | ci | — | must-have | p1 | D2 | Backlog |
| S1.4 | `feat(host,firewall): build the fcos vm with docker ce and the host-rule firewall stage` | M1 | host, firewall | — | must-have | p0 | D3 | **B** |
| S1.5 | `feat(firewall,compose): load the docker-user rules in two stages and prove them against a caddy stub` | M1 | firewall, compose | — | must-have | p0 | D4 | **B** |
| **E2** | `feat(web): web and mail — wordpress over trusted https and mail through postfix` | M2 | web, mail | — | must-have | p0 | D5–D6 | Backlog |
| S2.1 | `feat(web,compose): run wordpress and mariadb behind caddy with file-based secrets` | M2 | web, compose | — | must-have | p0 | D5 | **B** |
| S2.2 | `feat(mail,compose): run postfix for the single wordpress client and refuse other clients` | M2 | mail, compose | ac-05 | must-have | p0 | D6 | **B** |
| S2.3 | `feat(mail,web): send wordpress mail through the external relay and trace it by queue id` | M2 | mail, web | ac-04 | must-have | p0 | D6 | **B** |
| **E3** | `feat(logs): logs and monitoring — searchable web and mail events and checkmk alerts` | M3 | logs, monitoring | — | must-have | p0 | D7–D8 | Backlog |
| S3.1 | `feat(logs,proxy): collect web and mail logs in loki and search them in grafana` | M3 | logs, proxy | ac-02, ac-06 | must-have | p0 | D7 | **B** |
| S3.2 | `test(tests): prove automatic certificate renewal in a controlled trial` | M3 | tests, proxy | ac-03 | must-have | p0 | D7 | Backlog |
| S3.3 | `feat(monitoring): alert in checkmk when a service stops and clear on recovery` | M3 | monitoring, host | ac-08 | must-have | p0 | D8 | **B** |
| **E5** | `release(release): v0.1.0 release gate — acceptance in full, rebuild, changelog and tag` | v0.1.0 | release, tests | — | must-have | p0 | D9 | Backlog |
| S5.1 | `test(tests): run the firewall negative tests in full with all services up` | v0.1.0 | tests, firewall | ac-07 | must-have | p0 | D9 | **B** |
| S5.2 | `test(tests): prove services and firewall rules after a docker and a vm restart` | v0.1.0 | tests, host | ac-09 | must-have | p0 | D9 | Backlog |
| S5.3 | `test(tests): rebuild the vm from the repository and run the final acceptance pass` | v0.1.0 | tests, host | ac-01 | must-have | p0 | D9 | **B** |
| S5.4 | `release(repo): cut 0.1.0` | v0.1.0 | repo, release | — | must-have | p0 | D9 | **B** |
| **E6** | `feat(firewall): extra firewall layers — proxmox firewall and docker network isolation` | M1 | firewall | — | extra | p2 | D10 | Backlog |
| S6.1 | `feat(firewall): add the proxmox firewall layer with its own negative tests` | M1 | firewall | — | extra | p2 | D10 | **B** |
| S6.2 | `feat(firewall,compose): prove docker network isolation and limit container egress` | M1 | firewall, compose | — | extra | p2 | D10 | **B** |
| **E4** | `feat(backup): backup, restore and update — optional tier trials` | M4 | backup | — | optional | p2 | D11 | **B** |
| S4.1 | `feat(backup): back up and restore the stack with a measured restore trial` | M4 | backup | ac-10 | optional | p2 | D11 | **B** |
| S4.2 | `feat(backup): add the controlled update procedure with a recorded trial` | M4 | backup | — | optional | p2 | D11 | **B** |

Counts: 1 umbrella, 7 epics, 26 sub-issues. At creation: 1 `Done`, 1 `Ready`, 2 `In Progress`, 8 `Backlog`, 22 `Blocked`. Almost every sub-issue waits on the owner; that is the state [implementation-plan.md](implementation-plan.md) § 2 describes, not an artefact of the labelling.

S0.1 has no scope in its title (the mission fixes the wording; `commit-format.md` allows a scopeless `docs`). Its board Area is `Docs`, its first `area:` label.

**Conditional sub-issues** (S0.C3 since r3; S0.C4 since r6), each created under E0 only if the owner's answer at the publication gate asks for the work after publication instead of before the first commit:

| ID | Title | Created if |
|---|---|---|
| S0.C3 | `docs: add the licence chosen by the owner` | OQ-22 is answered with a licence; the file is the owner's choice, never added on the steward's initiative. *(r9: the owner deferred the licence, D-53, option L2. **S0.C3 is not created now**; it is created only if and when the owner later chooses a licence and asks for it as a pull request. It has no file in the Stage 2 package.)* |
| S0.C4 | `chore(repo): add the lab-access agent tooling after its closeout, review and scan` (r6; the scope is open, § 21.4). **The words "after its closeout, review and scan" are the steward's proposal for the title, not a condition set by the owner**: the owner set no condition for a later inclusion (D-49), and the title is reworded to whatever the owner decides then | **The first half of the condition is met:** the owner chose option C of § 21.4 on 2026-11-16 (D-49). The second half stands: **the owner later asks for the publication pull request. It is not created during the Stage 2 bootstrap, and not before that request**: its scope, tier, files and acceptance criteria depend on the owner's later decision and are written into this plan first. Until then the tree is 1 + 7 + 26. When it is created it sits under E0, `type:sub-issue`, `area:repo`, `priority:p2`, `status:blocked` on the owner's later decision (whether the workstream's own closeout is awaited first is the owner's to say, not assumed here); it may be closed as "not planned". Its `tier:` label is left to the owner's answer: the work is not a row of the scope lock (`product-vision.md`, litmus test question 1), so none of the three tiers fits without a decision. The `repo` scope of `commit-format.md` covers `.claude/`, `.agents/` and `.github/`, not a top-level `lab-agent/`; whether that directory gets a scope is part of the same decision and is not assumed here |

S0.C3 and S0.C4 are not part of the 26 and are not counted in § 7 or in the milestone table of § 6 unless created.

**Split in r4.** The owner answered gate item 13 on 2026-11-14, relayed by the orchestrating side: S2.2 is split in two, so that AC-05 is not held back by OQ-04. S2.2 keeps its ID with a narrower scope and claims AC-05; S2.3 is new and claims AC-04. Both belong to step D6. The record of that answer in [decision-log.md](decision-log.md) is the orchestrator's to write. *Note of r7: recorded since as D-47 (decision-log r5, 2026-11-16), as a relayed answer recorded after the fact and not confirmed anew.*

**Order in r5.** By the owner's decision D-48 of 2026-11-16, S3.1 follows S2.2 and no longer waits for S2.3 (§ 9). The table above does not change: same issues, labels, milestones and statuses at creation. S2.3 still precedes the release (§ 11).

Dropped in r3, IDs not reused: **S0.C1** (regenerate diagrams 01–04) and **S0.C2** (remove tooling that does not fit). The owner had both fixed before publication, so no follow-up work is left to track: the diagrams were regenerated with current text (D-44; CQ-07, formerly OQ-23), and the generic and third-party tooling is excluded through `.gitignore` and kept on disk (D-45; CQ-08, formerly OQ-17).

## 8. Umbrella U1

`feat(repo): coreos platform lab v0.1.0 — single-vm compose stack with proven acceptance checks` · `type:umbrella`, `area:repo`, `tier:must-have`, `priority:p0` · no milestone.

- **Summary:** the repository holds a plan and no platform: no Butane file, no Compose file, no test, no evidence (core-context § 5). The umbrella delivers the single-VM stack of [architecture § 1](../architecture.md) and proves each requirement on the lab.
- **Approach:** the refined order D0 … D11 of [implementation-plan.md](implementation-plan.md) § 3 (D-33): owner inputs, spike, scaffold, host and firewall against a stub, web, mail, logs, monitoring (the logs step may follow the first half of the mail step, D-48), then the full firewall run, restart, rebuild and release. Every check leaves an evidence file.
- **Decomposition:** E0 … E3 and E5 (MUST HAVE), E6 (EXTRA), E4 (OPTIONAL), each a native sub-issue of U1.
- **Out of scope**, from the EXCLUDED rows of the scope lock (`.claude/rules/product-vision.md`):
  - Docker Swarm or any multi-node cluster — rejected by the reviewer (D-01).
  - The Moby engine as the Docker runtime — the brief asks for Docker CE (D-02).
  - Kubernetes, high availability, multi-host storage — outside a single-VM homework.
  - Public internet exposure, public ACME certificates — internal lab only.
  - Also not opened as work: a configuration-management layer, WordPress content work beyond the demo, operating the Checkmk server (negative guardrails).
- **Success criteria** (the release gate, D-22):
  - [ ] AC-01 Rebuild · [ ] AC-02 HTTPS · [ ] AC-03 Certificate lifecycle · [ ] AC-04 Mail · [ ] AC-05 Relay protection · [ ] AC-06 Log search · [ ] AC-07 Firewall · [ ] AC-08 Monitoring · [ ] AC-09 Restart — each ticked only with its evidence file linked.
  - [ ] Every MUST HAVE requirement row of architecture § 2 has its proof linked, as mapped in implementation-plan § 6: the Docker CE proof block inside AC-01, EV-WEB for the web service. *(Proposed addition; it does not change which checks gate the release.)*
  - [ ] `v0.1.0` is tagged after the owner's word.
  - [ ] E0 … E3 and E5 are closed; E4 and E6 are closed as completed, or as "not planned" with a recorded owner decision.
- **Risks:** nearly every step waits on owner inputs (§ 11) · several mechanisms are unverified until the spike (assumptions A-02 … A-04, A-09 … A-14) · two MUST HAVE checks depend on outside systems (OQ-03, OQ-04) · overridden base packages can block a Fedora major upgrade (architecture § 2) · rollup on the board is manual and can drift, which the audit catches.
- **Tracking:** the board of § 5; milestones of § 6; close rules of the agent definition.

**Close rule for the umbrella** [proposal]: `v0.1.0` can be tagged while E6 and E4 are still open, because D10 and D11 start after the gate (implementation-plan § 3 rule 1). U1 then stays open until the owner has either had those tiers delivered or decided to drop them. A separate umbrella for the later tiers is the alternative; the mission asks for one umbrella.

## 9. Epics and sub-issues

Per sub-issue: **Source** (implementation-plan step and architecture section), **Author**, **Depends on**, **Files** (planned paths; names not fixed by D-05 are fixed by S1.2), and acceptance criteria that a command, a test script or an evidence file can verify. Blocked-on IDs are in § 11. Nothing below has been built or run.

### E0 — Preparation (`M0 - Preparation`, D0)

- **Purpose:** collect the owner inputs of architecture § 10 step 1, bootstrap the repository, and record the two things the build waits for: the owner's pass over the proposals and the implementation gate.
- **Epic criteria:**
  - [ ] S0.1 … S0.7 closed.
  - [ ] Lab-private answers, each with proof `owner answer, <date>` and no value written anywhere on GitHub: the lab addresses for every test role are in the untracked variables file (OQ-06) · the read-only auditor token exists outside the repository (OQ-02) · relay credentials and the test mailbox are at hand outside the repository (OQ-04) · Checkmk access is at hand (OQ-03).
  - [ ] OQ-01 (deadline) and OQ-24 (how the reviewer evaluates) are answered or explicitly deferred.
- **Out of scope:** any platform configuration; any contact with the lab.
- **Validation path:** `gh issue list --milestone "M0 - Preparation" --state open` returns nothing · `grep -n 'Approved by owner' docs/.prepare/decision-log.md`.

**S0.1 — bootstrap commit (issue #1).** Source: mission § 2.1; D-28; no implementation-plan step — "repo bootstrapped" is part of the M0 exit beside architecture § 10 step 1. Author: steward. Depends on: the publication gate. Files: everything the pre-publication scan clears.
- [ ] The commit contains `README.md`, the root `AGENTS.md` and `CLAUDE.md` (both exist since 2026-11-16 and were not in the r5 list), `.gitignore`, `docs/architecture.md`, `docs/alternatives/swarm.md`, `docs/.prepare/**`, `diagrams/**`, and the parts of `.agents/` and `.claude/` that `.gitignore` lets through, which include the 26 command files and 2 agent definitions that D-45 does not name *(r9: kept, D-50)* — `git show --stat --name-only <sha>`.
- [ ] The list of paths in the commit equals the frozen manifest of the final scan (§ 22.3) — path for path, and each blob equal to the hash recorded in the manifest (`git ls-tree -r --name-only <sha>` against the manifest).
- [ ] It does not contain `HANDOFF.md`, `.handoffs/`, `.claude/settings.local.json`, any `*.ign`, a file over 5 MB, a project `LICENSE` or `COPYING` file at the repository root *(r9: no project licence is added now, D-53; third-party licence and attribution files, if any, stay)*, or any path the `.gitignore` block for generic tooling excludes (D-45) — `git ls-tree -r --name-only <sha>` filtered for those names returns nothing.
- [ ] The Proxmox lab-agent workstream is excluded from the initial publication (owner's answer, option C of § 21.4, D-49): the commit holds none of `lab-agent/`, `.mcp.json`, `.claude/agents/pve-lab.md`, `.claude/hooks/pve-guard.py`, `.agents/plans/proxmox-admin-agent-plan.md` and `.agents/plans/proxmox-admin-agent-governance.diff` — a filtered `git ls-tree -r --name-only <sha>` returns nothing.
- [ ] No tracked file calls or requires a path that is not in the commit. Every `hooks` command of `.claude/settings.json` resolves to a file in `git ls-tree -r --name-only <sha>`; that file holds no `mcp__pve__*` entry and no `Read(~/…)` deny entry; `AGENTS.md` and `CLAUDE.md` **name no path that is absent from the commit**. They keep a general safety instruction about local, untracked lab tooling, which is intended and is not a dangling reference.
- [ ] It contains no platform configuration: no `butane/`, `compose.yaml`, `Caddyfile`, `firewall/`, `scripts/`, `tests/`.
- [ ] The pre-publication scan of § 22.3 ran on the frozen manifest immediately before the commit with zero hits, or with every hit listed by file and line, explained, and accepted by the owner in writing (run log with the manifest hash).
- [ ] The subject is exactly `docs: add architecture, diagrams, preparation package and agent tooling (#1)` and the message has no trailer — `git log -1 --format=%B <sha>`.

**S0.2 — GitHub scaffold.** Source: mission § 2.4; agent definition § 2; no implementation-plan step — part of the same M0 exit as S0.1. Author: steward. Depends on: S0.1. Files: `.github/ISSUE_TEMPLATE/umbrella.md`, `epic.md`, `sub-issue.md`, `bug_report.md`, `config.yml`; `.github/PULL_REQUEST_TEMPLATE.md`; `.github/CODEOWNERS`; `.github/dependabot.yml`. The pull request is opened and **not merged** in Stage 2.
- [ ] The four templates and `config.yml` exist; `blank_issues_enabled: false`.
- [ ] Each hierarchy template pre-applies its `type:` label and carries the section list of the agent definition ("Issue body templates"); they are Markdown, modelled on the `cvforge-ai` issue forms.
- [ ] The pull-request template has: summary, `Closes #`, static gates, acceptance checks touched with evidence links, checks to re-run after this change, vision check, security check, and the title grammar.
- [ ] `CODEOWNERS` is the single rule `* @w7-mgfcode`.
- [ ] `dependabot.yml` lists only `github-actions`, with commit prefix `chore(ci)`.
- [ ] The diff has no file under `.github/workflows/` — `git diff --name-only origin/main...`.
- [ ] The pull-request title follows `type(scope): description (#issue)` and its body has no AI attribution line.

**S0.3 — Proxmox capacity, VM size, provisioning path.** Source: D0; architecture § 3; OQ-02, OQ-05; R-02. Author: the owner, or a session the owner asks. Depends on: none (it waits on the owner's answers, § 11). Files: `docs/.prepare/open-questions.md`, `docs/.prepare/decision-log.md`.
- [ ] OQ-02 is closed with the Proxmox VE major version, the VM size (CPU, memory, disk) and whether a second VM fits beside the first for AC-01 — or the deferral and its consequence are recorded.
- [ ] OQ-05 is closed with who runs the provisioning procedure and with which privilege, and whether the agent token stays read-only.
- [ ] The diff holds no host name, address, storage name or token (pre-push scan).

**S0.4 — test roles and name resolution.** Source: D0; architecture § 5, § 6; OQ-06, OQ-28; R-04; F-27. Author and files as S0.3. Depends on: none.
- [ ] The variable names for each test role are recorded — client network, admin source, Checkmk source, a forbidden source that can reach the VM, an optional second forbidden source — with placeholders from the documentation ranges only.
- [ ] The role of the machine that runs the client-role tests is recorded.
- [ ] How `app.corelab.test` and `logs.corelab.test` resolve is recorded: DNS or hosts entries.
- [ ] OQ-28 is answered: the Checkmk source lies in the client network, or the owner amends the rule line.

**S0.5 — mail relay and test mailbox.** Source: D0; architecture § 7; OQ-04, OQ-31; R-06. Author and files as S0.3. Depends on: none.
- [ ] It is recorded whether an authenticated relay on TCP 587 and a test mailbox are available, without any account, address or host name.
- [ ] If not: the fallback and what it proves are written down, and OQ-31 is answered (does an in-lab delivery count as AC-04).

**S0.6 — Checkmk instance and monitoring scope.** Source: D0; architecture § 7; OQ-03, OQ-30, OQ-32; R-06. Author and files as S0.3. Depends on: none.
- [ ] It is recorded whether an existing or a test instance is used, its version line, and whether the owner can change its trust store and checks.
- [ ] OQ-30 is answered: the release needs agent evidence, or the active check is enough.
- [ ] OQ-32 is answered: what "alert" must show in the evidence.

**S0.7 — owner's pass and the implementation gate.** Source: D0; OQ-07; R-14; D-09. Author: the owner, or a session at the owner's explicit request; never the steward. Depends on: none. Files: `docs/.prepare/decision-log.md`, `docs/.prepare/open-questions.md`.
- [ ] Every row of decision-log § 3 that the publication gate did not settle has a recorded status: confirmed, amended, rejected, or deferred with its consequence.
- [ ] OQ-12, OQ-19, OQ-26, OQ-27, OQ-29, OQ-33 and OQ-34 are answered or deferred with their consequence.
- [ ] decision-log § 5 holds a dated "Approved by owner" line that the owner wrote or dictated — `grep -n 'Approved by owner' docs/.prepare/decision-log.md`.
- [ ] A comment on this issue lists the issues whose `status:blocked` was removed because all their named IDs were answered.

### E1 — Host and firewall (`M1 - Host & Firewall`, D1–D4)

- **Purpose:** a VM that is built from the repository, runs Docker CE, starts the stack at boot and has the mandatory firewall layer loaded before any port is published (requirement rows 1, 2 and 9; D-01 … D-03).
- **Epic criteria:**
  - [ ] S1.1 … S1.5 closed.
  - [ ] The partial firewall run is recorded as partial; AC-07 and AC-09 are still marked "not run".
  - [ ] Branch protection on `main` was proposed to the owner after the first CI run, and the owner's answer is recorded here.
- **Out of scope:** the EXTRA layers (E6); any service other than the Caddy stub.
- **Validation path:** `scripts/validate.sh` · `gh pr checks <n>` · the commands named in S1.4 and S1.5.

**S1.1 — spike.** Source: D1, implementation-plan § 4; architecture § 10 step 2; R-08, R-20. Author: implementing session; the owner runs the lab part. Depends on: S0.3, S0.4, S0.7. Files: the pinned Butane render command (tracked; its home under `scripts/` is fixed by S1.2), `docs/spike-notes.md` (proposed path, outside `docs/evidence/`). The throwaway Butane file stays untracked.
- [ ] The Butane render command names a tool image pinned by version or digest and renders the minimal file with `--strict` and no warnings (command and output in the notes).
- [ ] Each of SP-01 … SP-20 has the command that was run, the answer, and the decision it leads to.
- [ ] The log driver and any SELinux daemon setting are derived from SP-11 and SP-15 and stated, because S1.4 needs them first.
- [ ] The notes say they are working notes, not acceptance evidence; nothing is added under `docs/evidence/`.
- [ ] The notes record that the spike VM was destroyed.
- [ ] No lab address, host name, key or rendered `*.ign` is in the diff.

**S1.2 — platform scaffold.** Source: D2; S1 § 7.2; R-17, R-21; D-05. Author: implementing session. Depends on: S1.1 (order of D-33; nothing in the scaffold depends on a spike answer), S0.7. Files: the D-05 layout with minimal `butane/app-01.bu`, `compose.yaml`, `Caddyfile`; `firewall/`; `scripts/validate.sh`; `tests/`; `docs/evidence/` with its index and the evidence template; the example variables file and the secrets example file (names and placeholders only); the root `AGENTS.md` and `CLAUDE.md`, which exist since 2026-11-16 and are **updated** here, not created (r6; implementation-plan r3 records this in a dated note under its § 3 table, DOC-1, which appeared while r6 was being written; the D2 cell and R-21 still say "a root `CLAUDE.md`", § 21.7); the gate block of `.claude/rules/test-requirements.md`, which that rule requires in the same change and which needs the owner's agreement.
- [ ] `scripts/validate.sh` exits 0 on the scaffold.
- [ ] It exits non-zero on a deliberately broken copy of each input — Butane, Compose, Caddyfile, a shell script; the four outputs are in the pull-request description.
- [ ] Every tool runs from an image pinned by version or digest; no `:latest` and no untagged image in the script.
- [ ] The script fails when a file under `tests/` or `scripts/` contains an option that disables certificate verification (S2 § 10.0).
- [ ] `git ls-files` shows no `*.ign` and no secrets file; the example files hold names and placeholders only.
- [ ] The sections "Build & Test Commands" and "Validation Gates" of the root `AGENTS.md`, which say that the scaffold makes `scripts/validate.sh` the gate and that the section is then updated in the same change, name that script and its invocation; root `CLAUDE.md` stays at or under 150 lines and lists the gate commands — `wc -l CLAUDE.md`, `grep -n 'validate.sh' AGENTS.md CLAUDE.md`. *(r6: replaces "Root `CLAUDE.md` exists, is about a page, and lists the gate commands", which no longer describes a creation.)*
- [ ] The gate block in the test rule matches the script; OQ-18 is closed with the observed result.

**S1.3 — CI workflow.** Source: D2 (it runs the script D2 creates); architecture § 10 step 2; agent definition § 4. Author: steward. Depends on: S1.2. Files: `.github/workflows/ci.yml`.
- [ ] Triggers are `pull_request` and `push` to `main` only.
- [ ] Top-level `permissions: contents: read`; `grep -c 'secrets\.' .github/workflows/ci.yml` returns 0.
- [ ] Every `uses:` is pinned by a 40-character commit SHA.
- [ ] The gate job calls `scripts/validate.sh` and nothing that needs the lab; there is no deployment step and no self-hosted runner.
- [ ] The title job accepts every "Good" example and rejects every "Bad" example of `.claude/rules/commit-format.md` (output in the pull-request description).
- [ ] The workflow's own run on this pull request is green — `gh pr checks <n>`.

**S1.4 — host.** Source: D3; S1 § 2–3, § 5; architecture § 2 rows 1–2, § 3; R-02, R-09, R-20; F-22. Author: implementing session; the owner builds the VM. Depends on: S1.1, S1.2, S0.3, S0.4. Files: `butane/app-01.bu`; the provisioning script under `scripts/`; the host-rule stage under `firewall/`; the version list and the install documentation under `docs/`; the example variables file. The install documentation is the first part of the deploy runbook, and this issue owns it.
- [ ] `scripts/validate.sh` passes.
- [ ] The tracked Butane file holds no secret and no lab-private value; `git ls-files '*.ign'` is empty.
- [ ] Docker's repository definition ships in Butane; no unit downloads a repository definition or pipes a download into a shell (`grep` over `butane/`).
- [ ] The owner built the VM from the repository by the documented procedure; the run log is kept as raw material for AC-01.
- [ ] The Docker CE proof block is captured — `rpm -q docker-ce`, `rpm-ostree status`, `docker version`, `docker compose version`, and the Moby package absent — as a dated section marked partial; AC-01 stays "not run".
- [ ] After a second reboot the install unit is skipped and Docker is running (command output recorded).
- [ ] The host's SELinux mode and the daemon's security options are recorded.
- [ ] From the first boot, TCP 22 answers from the admin role and not from the forbidden role (recorded as partial).
- [ ] The version list names the FCOS stream, version and checksum and the installed Docker CE and Compose versions.
- [ ] The update window in Butane equals the owner's answer to OQ-12.
- [ ] The install documentation names every privileged step and who runs it.

**S1.5 — host firewall against a stub.** Source: D4; S2 § 3; architecture § 6; R-03; F-03, F-13. Author: implementing session; the owner runs the lab part. Depends on: S1.4. Files: `firewall/**`; the firewall and stack units in `butane/app-01.bu`; `compose.yaml` and `Caddyfile` (Caddy alone, `tls internal`, a static response); `tests/firewall-negative-external.sh`; `tests/proxy-https.sh` (first form); a dated partial section of `docs/evidence/ac-07-firewall.md`.
- [ ] `scripts/validate.sh` passes.
- [ ] `docker compose config` shows exactly one published port, TCP 443 on Caddy.
- [ ] The rules for the published port sit in `DOCKER-USER` and match the original destination — `iptables -S DOCKER-USER` output recorded.
- [ ] The stack unit requires the firewall unit; with a lab variable unset the firewall unit fails and the stack does not start (output of a deliberate trial).
- [ ] Partial run: for N-E2, N-E3, N-E4, N-E6 and N-E14 the allowed control succeeds first and the forbidden attempt fails, in the same run.
- [ ] The same holds after a Docker restart and after a reboot.
- [ ] IPv6 follows the SP-10 answer: not in use and enforced, with the `ip6tables -S` output, or rule parity.
- [ ] The result is a dated section marked **partial** in `docs/evidence/ac-07-firewall.md`; AC-07 and AC-09 stay "not run".
- [ ] Lab values appear only as variable names in tracked files and evidence.

### E2 — Web and mail (`M2 - Web & Mail`, D5–D6)

- **Purpose:** the demo workload over trusted HTTPS, and mail from WordPress through a relay that refuses every other client (requirement rows 3–6).
- **Epic criteria:** [ ] S2.1 … S2.3 closed · [ ] EV-WEB and the first EV-SEC section exist · [ ] AC-04 and AC-05 are marked passed with their evidence linked · [ ] AC-02 is still marked partial.
- **Out of scope:** WordPress themes, content and plugins beyond what mail and the demo need; a published SMTP or database port.
- **Validation path:** `scripts/validate.sh` · `tests/web-content-upload.sh` · `tests/secrets-hygiene.sh` · `tests/mail-send-trace.sh` · `tests/mail-relay-refusal.sh`.

**S2.1 — web with file-based secrets.** Source: D5; S1 § 4; S2 § 7; architecture § 4, § 5, § 8; R-18; F-20, F-23. Author: implementing session; the owner runs the lab part. Depends on: S1.5. Files: `compose.yaml`; `Caddyfile`; the WordPress files and the initialisation script; the secrets example file and the secrets channel documentation; the stack unit's secrets condition in `butane/app-01.bu`; `tests/web-content-upload.sh`; `tests/secrets-hygiene.sh`; `docs/evidence/req-web-function.md`; `docs/evidence/req-secrets.md`; a partial section of `docs/evidence/ac-02-https.md`.
- [ ] `scripts/validate.sh` passes; every image is pinned by version or digest and listed in the version list.
- [ ] `tests/secrets-hygiene.sh` ends with PASS and prints names and booleans only → `docs/evidence/req-secrets.md` (EV-SEC, first section).
- [ ] MariaDB has no `ports:` entry in `docker compose config`.
- [ ] `tests/web-content-upload.sh` ends with PASS: a login, a post with a unique token and an upload, both read back over HTTPS verified with the lab root only → `docs/evidence/req-web-function.md` (EV-WEB).
- [ ] The upload is still there after the stack was stopped and started.
- [ ] `tests/proxy-https.sh` for the application name passes with the lab root and fails on verification without it, in the same session; recorded as **partial**, AC-02 stays "not run".
- [ ] The initialisation run is recorded, so a rebuilt stack does not stop at an installation screen.
- [ ] The example file lists every secret name in use; the documentation says there is no encryption at rest.
- [ ] The pull request names the checks to re-run (the partial firewall run of S1.5).

**S2.2 — Postfix for one client, and the refusal.** Source: D6 (first half); S2 § 8.1–8.3, § 8.4 ("AC-05 does not depend on the relay"), § 10.5; S1 § 4 (Postfix row); architecture § 7; R-05, R-11 (the image); F-05, F-11. Author: implementing session; the owner runs the lab part. Depends on: S2.1. Files: the Postfix configuration without the relay hand-over; `compose.yaml` (the Postfix service, its queue volume, the fixed addressing on the mail network); `tests/mail-relay-refusal.sh`; `docs/evidence/ac-05-relay-refusal.md`.
- [ ] `scripts/validate.sh` passes; the Postfix image is pinned, listed, and its choice cites the image's own documentation.
- [ ] Postfix has no `ports:` entry.
- [ ] The trusted client list is the single fixed WordPress address plus loopback (configuration shown in the pull request).
- [ ] `tests/mail-relay-refusal.sh` ends with PASS: the allowed client is queued in the same run; the probe on the mail network gets the banner and then a permanent refusal for an outside recipient, also with the WordPress sender address; nothing is queued for it; a timeout, a refused connection or a temporary reply is a FAIL → `docs/evidence/ac-05-relay-refusal.md` with both transcripts.
- [ ] The script narrows no source and drops no path of S2 § 2 (AC-05 is load-bearing).
- [ ] The evidence says what became of the message the allowed client queued in that run, and the queue listing at the end of the run is in it. *(Proposed addition, not in S2 § 10.5: without a relay hand-over that message cannot be delivered, and it must not be sent later as a stale test message.)*
- [ ] The evidence states that no relay hand-over was configured on that run; AC-04 stays "not run".
- [ ] No mail address, relay name or account is in a tracked file or in the evidence.

**S2.3 — relay hand-over and the WordPress mail path.** Source: D6 (second half); S1 § 6.2; S2 § 8.1 (upstream side), § 8.4, § 10.4; architecture § 7; R-11 (the WordPress mail integration); F-06, F-11. Author: implementing session; the owner runs the lab part. Depends on: S2.2, S0.5. Files: the relay hand-over in the Postfix configuration; the must-use plugin file; `compose.yaml` (the relay credentials secret, the plugin mount); the secrets example file; `tests/mail-send-trace.sh`; `docs/evidence/ac-04-mail.md`; a dated re-run section in `docs/evidence/ac-05-relay-refusal.md`.
- [ ] `scripts/validate.sh` passes; the relay credentials are read from a secret file, and the example file lists the new secret names with placeholders only.
- [ ] `tests/mail-send-trace.sh` ends with PASS: a token new on this run, the queue ID in the Postfix log, the relay's acceptance, and the same queue ID in the received message → `docs/evidence/ac-04-mail.md`, redacted.
- [ ] If only a test receiver exists, the first line of that evidence says the proof covers in-lab delivery only, and AC-04 is marked as OQ-31 decides.
- [ ] The trusted client list is unchanged from S2.2 (configuration shown in the pull request).
- [ ] The pull request names the check to re-run, AC-05: `tests/mail-relay-refusal.sh` ends with PASS again with the relay hand-over in place → a dated section in `docs/evidence/ac-05-relay-refusal.md`. This is a re-run under `.claude/rules/test-requirements.md` ("When a relevant change lands after a check passed"), not a second claim of AC-05.
- [ ] The script narrows no source and drops no path of S2 § 2.
- [ ] No mail address, relay name or account is in a tracked file or in the evidence.

Notes on order (D-48; not acceptance criteria): S3.1 may run before, beside or after this issue. While both are open, `compose.yaml`, `Caddyfile` and the secrets example file have one designated writer at a time; rebasing one branch onto the other does not replace that coordination (`.claude/rules/herdr-orchestration.md`, "Bounded packets and ownership"). This issue is merged and deployed outside the observation window of the renewal trial (S3.2): with the deployment procedure described today its deployment restarts Caddy, and its `compose.yaml` change trips S3.2's merge criterion as that criterion stands. If AC-06 has passed before this pull request merges and the change touches Postfix's image, its log output or the log route, the pull request also names AC-06 for re-run (§ 13).

### E3 — Logs and monitoring (`M3 - Logs & Monitoring`, D7–D8)

- **Purpose:** web and mail events found by a query in Grafana, HTTPS proven for both names, the renewal trial, and an external alert on a stopped service (requirement rows 5, 7 and 8).
- **Epic criteria:** [ ] S3.1 … S3.3 closed · [ ] AC-02, AC-03, AC-06 and AC-08 are marked passed with their evidence linked · [ ] the monitoring row is closed with agent evidence, or the gap against the row is stated here (D-40).
- **Out of scope:** operating the Checkmk server; a Docker socket mount; published ports for Loki, Grafana or Alloy.
- **Dependencies:** E3 starts after S2.2, the first half of D6, and does not wait for S2.3 (D-48, owner, 2026-11-16). This is one exception to the rule of [implementation-plan.md](implementation-plan.md) § 3 that a step's exit is observed before the next step starts; D-33 as a whole stays a proposal. S2.3 still precedes the release (E2, E5). S3.2 and S5.1 get no unconditional dependency on S2.3.
- **Validation path:** `scripts/validate.sh` · `tests/logs-search.sh` · `tests/proxy-https.sh` · `tests/proxy-cert-renewal.sh record` then `compare` · `tests/monitoring-service-restart.sh`.

**S3.1 — logs.** Source: D7; S1 § 6.1; S2 § 9.2, § 10.2, § 10.6; architecture § 4, § 7; R-13; F-08, F-25. Author: implementing session; the owner runs the lab part. Depends on: S2.2, S1.1 (D-48; S2.3 until r4). Files: the Alloy, Loki and Grafana configuration and provisioning; `compose.yaml`; `Caddyfile` (the logs name — the last planned proxy change); the secrets example file; `tests/logs-search.sh`; `docs/evidence/ac-06-log-search.md` and its screenshot; `docs/evidence/ac-02-https.md`.

Prerequisites by kind (D-48; they add no criterion):
- *Local preparation* — the files above and the test script. Like every platform file it waits for the implementation gate (§ 2 point 5), and it needs the spike's answer on the log route (S1.1; OQ-20, D-38).
- *Integration and deployment on the lab* — after S2.2 is integrated; S2.3 is not needed. While S2.3 is open, the shared files have one designated writer at a time (note under S2.3).
- *Running its checks* — AC-06 and AC-02 in full. The SMTP event AC-06 searches for may be the AC-05 refusal from S2.2, as the security draft allows ([s2-security-verification.md](delegation/s2-security-verification.md) § 10.6), or the AC-04 queue ID if S2.3 is already in.
- *Closing the issue, and the release* — the issue closes when its pull request merges with every box below ticked with proof, without S2.3. The release still needs S2.3 (AC-04) and the queue-ID search of the final pass (S5.3).
- [ ] `scripts/validate.sh` passes; images are pinned and listed.
- [ ] Loki, Grafana and Alloy have no `ports:` entry and no container mounts the Docker socket (`docker compose config`).
- [ ] Any SELinux label exception has its justification next to it and cites the SP-15 answer.
- [ ] `tests/logs-search.sh` ends with PASS: an HTTP error line with a unique token and an SMTP event of the same session are returned by an authenticated query over verified HTTPS; a query for a token never sent returns nothing; an unauthenticated query is refused → `docs/evidence/ac-06-log-search.md`, with the screenshot's result repeated as text.
- [ ] The label set is service, host and environment only.
- [ ] The evidence records the rotation and retention settings.
- [ ] `tests/proxy-https.sh` ends with PASS for both names, with the failing counterparts in the same session → `docs/evidence/ac-02-https.md` in full.
- [ ] A section for the Grafana admin secret is added to `docs/evidence/req-secrets.md`.

**S3.2 — certificate renewal trial.** Source: D7, implementation-plan § 5; S2 § 6.3, § 10.3; architecture § 5; F-18. Author: implementing session; the owner runs the lab part. Depends on: S3.1. Files: `tests/proxy-cert-renewal.sh`; `docs/evidence/ac-03-cert-renewal.md`.
- [ ] `record` and `compare` show a new leaf serial with a later expiry under the same root fingerprint, and Caddy's log lines for the renewal lie between the two readings.
- [ ] Caddy's container start time is unchanged and no manual step lies between the readings.
- [ ] No change to `Caddyfile` or `compose.yaml` was merged between the readings (`git log` on both paths).
- [ ] The observed renewal point and the bound of the trial are recorded; an intermediate renewal is stated as not verified.
- [ ] The file ends with PASS, and the trial ended before S5.2 started.

Scheduling note (D-48; no criterion and no dependency on S2.3): the only deployment procedure described today copies the files over SSH and restarts the stack unit, which stops and starts every service, Caddy included (S1 § 2.3 P-03, § 5). A deployment of S2.3 during the trial would therefore restart Caddy, so it is scheduled outside the observation window. The deployment timing follows from that procedure, which restarts Caddy. Independently, while the criterion on `Caddyfile` and `compose.yaml` merges above stands as written, a merge of S2.3 between the readings also invalidates the trial, because S2.3 changes `compose.yaml`; so S2.3 is merged and deployed outside the observation window, or the trial is started again afterwards. This adds no dependency on S2.3, and the criterion itself is not changed here: its rewording is a pending proposal, not decided.

**S3.3 — monitoring.** Source: D8; S1 § 6.3; S2 § 9.3, § 10.8; architecture § 7; R-07; F-07, F-25. Author: implementing session; the owner configures Checkmk and runs the lab part. Depends on: S3.1, S0.6, S1.1. Files: the agent and local-check files; additions to `butane/app-01.bu`; the agent-port rule under `firewall/` if the agent route is chosen; the documentation of the Checkmk-side settings; `tests/monitoring-service-restart.sh`; `docs/evidence/ac-08-monitoring.md` and screenshots.
- [ ] Every Checkmk statement the design relies on cites the Checkmk documentation (closes OQ-25).
- [ ] The active HTTPS check runs with verification on and the lab root in Checkmk's trust store.
- [ ] `tests/monitoring-service-restart.sh` ends with PASS: OK before, critical after WordPress is stopped, OK after it is restored, three timestamps, and the critical output names an HTTP failure → `docs/evidence/ac-08-monitoring.md`, text beside every screenshot.
- [ ] The same file holds the agent evidence — a host resource check and the disk check — or states the gap against the requirement row if the spike ruled the agent out.
- [ ] If an agent port is used, it answers from the Checkmk source only and N-E8 is added to the external firewall test.
- [ ] No container mounts the Docker socket.

### E5 — Release gate (`v0.1.0 - Release Gate`, D9)

- **Purpose:** the full firewall run, the restart checks, the rebuild, and the release (D-22).
- **Epic criteria:**
  - [ ] S5.1 … S5.4 closed.
  - [ ] This table is filled, and no date is older than the last relevant change to the component:

    | Check | Evidence file | Last passed | On VM build |
    |---|---|---|---|
    | AC-01 … AC-09 | `docs/evidence/ac-NN-<slug>.md` | date | repository revision and FCOS version |
- **Out of scope:** AC-10; the EXTRA layers; any release automation.
- **Validation path:** `tests/run-acceptance.sh` · `tests/host-restart.sh docker` · `tests/host-restart.sh vm` · `tests/host-rebuild-verify.sh` · `git describe --tags`.

**S5.1 — firewall in full.** Source: D9; S2 § 2, § 10.7; architecture § 6, § 10; F-13. Author: implementing session; the owner runs the lab part. Depends on: S3.3. Files: `tests/firewall-negative-external.sh`; `tests/firewall-negative-container.sh`; `tests/run-acceptance.sh`; `docs/evidence/ac-07-firewall.md`.
- [ ] The evidence records that all seven services were running.
- [ ] There is one result line per path: N-E2 … N-E14 from every forbidden role the lab has, and N-C7 … N-C10 by container address and by the VM address.
- [ ] Per path, the allowed control succeeds first in the same run; a negative with a failed control is a FAIL.
- [ ] Each block on the published port is attributed by the host's drop counter.
- [ ] No path of S2 § 2 is removed and no source is narrowed (the path list in the script equals the matrix).
- [ ] A role the lab does not have is recorded as "not run".
- [ ] The file ends with PASS.

**S5.2 — restart.** Source: D9; S2 § 10.9; architecture § 10. Author: implementing session; the owner runs the lab part. Depends on: S5.1, S3.2. Files: `tests/host-restart.sh`; `docs/evidence/ac-09-restart.md`; a section added to `docs/evidence/req-web-function.md`.
- [ ] `tests/host-restart.sh docker` and `tests/host-restart.sh vm` each re-run AC-02 and AC-07 in full and end with PASS.
- [ ] The normalised `INPUT`, `DOCKER-USER` and `ip6tables` rule sets are equal before and after each restart.
- [ ] The same root file validates the site, and the EV-WEB token post is still there.
- [ ] The client role sees an outage and a recovery while the forbidden role never gets through.

**S5.3 — rebuild and final acceptance pass.** Source: D9; S1 § 7.4; S2 § 10.1; architecture § 10; R-01; F-12, F-26. Author: implementing session; the owner builds the VM. Depends on: S5.2, S2.3 (r6: made explicit; *r9: a proposed edge, not decided, § 15 point 14*; the final pass needs the AC-04 evidence, and without this edge nothing in the sub-issue graph would order S2.3 before the release, § 20). Files: `tests/host-rebuild-verify.sh`; `docs/evidence/ac-01-rebuild.md`; the version list; re-run sections in the other evidence files.
- [ ] The owner built a new VM from a clean checkout at a recorded commit, following the install documentation only; the run log is in the evidence.
- [ ] `tests/host-rebuild-verify.sh` ends with PASS: the machine was provisioned after the run started; the Docker CE proof block; the Moby package absent; the SELinux mode and the daemon's security options; the install unit ran once; the firewall unit active; seven services running.
- [ ] Every input from outside the repository is listed.
- [ ] Where a previous VM existed, its root certificate fails against the new one.
- [ ] AC-02 and AC-07 end with PASS against the new VM.
- [ ] As OQ-29 decides: every evidence file AC-01 … AC-09 has a PASS section for the VM that carries the release evidence, dated after the last relevant change.
- [ ] The log-search evidence of this pass includes a Grafana query that finds a Postfix queue ID, the search that [architecture § 2](../architecture.md#2-követelmények-és-döntések) names for the searchable-logs row (D-48); an earlier AC-06 pass on the refusal event is not the only log-search evidence at release → a dated section in `docs/evidence/ac-06-log-search.md`.

**S5.4 — release.** Source: D9; architecture § 10 (the acceptance table and the closing paragraph on delivered evidence); `.claude/rules/versioning.md`; agent definition § 5. Author: steward; the owner is asked before the tag. Depends on: S5.3. Files: `CHANGELOG.md`; the status section of `README.md` (Hungarian, D-12).
- [ ] The table in E5 is complete and current (`git log` per component path against the evidence dates).
- [ ] The requirement-row proofs are linked: the Docker CE proof block, EV-WEB, EV-SEC, and the agent evidence as OQ-30 decides.
- [ ] `CHANGELOG.md` has a dated `0.1.0` section with the known gaps, added in one commit `release(repo): cut 0.1.0 (#N)`.
- [ ] The README status section matches the evidence.
- [ ] The owner agreed to the tag; `git describe --tags` returns `v0.1.0`, equal to the changelog heading.
- [ ] `gh release view v0.1.0` succeeds and the `release/v0-1-0` branch is deleted.

### E6 — EXTRA firewall layers (`M1 - Host & Firewall`, D10)

- **Purpose:** the two layers the reviewer welcomed as extras (D-03), each with its own negative tests, attributed to that layer.
- **Epic criteria:** [ ] S6.1 and S6.2 closed, or closed as "not planned" with a recorded owner decision · [ ] the MUST HAVE section of the AC-07 evidence is unchanged · [ ] the checks named for re-run have been re-run.
- **Dependencies:** S5.3 (the gate has passed), unless the owner explicitly decides otherwise (implementation-plan § 3 rule 1).
- **Validation path:** `tests/firewall-negative-external.sh` · `tests/firewall-negative-container.sh`.

**S6.1 — Proxmox firewall.** Source: D10; S2 § 4.1–4.2; architecture § 6. Author: implementing session; the owner applies the rules on the host. Depends on: S5.3. Files: a rule-set example under `firewall/` with placeholder addresses; its documentation; additions to `tests/firewall-negative-external.sh`; a dated EXTRA section of `docs/evidence/ac-07-firewall.md`.
- [ ] Every statement about the Proxmox firewall cites its documentation (no register entry covers it today).
- [ ] The tracked rule set holds placeholder addresses only.
- [ ] The owner applied it; the agent token stayed read-only.
- [ ] Each block is attributed to its layer by counters or the firewall log: the far forbidden source is dropped at Proxmox, the near one still at the host.
- [ ] No layer was disabled for any test.
- [ ] The pull request names the checks to re-run: AC-07, AC-09, and AC-01 if outbound traffic is filtered.

**S6.2 — Docker-network isolation and egress.** Source: D10; S2 § 4.3, § 5; architecture § 6; R-10; F-10, F-21. Author: implementing session; the owner runs the lab part. Depends on: S5.3. Files: `compose.yaml`; the egress rules under `firewall/`; additions to `tests/firewall-negative-container.sh`; a dated EXTRA section of `docs/evidence/ac-07-firewall.md`.
- [ ] N-C11, N-C12 and N-C13 each end with a result line, the control first in the same run.
- [ ] Postfix still reaches the relay on TCP 587 (`tests/mail-send-trace.sh` ends with PASS afterwards).
- [ ] The pull request names the checks to re-run: AC-04, AC-07, AC-09.

### E4 — Backup, restore and update (`M4 - Backup, Restore & Update`, D11)

- **Purpose:** the OPTIONAL operations row of the requirements table. Whether it is delivered at all, and before or after the release, is OQ-19.
- **Epic criteria:** [ ] S4.1 and S4.2 closed, or closed as "not planned" with a recorded owner decision · [ ] AC-10 is marked passed only with `docs/evidence/ac-10-restore.md` linked.
- **Dependencies:** S5.3, unless the owner decides otherwise.
- **Validation path:** `tests/backup-restore.sh`.

**S4.1 — backup and restore.** Source: D11; S1 § 8.1–8.2; S2 § 10.10; architecture § 8. Author: implementing session; the owner runs the lab part. Depends on: S5.3 (the epic rule above: the gate has passed unless the owner decides otherwise). Files: the backup and restore scripts; the procedure documentation; the secrets example file (backup passphrase); `tests/backup-restore.sh`; `docs/evidence/ac-10-restore.md`.
- [ ] The backup is encrypted and leaves the VM; the database part is a consistent dump, not a copy of the live volume.
- [ ] `tests/backup-restore.sh` ends with PASS on a fresh VM: token A and its upload are present, token B written after the backup is absent, and AC-02 passes with the previous root file untouched.
- [ ] The measured restore time and data loss are in `docs/evidence/ac-10-restore.md`.
- [ ] No test message is sent a second time from a restored queue.

**S4.2 — controlled update.** Source: D11; S1 § 8.3; architecture § 9; R-19; F-17. Author: implementing session; the owner runs the lab part. Depends on: S5.3 (as S4.1); S4.1 (r6, the steward's proposal; *r9: not decided, § 15 point 14*: the update trial needs "a backup before", architecture § 9, S1 § 8.3). Files: the update procedure documentation; an optional local check for the update state; `docs/evidence/req-update-trial.md` (EV-UPD).
- [ ] The procedure states the maintenance window, the check before a Fedora major rebase, and `rpm-ostree rollback` as the way back.
- [ ] One trial is recorded in `docs/evidence/req-update-trial.md`: an image pin changed by pull request, a backup before, and the affected checks re-run after.
- [ ] A rollback trial is recorded, or stated as "not run".

## 10. Coverage

| Requirement row (architecture § 2) | Tier | Built in | Proof claimed in |
|---|---|---|---|
| Fedora CoreOS on Proxmox | MUST HAVE | S1.1, S1.4 | S5.3 (AC-01) |
| Docker CE | MUST HAVE | S1.4 | S5.3 (Docker CE proof block in AC-01) |
| Web service | MUST HAVE | S2.1 | S2.1 (EV-WEB), re-read in S5.2 |
| HTTPS reverse proxy | MUST HAVE | S1.5, S2.1, S3.1 | S3.1 (AC-02) |
| Internal CA and automation | MUST HAVE | S1.5 | S3.1 (AC-02), S3.2 (AC-03) |
| SMTP container | MUST HAVE | S2.2, S2.3 | S2.2 (AC-05), S2.3 (AC-04) |
| Searchable logs | MUST HAVE | S3.1 | S3.1 (AC-06); the Postfix queue-ID search in S5.3 (D-48) |
| External monitoring | MUST HAVE | S3.3 | S3.3 (AC-08, with the agent evidence of D-40) |
| Firewall — host layer | MUST HAVE | S1.4, S1.5 | S5.1 (AC-07), S5.2 (AC-09) |
| Firewall — Proxmox layer, network isolation | EXTRA | S6.1, S6.2 | EXTRA sections of the AC-07 evidence |
| Optional operations | OPTIONAL | S4.1, S4.2; secrets from S2.1 | S4.1 (AC-10), S4.2 (EV-UPD), S2.1 (EV-SEC) |

Every check AC-01 … AC-09 is claimed by exactly one sub-issue; AC-10 appears only under E4. No issue exists for an EXCLUDED row. Steps: D0 → E0 · D1–D4 → E1 · D5–D6 → E2 · D7–D8 → E3 · D9 → E5 · D10 → E6 · D11 → E4. Order inside D6–D7 (D-48): S3.1 follows S2.2; S2.3 runs before, beside or after E3 and is done before the release.

## 11. What waits on the owner

An issue is unblocked when every ID in its row is answered; the steward then removes `status:blocked` and sets the board status.

| Issue | Waits on |
|---|---|
| S0.3 | OQ-02, OQ-05 |
| S0.4 | OQ-06, OQ-28 |
| S0.5 | OQ-04, OQ-31 |
| S0.6 | OQ-03, OQ-30, OQ-32 |
| S0.7 | OQ-07 |
| S1.1 | OQ-02, OQ-05, OQ-06 |
| S1.2 | OQ-34 |
| S1.4 | OQ-02, OQ-05, OQ-06, OQ-12, OQ-14, D-24, D-25, D-37, D-38 |
| S1.5 | OQ-06, OQ-27, OQ-28, D-31, D-36, D-37 |
| S2.1 | OQ-16, OQ-26, OQ-27, OQ-33, D-36 |
| S2.2 | OQ-10, OQ-11, D-36 |
| S2.3 | OQ-04, OQ-10, OQ-31 |
| S3.1 | OQ-20, D-38 |
| S3.3 | OQ-03, OQ-25, OQ-28, OQ-30, OQ-32, D-40 |
| S5.1 | OQ-06, D-31 |
| S5.3 | OQ-02, OQ-29, D-32, D-43 |
| S5.4 | OQ-19, OQ-29, OQ-30 |
| S6.1 | D-27; the owner's agreement to a role wider than read-only on Proxmox, or to apply the rules personally (`security-patterns.md`, "Lab access") — no question ID exists for it yet |
| S6.2 | OQ-27, D-27, D-36 |
| E4, S4.1 | OQ-19 |
| S4.2 | OQ-12, OQ-19, D-25 |

Not blocked at creation: U1, S0.1 (done in the bootstrap), S0.2, S1.3, S3.2, S5.2, and the epics E0 … E3, E5, E6.

After the split of r4, OQ-04 and OQ-31 hold only S2.3. S2.2 still waits on OQ-10 (how narrow the trusted list is), OQ-11 (the Postfix image) and D-36 (Postfix's network membership, set when the service is created); S2.3 inherits OQ-11 and D-36 through S2.2 and waits on OQ-10 for the WordPress side of it.

Since r5 (D-48), S3.1 depends on S2.2 and no longer waits on OQ-04, OQ-31 or S0.5 through S2.3. Its own row, OQ-20 and D-38, is unchanged; through S2.2 and S1.1 it still inherits the IDs those issues wait on. **S2.3 still precedes the release**: AC-04 stays mandatory, and the E2 epic criteria (AC-04 marked passed), the E5 table (AC-01 … AC-09), S5.3 (a PASS section in every evidence file AC-01 … AC-09) and S5.4 (the E5 table complete) all require its evidence. S2.3 is no longer an ancestor of S3.1, but it remains one of the release through E2 and E5. Since r6 that is also a dependency line: S5.3 depends on S2.3 (§ 9, § 20). It is the r6 steward's proposal, not part of D-48; D-48 forbids only an unconditional dependency of S3.2 or S5.1 on S2.3, and neither has one.

D-41 and D-42 (the two drafts as the starting design) are named in the bodies of the platform sub-issues as proposed design inputs. They are **not** used as blockers here, because the acceptance criteria above are written at outcome level and hold whichever way the owner amends the design. The orchestrator may prefer to block on them.

## 12. Stage 2 bootstrap sequence

Runs only after the publication gate. Each step first checks whether its object exists, so a re-run creates no duplicate. A failed step stops the sequence; the run log lists every created object with its URL.

**Preconditions.** The owner has given: the go-ahead; agreement to the first-commit exception (D-28); the decision on the commit address (OQ-21); the licence decision (OQ-22); the answer on D-20, D-21, D-22, D-23 and D-33. *(r9: the list above is the r5 form. Status on 2026-11-16: every item except the go-ahead has an owner answer recorded in [decision-log.md](decision-log.md) r8. D-28 is approved as a procedure and is **not yet permission to create a commit or to push**; the commit address is settled by D-52 (option I1); the licence is deferred by D-53 (option L2, no `LICENSE` file); D-20, D-21, D-22, D-23 and D-33 are approved by name. The go-ahead is not given and stays the last precondition. Open point 14 of § 15 still goes to the owner with the go-ahead request.)* The orchestrator has recorded those answers in [decision-log.md](decision-log.md) before the first commit, because the steward does not edit that file. The orchestrator has reviewed this plan. *(r6: the list above is the r5 form. The decisions Stage 2 needs, with the lab-agent question added and the others grouped, are in § 21.8, in the order they must be answered. Step 0 below makes them a precondition.)* *(r8: the lab-agent question, item 1 of § 21.8, is answered: option C, D-49, recorded in [decision-log.md](decision-log.md) r7 on 2026-11-16, which is the decision-log row the r6 note asked for. The tooling is excluded from the initial publication. Items 2 to 7 of § 21.8 are still open and are still preconditions. State at r8; see the r9 note above: items 2 to 6 are answered, item 7, the go-ahead, is open.)* *(r9: where the go-ahead itself is recorded — in the decision log before the first commit, which changes the scanned manifest and requires a new freeze and scan, or by the first pull request after the bootstrap, which leaves the scanned manifest unchanged — is put to the owner with the go-ahead request. The same holds for the owner's answer on open point 14.)*

| # | Step | Check before | Stop if |
|---|---|---|---|
| 0 | **Freeze** (r6): the owner's answers of § 21.8 are in hand; the contents of the bootstrap commit are fixed (§ 21.3, § 21.4); no other session writes in the checkout from here to step 6; `gh auth status` lists `repo`, `project` and `workflow` again (the 2026-11-14 observation is not reused); this plan has been revised to the owner's answers: no `[provisional]` marker and no option wording remains in a criterion *(r9: this revision condition is met for the answers that exist; step 0 itself has not run. Point 14 still stands as proposed, and the go-ahead of item 7 is not given)* | the orchestrator confirms the checkout is quiet; the tool lists no scope missing | a file changes between the scan and step 6 (compared by hash, § 22.3); a scope is missing: report the exact output |
| 1 | Pre-publication scan over `git add -A --dry-run`, as in the agent definition's operating rules | — | any hit that is not on the list of explained hits the owner accepted in writing for this manifest; report file and line, never the value |
| 2 | `gh repo create w7-mgfcode/coreos-platform-lab --public --description "<§ 3>"`, without `--source` and `--push`; then the settings of § 3 | `gh repo view` fails with "not found" | the name is taken |
| 3 | The 35 labels of § 4 | `gh label list` | — |
| 4 | The six milestones of § 6 | `gh api repos/w7-mgfcode/coreos-platform-lab/milestones?state=all` | — |
| 5 | Issue S0.1, with milestone and labels | `gh issue list --state all` is empty | the new issue is not number 1: the commit subject names `#1` |
| 6 | `git add -A`; confirm the staged list equals the scanned list; `git commit` with the subject of S0.1 and no trailer; `git remote add origin https://github.com/w7-mgfcode/coreos-platform-lab.git`; `git push -u origin main` through gh's credential helper | the commit hook accepts the message | the push is rejected for exposing a private address: stop and ask, do not change the identity |
| 7 | Tick the criteria of #1 with the commit SHA as proof; close it with a comment giving the SHA | — | a criterion does not hold |
| 8 | Board: `gh project create --owner w7-mgfcode --title "CoreOS Platform Lab Delivery"`; make it public with its description and README; `gh project link`; create the fields of § 5; replace the `Status` options through `updateProjectV2Field` **before** any item is added | `gh project list --owner w7-mgfcode` | `gh` reports a missing `project` scope: report the exact error |
| 9 | Issues in this order: U1; E0, E1, E2, E3, E5, E6, E4; then the sub-issues in the order of § 7. Bodies are written to scratch files outside the repository, scanned, and posted with `--body-file` | `gh issue list --search "<title>" --state all` per issue | a scan hit in a body |
| 10 | Native links: each epic under U1, each sub-issue under its epic, #1 under E0 | `gh api …/issues/<parent>/sub_issues` | — |
| 10a | **Number pass** (r6): bodies created in step 9 name other issues by plan ID (`S2.2`, `E3`). Once every issue exists, replace each plan ID with its issue number in every body, in one pass with `gh issue edit --body-file`; rescan each edited body before posting; list the replacements in the run log. Before replacing, every range of plan IDs (`S0.1 … S0.7`, `E0 … E3`) is expanded into the full list of IDs; a range is never translated end to end. The tokens replaced are exactly the Plan ID column of § 19 (`U1`, `E0` … `E6`, `S0.1` … `S6.2`). `S1 §` and `S2 §` name the two drafts and are written out as `docs/.prepare/delegation/s1-platform-delivery.md §` and `docs/.prepare/delegation/s2-security-verification.md §` | the table of § 19 is filled with the numbers just assigned | any plan-ID token remains in a body; a scan hit in an edited body |
| 11 | Board items: add every issue with `gh project item-add`; set Type, Area, Priority, Tier, Gate and Status | item list | — |
| 12 | GitHub scaffold: `git switch -c chore/repo-github-scaffold`; add the files of S0.2; scan `git diff --stat origin/main...`; commit `chore(repo): add issue and pr templates, codeowners and dependabot (#<S0.2>)`; push; open the pull request with `Closes #<S0.2>`. **Not merged.** Board status of S0.2: `In Review` | S0.2 exists and is open | — |
| 13 | Read-only audit of what was created: counts against § 7, no issue without a parent, milestone or `type:` label; then the final report | — | — |

**Where commits run** (review note b): every `git commit` in steps 6 and 12 runs from the repository root, because `.claude/settings.json` calls the commit hook by a relative path and the hook is not found from any other directory. The steward checks the message against `.claude/rules/commit-format.md` itself before the commit and does not rely on the hook alone. *(r8: the orchestrator session reports that the hook command now uses the project-directory form, § 21.4; the rule to commit from the root and to check the message first is kept.)*

**First-commit exception** (D-28): step 6 is the only direct push to `main`. Every later change, including step 12, is a pull request.

**Commit identity** [step 6: decided, D-52, option I1; squash-commit identity: open]: step 6 publishes the repo-local name and address as they are, as the owner approved on 2026-11-16 (D-52). The identity is configured for this repository only and is compared with the owner's instruction without printing it; **no value is written in this plan, in an issue, a pull request, the board or a report**. The steward had recommended I2 (a no-reply address); **that recommendation was not adopted**. The account's privacy settings are not changed; if a setting rejects the push, step 6 stops and the specific blocker is reported (its stop condition stays). Squash merges made on GitHub are a second matter, **not decided by D-52 (open point 6)**: such a commit is authored with the account's own name and its GitHub address setting, not with the repo-local identity (known GitHub behaviour, not observed in this repository). `main` would then carry two identities unless the owner aligns them.

**After the bootstrap**, this file is not rewritten with issue numbers: the tree on GitHub is the work record (core-context § 9).

## 13. Keeping the tree truthful

- After every merge: board status to `Done`, the parent's line ticked with the pull request as proof, `Sub-issues progress` checked, the next unblocked sub-issue to `Ready`.
- A box is ticked only with proof appended. A check that was not run on the lab is recorded as not run.
- Every pull request that touches a deployed component names the checks to re-run (`.claude/rules/test-requirements.md`, "When a relevant change lands after a check passed"); the E5 table is updated when they have been.
- A change to a pinned component version gets its own issue, naming the checks to re-run.
- A Dependabot pull request gets an issue and a corrected title before a merge is proposed.
- Rollup stays manual. Automation would need a stored token with project access, which is the owner's decision.

## 14. Differences from the mission

The mission says the reviewed plan wins where they differ and asks for the differences to be reported. The orchestrator's review of 2026-11-14 accepted all five; the questions behind rows 1 and 2 still go to the owner (§ 15, open points 1 and 2).

| # | Mission | This plan | Reason |
|---|---|---|---|
| 1 | The platform scaffold and the CI workflow are sub-issues of E0 | They are S1.2 and S1.3 under E1 | [implementation-plan.md](implementation-plan.md) § 3 puts D2 in architecture step 2 and after the spike (D-33). Inside E0 they would keep `M0 - Preparation` open until lab work has begun |
| 2 | The EXTRA layers are sub-issues of E1 | Their own epic E6, still in `M1 - Host & Firewall` | E1 can then close at the MUST HAVE exit. The agent definition allows "their own later epic". Cost: milestone M1 stays open until E6 is resolved |
| 3 | Epics E0 … E5 | E0 … E6 | follows from 2 |
| 4 | — | The spike sub-issue carries the pinned Butane render command in the same pull request | implementation-plan D1 makes that command the first part of the spike; one branch, one pull request |
| 5 | Status `Ready` for E0's actionable items | Only S0.2 is `Ready`; the D0 items are `Blocked` | each waits on an owner answer |

## 15. Verified, assumed, proposed, open

**Verified** (commands run on 2026-11-14; the reference observations are in the G-1 report recorded in [delegation-manifest.md](delegation-manifest.md) § 4):
- `gh repo view w7-mgfcode/coreos-platform-lab` returns "not found"; the token lists the `repo`, `project` and `workflow` scopes (`gh auth status`).
- The working tree has no commit, no remote and no `.github/` directory (`git status`, `git remote -v`).
- The installed `gh` is 2.46.0. `gh repo edit --help` shows no flag for secret scanning or the squash title. Every other flag named in § 3 and § 12 is in the help text of its command: `gh repo create`, `gh repo edit`, `gh project edit`, `gh project field-create`, `gh project link`, `gh pr merge`.
- Every title in § 7, with ` (#1)` appended, matches the subject pattern of `.claude/hooks/check-commit-format.sh`; every label description is within 100 characters (checked after writing; see § 17).
- The reference board has the six `Status` options and the built-in fields used in § 5 (`gh project field-list 2 --owner w7-mgfcode`).

**Verified again on 2026-11-16 (r9; read-only queries only, nothing created; the 2026-11-14 observations above are not reused). The Stage 2 package named in this plan is a local, unpublished working set and is not part of this repository:**
- `gh auth status`: logged in as `w7-mgfcode`; the token scopes include `repo`, `project` and `workflow` (observed on 2026-11-16; step 0 checks it again when Stage 2 runs). No token value was printed.
- `gh repo view w7-mgfcode/coreos-platform-lab`: "Could not resolve to a Repository": the repository does not exist, as expected.
- No board titled `CoreOS Platform Lab Delivery` exists for the owner.
- The installed `gh` is 2.46.0. Every flag of § 3, § 5 and § 12 is in the help text of its command, except those that the plan already routes through `gh api`: `gh repo edit` has no flag for secret scanning, push protection or the squash title fields; `gh project create` has no visibility flag (`gh project edit --visibility` has it); `gh issue create` and `gh issue edit` have no parent or sub-issue flag (the native links use `gh api`). `gh project` has no view command and no workflow command.
- The GraphQL schema has `createProjectV2View`, `updateProjectV2View`, `createProjectV2Field`, `updateProjectV2Field` and `deleteProjectV2Workflow`, and no mutation that creates or edits a built-in workflow. This corrects the assumption below on views.
- The REST endpoints for native sub-issues (`GET …/issues/<n>/sub_issues`) and for issue dependencies (`GET …/issues/<n>/dependencies/blocked_by`) answer on an existing repository of the owner. The `POST` forms were not run.
- The GraphQL field type list has `ISSUE_TYPE`: a board may already own a built-in field called `Type`. Whether `gh project field-create --name Type` is rejected on a new board is **not verified**; the Stage 2 package carries the fallback name (open for the owner).
- Whether the account blocks command-line pushes that expose an address cannot be read with the installed tooling and is not known; no account setting was changed.

**Assumed:**
- GitHub appends the pull-request number to a default squash subject, and authors a squash commit with the account's identity. Known behaviour, not observed in this repository.
- A new board offers `Parent issue` and `Sub-issues progress` as the reference board does.
- Project views cannot be created through the API with the installed tooling. *(r9: corrected by the read-only check above: `gh` has no view command, but the GraphQL schema has `createProjectV2View` and `updateProjectV2View`. They take no grouping, so the grouped "Roadmap" view cannot be fully set that way. Not run.)*
- `PATCH` on a new public repository accepts `security_and_analysis` and the squash title fields.
- Planned paths not named by D-05 (the spike notes, the version list, the install documentation, the example files, per-service configuration) are placeholders until S1.2 and OQ-34 fix them.

**Proposed** (each is the steward's and can be overruled):
- The tree of § 7 with 1 umbrella, 7 epics and 26 sub-issues, and conditional sub-issues (S0.C3; S0.C4 since r6).
- The five differences of § 14.
- `gate:` labels mark claims only (§ 2 point 6).
- One colour for the whole `priority:` family, as the agent definition asks; the reference grades the three priorities by colour.
- `squash_merge_commit_message=BLANK`, so a squash commit carries its subject only.
- The umbrella's extra success line on requirement-row proofs, and its close rule (§ 8).
- The implementation gate is expressed as a board rule, not as a label (§ 2 point 5).
- A new open question for the Proxmox role that S6.1 needs.
- *(r6)* The conditional sub-issue S0.C4 (r8: its title wording is the steward's proposal, not an owner condition); the added edges (S5.3 depends on S2.3; S4.2 depends on S4.1); the freeze and number-pass steps of § 12; the status workflow of § 5; every recommendation of § 21.

**Open:**
1. **Answered on 2026-11-16 by D-51: as the plan proposes.** The platform scaffold and the CI workflow sit under E1 (S1.2, S1.3), not in E0 (§ 14 row 1). *(Question as asked: should they sit in E0 as the mission says, or in E1 as proposed?)*
2. **Answered on 2026-11-16 by D-51: E6 keeps M1.** M1 stays open until E6 is delivered or closed as "not planned" with a recorded owner decision (§ 6). *(Question as asked: keep M1 or a seventh milestone?)*
3. **Answered on 2026-11-16 by D-51: no.** D-41 and D-42 do not prevent the platform sub-issues from being prepared (§ 11). This approves neither the technical substance of D-41 and D-42, which stay proposals, nor anything behind the implementation gate. *(Question as asked: should they block the platform sub-issues?)*
4. May the scaffold (S1.2) start before the spike if the owner inputs for the spike are late? Nothing in it depends on a spike answer; D-33 orders it after. *(r9: still open; D-51 does not decide it.)*
5. **Answered on 2026-11-14 (gate item 13): split.** S2.2 claimed AC-04 and AC-05 together, as D6 does. AC-05 does not need the external relay, so the owner had the issue split: S2.2 claims AC-05, S2.3 claims AC-04 (§ 7, § 9; review note a, § 16).
6. Which identity should squash commits on `main` carry (§ 12)? *(r9: the identity of the **first (bootstrap) commit** is answered by D-52, option I1, 2026-11-16. The identity of squash merges made on GitHub is **not decided**: D-52 says so, and this point stays open.)*
7. The clarification pull requests S0.3 … S0.7 edit files under `docs/.prepare/`. The mission puts those edits outside the steward's bounds, so another session or the owner writes them. Is that meant to stay so after publication? **Answered on 2026-11-16 by D-51:** the implementation of S0.3 … S0.7 belongs to the owner or to a session the owner assigns; the steward does not write them.
8. [readiness-report.md](readiness-report.md) (PREP-10) did not exist when this plan was written; the proposed rule changes it is said to list (the test rule's gate block, the scope for `scripts/validate.sh`, the hook's optional scope) could not be cross-checked.
9. **Answered on 2026-11-16 by D-48: S3.1 after S2.2.** *(Added in r4 as an open question.)* Decided: S3.1 may be integrated and accepted after S2.2 without waiting for S2.3, provided its own prerequisites and acceptance conditions hold. As the security draft § 10.6 already allows, the SMTP event of AC-06 may then come from S2.2. Conditions the owner attached, carried as notes under S2.3 and S3.2 and as one criterion in S5.3: one designated writer at a time for the shared files; the deployment of S2.3 outside the renewal trial's observation window, because the described procedure restarts Caddy; a re-run of AC-06 when S2.3 affects it; the Postfix queue-ID search in the final release evidence; no unconditional dependency of S3.2 or S5.1 on S2.3. AC-04 stays mandatory, so S2.3 still precedes the release (§ 11). Not decided: D-33 as a whole, which stays a proposal; the proposals of the same review on the mail tests (holding or removing the test message, queue clean-up criteria, exact Postfix settings, further test conditions) and on the wording of the renewal-trial criterion; D-47 is not confirmed anew.
10. *(r6)* Is the Proxmox lab-agent workstream part of the public repository, and when? **Answered on 2026-11-16 by D-49: option C.** The tooling is excluded from the initial publication; a later inclusion needs a separate owner decision and a separate pull request. Options A–D and the recommendation stay in § 21.4 as the record. The owner set no condition for a later inclusion, and none is assumed here.
11. *(r6)* What exactly is in the bootstrap commit? § 21.3 lists the candidate set, 95 paths after D-49. **Answered on 2026-11-16 by D-50:** the 26 command files and 2 agent definitions under `.claude/` that D-45 does not name are kept; `docs/.prepare/` is included in the initial publication; OQ-35 is not a prerequisite. The 95 paths are the starting point, subject to the corrections the owner authorized on the same day and to the verification of the final manifest (§ 22.3). The root `AGENTS.md` and `CLAUDE.md` are in, reworded by the orchestrator session so that they name no excluded path (reported, § 21.4).
12. *(r6)* Licence (OQ-22) and commit identity (OQ-21, with open point 6): options and recommendations in § 21.1 and § 21.2. **Answered on 2026-11-16:** the licence is deferred, L2, no `LICENSE` file now (D-53; OQ-22 stays open); the identity of the bootstrap commit is I1, the repo-local name and address as they are (D-52; OQ-21 is closed by that row). The steward's recommendation I2 was not adopted. The identity of squash merges stays open (point 6).
13. *(r6)* Is the bootstrap one direct push of a content commit (D-28), or an empty first commit followed by a reviewed pull request (§ 21.5)? **Answered on 2026-11-16 (D-28, option P1):** one direct push of the bootstrap commit under #1, then pull requests only. The owner's words: approving the procedure is not yet permission to create a commit or to push.
14. *(r6)* Two added dependency edges (§ 20): S5.3 depends on S2.3, which makes AC-04's place before the release visible in the sub-issue graph, and S4.2 depends on S4.1, because the update trial of S4.2 needs "a backup before". S4.1 → S5.3 and S4.2 → S5.3 only restate the epic rule of E4 per issue. Keep or drop? **Not decided. Both edges stay in this plan as proposed, and the owner is asked with the final go-ahead request** (the owner stated on 2026-11-16 that an item whose content had not been presented is not approved; D-51 says the same). What dropping each edge would change is in § 20, "If the owner drops a point-14 edge".
15. *(r6)* The root `AGENTS.md` and `CLAUDE.md` now exist, so S1.2 updates them instead of creating one (§ 9). Implementation-plan D2 and R-21 still speak of creating a root `CLAUDE.md`: the orchestrator is to align them (§ 21.7).

## 16. Orchestrator review, 2026-11-14

The orchestrator session reviewed r1 and accepted it for the owner's review. Its findings: every MUST HAVE row and AC-01 … AC-09 are covered; AC-10 sits only under the OPTIONAL epic; no EXCLUDED item has an issue; the five differences of § 14 are accepted. This is an agent review, not an approval.

| Note | Content | Effect on this plan |
|---|---|---|
| a | Open point 5 is to be shown to the owner as an option: split S2.2 so that AC-05, which is load-bearing and does not need the external relay, is not held back by OQ-04 | Offered at the gate. If the owner takes it, S2.2 becomes two sub-issues before anything is created: one that brings up Postfix with the single trusted client and claims AC-05, and one that adds the relay hand-over and the WordPress mail path and claims AC-04. The tree then has 26 sub-issues |
| b | In the steward's pane a Bash call reported that `.claude/hooks/check-commit-format.sh` was not found. `.claude/settings.json` calls the hook by a relative path, so it runs only when the shell is in the repository root | Stage 2 runs every `git commit` from the repository root and the steward checks the message against the commit rule first (§ 12) |
| c | Open points 1, 2, 3, 4, 6 and 7 go to the owner as they are | Listed among the owner decisions at the publication gate. Open point 8 stays with the orchestrator: it concerns the readiness report |

**After the review (r3).** On 2026-11-14 the orchestrating side relayed two owner decisions, D-44 and D-45, which settle gate items "diagrams 01–04" and "tooling under `.claude/`" as fixed before publication. This plan changed in three places only: the conditional sub-issues S0.C1 and S0.C2 are dropped (§ 7), the criteria of S0.1 name the excluded tooling (§ 9), and the count of conditional sub-issues is corrected (§ 15). The tree of 1 umbrella, 7 epics and 25 sub-issues is unchanged. The publication gate stayed closed.

**After the review (r4).** On 2026-11-14 the orchestrating side relayed the owner's answer to gate item 13: yes, split S2.2 as note a describes. The split is applied: S2.2 brings up Postfix with the single trusted client and claims AC-05; S2.3 adds the relay hand-over and the WordPress mail path, claims AC-04 and re-runs AC-05. The changes are in § 7 (table, counts), § 9 (E2), § 10, § 11 and § 15. Two things in them go beyond note a and are the steward's proposals: the criterion on the message the allowed client queues in S2.2, and the re-run of AC-05 in S2.3. The dependency of S3.1 was moved from S2.2 to S2.3 so that the order of the reviewed plan is kept (§ 15, open point 9). The tree has 1 umbrella, 7 epics and 26 sub-issues. This revision was not re-reviewed. The publication gate stayed closed.

**After the review (r5).** On 2026-11-16 the orchestrating side relayed the owner's scheduling decision D-48 ([decision-log.md](decision-log.md) r6), given after a read-only review of r3 and r4: S3.1 may be integrated and accepted after S2.2 without waiting for S2.3. It answers open point 9 (§ 15). The changes: the header; a note in § 7; the approach line of § 8; in § 9 the dependency of S3.1 (S2.2, S1.1), its prerequisites by kind, a dependencies line in E3, notes under S2.3 and S3.2, and one criterion in S5.3 on the Postfix queue-ID search; a coverage cell and the order line of § 10; a paragraph in § 11; open point 9 in § 15. Requirements, acceptance conditions, labels, milestones, counts and statuses are unchanged, and the split of r4 is not reopened. § 17 remains the completion report of task G-2 and is not rewritten. The review state of r5 is recorded by the orchestrator in [readiness-report.md](readiness-report.md); this paragraph claims no review. Both owner gates stayed closed.

**Task GH-6 (r6).** On 2026-11-16 the orchestrating side asked for the local Stage 1 package to be completed, under the owner's instruction of that day: local preparation only, both gates closed, nothing created on GitHub. The existing plan was reused; the decomposition was not restarted. What changed, and nothing else: § 18 … § 22 are new; the header; a pointer in § 1; one setting row in § 3 and the label-application rules in § 4; the status workflow in § 5; the milestone scope table in § 6; the conditional S0.C4 in § 7; in § 9 the criteria of S0.1 (the root files, the manifest, the lab-agent line) and of S1.2 (the root files exist), `Depends on` lines for S0.3 … S0.7, S4.1 and S4.2, and the edges S5.3 depends on S2.3 and S4.2 depends on S4.1; the preconditions note, step 0 and step 10a in § 12; open points 10 … 15 and one line under "Proposed" in § 15; two sentences at the end of the D-48 paragraph of § 11; the first line under "Proposed" in § 15. Requirements, acceptance conditions, labels (35), milestones (6), issue counts (1 + 7 + 26), the statuses at creation and D-48 are unchanged. The status is `draft`. This revision claims no review and no publication readiness. § 17 remains the completion report of task G-2 and is not rewritten.

**Task GH-6c (r7).** On 2026-11-16 the orchestrating side asked for corrections to r6 after the final independent review, which is recorded by the orchestrator and is not described here. Same authority and same single write path as GH-6; both owner gates stayed closed and nothing was created on GitHub. The corrections are the list in the header's r7 line. They touch the header, § 4, § 5, § 7, § 9 (S0.1, S4.2), § 12 (steps 0, 1 and 10a), § 15, this section, § 18, § 19 (the generated table), § 21 and § 22. Requirements, acceptance conditions, labels (35), milestones (6), issue counts (1 + 7 + 26), the statuses at creation, D-48 and every criterion of S1.5, S2.2, S2.3, S5.1, S6.1 and S6.2 are unchanged. The status was `draft` when these corrections were made. The final independent review of r6 and its confirmation of r7 (both by a session other than the author, 2026-11-16) ended with no blocking finding. The two wording points N3 and N4 and the status field were changed after that confirmation and were checked by the orchestrator by diff, not by the reviewer. A technical review is not an owner approval, and both owner gates stay closed.

**Task GH-P (r9).** On 2026-11-16 the orchestrator session asked for this plan to carry the owner's answers to items 2 to 6 of § 21.8 and for the Stage 2 package to be prepared and not executed. Same authority and bounds: the write path of this file is the only change to `docs/`; the publication gate is closed; only read-only `gh` queries were run (§ 15, "Verified again on 2026-11-16"). The changes are the list in the header's r9 line. Open and marked as such: point 14, point 4, D-35, the identity of squash merges and the go-ahead. This paragraph claims no review.

## 17. Completion report

| Item | Content |
|---|---|
| Session | `github-steward`, task G-2, Stage 1b |
| Baseline | `docs-baseline-r2` |
| Files created or changed | `docs/.prepare/github-project-plan.md` (this file) only. No commit, branch, remote or GitHub object |
| Evidence consulted | the agent definition and the mission as revised; `.claude/rules/` (seven files); [docs/architecture.md](../architecture.md) § 2, § 6, § 10; README, core-context, source-register, decision-log, open-questions at r2; methodology-adaptation r1; implementation-plan r1; plan-review r2 (§ 6, § 8, § 9); the platform and security drafts for files, test names and the exposure matrix; the reference observations of G-1 |
| Decisions proposed | the eight proposals of § 15; none is settled |
| Assumptions introduced | the five of § 15 |
| Open questions | the eight of § 15 as written at r1 (point 5 answered and a ninth added at r4); one candidate for the open-questions list (the Proxmox role for S6.1) |
| Proposed changes to core documents | open-questions: add the Proxmox-role question for S6.1; record whether views are the owner's manual step. Decision log: record the gate answers before the first commit (§ 12). Mission: § 2.4 step 2 still says the CI workflow "belongs to the scaffold sub-issue"; it is its own sub-issue (S1.3) |
| Validation performed | titles checked against the hook's subject pattern; label count and description lengths; every MUST HAVE row and AC-01 … AC-09 mapped in § 10; AC-10 only under E4; every `Blocked` issue of § 7 has a row in § 11; the file scanned for absolute home paths, mail addresses, the local git identity and the former working name |
| Limitations | nothing here was tried on github.com. Paths and test names come from the drafts and are proposals. The plan was written before the readiness report existed |
| Status | r4: as reviewed at r2 and accepted with three notes, plus the two changes recorded at the end of § 16; `ready-for-human-review`. The pre-publication scan and the gate presentation (Stage 1c) are shown in the steward's session, not in this file |

**Task GH-C (r8).** On 2026-11-16 the orchestrator session asked for this plan to carry the owner's answer to item 1 of § 21.8: option C, recorded as D-49 (decision-log r7). Stage 1 only: the one write path is this file; no `gh` command was run, nothing was created on GitHub, and both owner gates stay closed. What changed: the answer and the record markers in § 21.4; the listing and the groups in § 21.3 (161 before, 66 excluded, 95 after); § 21.6 (D-20), § 21.7 and § 21.8; the condition of S0.C4 (§ 7, § 19) and the two lab-agent criteria of S0.1 (§ 9); the preconditions note (§ 12), open points 10 and 11 (§ 15); § 22.1 (superseded snapshot), § 22.2, § 22.3 check 12 and § 22.4; the header. The tree (1 + 7 + 26), the labels (35), the milestones (6), the statuses at creation and the Stage 2 order are unchanged. Facts about the change to `.gitignore`, `.claude/settings.json`, `AGENTS.md` and `CLAUDE.md` are as reported by the orchestrator session; the steward confirmed the count of 95 and its groups. Publication readiness is not established. Corrected after an independent review on 2026-11-16 (the pointer and the marker in § 21.4, the note on row C, the count note in § 21.3); the review state is recorded in [readiness-report.md](readiness-report.md) § 10e; a technical review is not an owner approval. The status is `ready-for-human-review`.

## 18. Completeness of the Stage 1 package

Added in r6, after the G-2 report of § 17. It answers one question: can Stage 2 create the repository, the issue hierarchy, the milestones and the board from this file without inventing anything? **Everything named below is a proposal.** Nothing exists on GitHub, no owner decision is assumed, and the tree is not approved by being complete.

| Part | Where | State in r6 | Added or confirmed in r6 | Still a proposal or open |
|---|---|---|---|---|
| a. Repository description and settings | § 3 | present, concrete | row for the default branch; the settings-API fields stay an assumption (§ 15) | all values are proposals; licence (§ 21.1); branch protection, proposed only after the first CI run |
| b. Labels: name, colour, description, purpose | § 4 | present, 35 labels | rules for applying each family; checked mechanically: 35 labels, family sizes 3 / 15 / 10 / 3 / 3 / 1, every description under 100 characters, every label an issue uses exists (§ 20) | colours and the family scheme are proposals (D-20, D-21). `area:diagrams` is used by no issue in § 7; it is one of the 15 scopes and is kept |
| c. Milestones with scope and exit, no due dates | § 6 | present, six | table of what each milestone holds, 8 / 9 / 4 / 4 / 3 / 5 issues and the umbrella outside them | whether E6 keeps M1 (§ 15 point 2). No due date: no deadline exists (OQ-01) |
| d. Umbrella, epics, sub-issues | §§ 7–9, § 11 | present: 1 + 7 + 26, each with title, parent (by ID, § 19), description, criteria, dependencies, labels, milestone | an explicit `Depends on` line on every sub-issue; criteria of S0.1 and S1.2 brought in line with the root files; conditional S0.C4 | the criteria are proposals; blocked items wait on § 11 |
| e. Project (Projects v2): fields, views, workflow, manual rollup | § 5, § 13 | present | status workflow and the rollup pass; the built-in workflows are an assumption to observe | views are created by hand in the browser, if wanted; no automation (owner decision); the board README text is composed in Stage 2 from the outline of § 5 and shown to the owner before it is posted |
| f. Creation order for Stage 2 | § 12 | present, 13 steps | step 0 (freeze and token scopes) and step 10a (number pass) | the order is a proposal; the preconditions need the answers of § 21.8 |
| g. One mapping table | § 19 | **new** | every plan identifier to its future GitHub object | numbers and URLs are assigned at creation |

**Composing the bodies without inventing text.** The templates are those of the agent definition ("Issue body templates"). Stage 2 fills each heading only from this file:

| Template heading | Filled from |
|---|---|
| Umbrella: Summary, Approach, Decomposition, Out of scope, Success criteria, Risks, Tracking | § 8, verbatim; Decomposition lists the issue numbers of E0 … E6 after the number pass |
| Epic: `Parent umbrella: #N` | the Parent column of § 19 |
| Epic: Purpose, Acceptance criteria, Dependencies, Out of scope, Validation path | the epic's own block in § 9, verbatim; a heading with no text there reads "none stated in the plan" |
| Epic: Sub-tasks | the children of the epic in § 19, one line each, with the title |
| Epic: Board fields | the last column of § 19 |
| Sub-issue: `Sub-issue of #N` | the Parent column of § 19 |
| Sub-issue: Purpose | the title, followed by the **Source** line of § 9 |
| Sub-issue: Scope | the **Files** and **Author** lines of § 9 |
| Sub-issue: Out of scope | the parent epic's "Out of scope", plus "everything outside the files listed" |
| Sub-issue: Dependencies and Risks / blockers | the `Depends on` line and the row of § 11, with the risk and finding references (R-, F-) of the Source line |
| Sub-issue: Acceptance criteria | the checkboxes of § 9, verbatim, all unticked |
| Sub-issue: Why it matters now | derived by rule: the step (Dn), what the issue follows and what it unblocks (§ 20), and the check it claims or "claims no check" |
| Any heading: links, references, markers | a relative Markdown link becomes its link text followed by the repository-relative path in code formatting (`docs/architecture.md`), with no URL; a bare `§ N` that means this plan is written `docs/.prepare/github-project-plan.md § N`; markers of the form `*(r6: …)*` and `[provisional]` are dropped, and a criterion marked `[provisional]` is first rewritten to the owner's answer in a revision of this plan |
| Sub-issue: Dependencies, continued | the paragraph headed "Notes on order", "Prerequisites by kind" or "Scheduling note" that follows the sub-issue in § 9, verbatim, under the sub-heading "Scheduling notes (D-48)"; these are not criteria |

A body says planned work is planned. It never says that something is built, tested or passing, and it ticks nothing without proof (§ 13).

## 19. Identifier mapping to GitHub objects

One table, generated from § 4, § 6, § 7 and § 9 as they stand and checked by the method of § 20, so that it cannot drift from them without the check failing. Every local identifier of this plan appears once: the repository, the 35 labels and 6 milestones by name, the board, the umbrella, the epics and sub-issues, the bootstrap commit, the one pull request, and the two conditional sub-issues. **The Number / URL column is "assigned at creation" throughout.** No issue number, URL, date or SHA is predicted. The one number the plan depends on is that S0.1 must be the first issue of the repository, because its commit subject names it (step 5 of § 12 stops otherwise).

How to read it:

- **Labels** lists `type:`, `area:`, `gate:`, `tier:`, `priority:` and `status:blocked`, as § 4 applies them. The board Area is the first scope of the title (§ 4); `Done`, `Ready`, `In Progress`, `Backlog` and `Blocked` are the statuses at creation (§ 5, § 7).
- **Depends on** is the sub-issue's own `Depends on` line (§ 9). For an epic it is the epic-level dependency of § 9 plus "its children": an epic closes after its sub-issues. U1 closes last.
- **Step** is the step of § 12 that creates the object; "link 10" and "board item 11" are the native-link and board steps for every issue. The plan identifiers in issue bodies are replaced by numbers in step 10a.
- The rows are ordered as Stage 2 creates them, not as § 7 lists them: S0.1 first (it must be #1), then U1, the epics, and the other sub-issues.

| Plan ID | Object | Title or name | Parent | Milestone | Labels | Depends on | Step (§ 12) | Board: Type · Area · Priority · Tier · Gate · Status at creation | Number / URL |
|---|---|---|---|---|---|---|---|---|---|
| REPO | repository | `w7-mgfcode/coreos-platform-lab`, public; settings of § 3 | — | — | — | — | 2 | — | assigned at creation |
| `type:umbrella` | label | `type:umbrella` (colour `1D76DB`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `type:epic` | label | `type:epic` (colour `1D76DB`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `type:sub-issue` | label | `type:sub-issue` (colour `1D76DB`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:host` | label | `area:host` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:compose` | label | `area:compose` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:proxy` | label | `area:proxy` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:web` | label | `area:web` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:mail` | label | `area:mail` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:logs` | label | `area:logs` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:monitoring` | label | `area:monitoring` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:firewall` | label | `area:firewall` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:backup` | label | `area:backup` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:tests` | label | `area:tests` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:docs` | label | `area:docs` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:diagrams` | label | `area:diagrams` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:ci` | label | `area:ci` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:repo` | label | `area:repo` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `area:release` | label | `area:release` (colour `BFD4F2`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `gate:ac-01` | label | `gate:ac-01` (colour `0E8A16`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `gate:ac-02` | label | `gate:ac-02` (colour `0E8A16`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `gate:ac-03` | label | `gate:ac-03` (colour `0E8A16`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `gate:ac-04` | label | `gate:ac-04` (colour `0E8A16`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `gate:ac-05` | label | `gate:ac-05` (colour `0E8A16`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `gate:ac-06` | label | `gate:ac-06` (colour `0E8A16`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `gate:ac-07` | label | `gate:ac-07` (colour `0E8A16`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `gate:ac-08` | label | `gate:ac-08` (colour `0E8A16`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `gate:ac-09` | label | `gate:ac-09` (colour `0E8A16`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `gate:ac-10` | label | `gate:ac-10` (colour `0E8A16`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `priority:p0` | label | `priority:p0` (colour `D93F0B`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `priority:p1` | label | `priority:p1` (colour `D93F0B`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `priority:p2` | label | `priority:p2` (colour `D93F0B`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `tier:must-have` | label | `tier:must-have` (colour `5319E7`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `tier:extra` | label | `tier:extra` (colour `5319E7`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `tier:optional` | label | `tier:optional` (colour `5319E7`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `status:blocked` | label | `status:blocked` (colour `B60205`, description in § 4) | — | — | — | — | 3 | — | assigned at creation |
| `M0 - Preparation` | milestone | `M0 - Preparation` (description in § 6) | — | — | — | — | 4 | — | assigned at creation |
| `M1 - Host & Firewall` | milestone | `M1 - Host & Firewall` (description in § 6) | — | — | — | — | 4 | — | assigned at creation |
| `M2 - Web & Mail` | milestone | `M2 - Web & Mail` (description in § 6) | — | — | — | — | 4 | — | assigned at creation |
| `M3 - Logs & Monitoring` | milestone | `M3 - Logs & Monitoring` (description in § 6) | — | — | — | — | 4 | — | assigned at creation |
| `M4 - Backup, Restore & Update` | milestone | `M4 - Backup, Restore & Update` (description in § 6) | — | — | — | — | 4 | — | assigned at creation |
| `v0.1.0 - Release Gate` | milestone | `v0.1.0 - Release Gate` (description in § 6) | — | — | — | — | 4 | — | assigned at creation |
| BOARD | Projects v2 board | `CoreOS Platform Lab Delivery`, owner `w7-mgfcode`, public, linked to the repository; README and short description of § 5 | — | — | — | — | 8 | — | assigned at creation |
| BOARD-F | board fields | Status (options replaced), Type, Area, Priority, Tier, Gate (§ 5) | BOARD | — | — | — | 8 | — | assigned at creation |
| **S0.1** | issue, sub-issue | `docs: add architecture, diagrams, preparation package and agent tooling` | E0 (native sub-issue, linked in step 10) | `M0 - Preparation` | `type:sub-issue`, `area:docs`, `area:repo`, `tier:must-have`, `priority:p1` | — | 5 (created as #1), 6 (commit), 7 (closed); link 10; board item 11 | Sub-issue · Docs · P1 · Must-have · — · Done | assigned at creation |
| **U1** | issue, umbrella | `feat(repo): coreos platform lab v0.1.0 — single-vm compose stack with proven acceptance checks` | — | none | `type:umbrella`, `area:repo`, `tier:must-have`, `priority:p0` | E0 … E6 (closes last) | 9; link 10; board item 11 | Umbrella · Repo · P0 · Must-have · — · In Progress | assigned at creation |
| **E0** | issue, epic | `chore(repo): preparation — owner inputs, repository bootstrap and github scaffold` | U1 (native sub-issue) | `M0 - Preparation` | `type:epic`, `area:repo`, `area:docs`, `tier:must-have`, `priority:p0` | its children | 9; link 10; board item 11 | Epic · Repo · P0 · Must-have · — · In Progress | assigned at creation |
| **E1** | issue, epic | `feat(host): host and firewall — fcos vm with docker ce, boot-time start and the host firewall` | U1 (native sub-issue) | `M1 - Host & Firewall` | `type:epic`, `area:host`, `area:firewall`, `tier:must-have`, `priority:p0` | its children | 9; link 10; board item 11 | Epic · Host · P0 · Must-have · — · Backlog | assigned at creation |
| **E2** | issue, epic | `feat(web): web and mail — wordpress over trusted https and mail through postfix` | U1 (native sub-issue) | `M2 - Web & Mail` | `type:epic`, `area:web`, `area:mail`, `tier:must-have`, `priority:p0` | its children | 9; link 10; board item 11 | Epic · Web · P0 · Must-have · — · Backlog | assigned at creation |
| **E3** | issue, epic | `feat(logs): logs and monitoring — searchable web and mail events and checkmk alerts` | U1 (native sub-issue) | `M3 - Logs & Monitoring` | `type:epic`, `area:logs`, `area:monitoring`, `tier:must-have`, `priority:p0` | S2.2 (+ its children) | 9; link 10; board item 11 | Epic · Logs · P0 · Must-have · — · Backlog | assigned at creation |
| **E5** | issue, epic | `release(release): v0.1.0 release gate — acceptance in full, rebuild, changelog and tag` | U1 (native sub-issue) | `v0.1.0 - Release Gate` | `type:epic`, `area:release`, `area:tests`, `tier:must-have`, `priority:p0` | its children | 9; link 10; board item 11 | Epic · Release · P0 · Must-have · — · Backlog | assigned at creation |
| **E6** | issue, epic | `feat(firewall): extra firewall layers — proxmox firewall and docker network isolation` | U1 (native sub-issue) | `M1 - Host & Firewall` | `type:epic`, `area:firewall`, `tier:extra`, `priority:p2` | S5.3, unless the owner decides otherwise (+ its children) | 9; link 10; board item 11 | Epic · Firewall · P2 · Extra · — · Backlog | assigned at creation |
| **E4** | issue, epic | `feat(backup): backup, restore and update — optional tier trials` | U1 (native sub-issue) | `M4 - Backup, Restore & Update` | `type:epic`, `area:backup`, `tier:optional`, `priority:p2`, `status:blocked` | S5.3, unless the owner decides otherwise (+ its children) | 9; link 10; board item 11 | Epic · Backup · P2 · Optional · — · Blocked | assigned at creation |
| **S0.2** | issue, sub-issue | `chore(repo): add issue and pr templates, codeowners and dependabot` | E0 (native sub-issue) | `M0 - Preparation` | `type:sub-issue`, `area:repo`, `tier:must-have`, `priority:p1` | S0.1 | 9; 12 (pull request, not merged); link 10; board item 11 | Sub-issue · Repo · P1 · Must-have · — · Ready | assigned at creation |
| **S0.3** | issue, sub-issue | `docs(docs): record the proxmox capacity, vm size and provisioning path` | E0 (native sub-issue) | `M0 - Preparation` | `type:sub-issue`, `area:docs`, `tier:must-have`, `priority:p0`, `status:blocked` | — | 9; link 10; board item 11 | Sub-issue · Docs · P0 · Must-have · — · Blocked | assigned at creation |
| **S0.4** | issue, sub-issue | `docs(docs): record the lab test roles and the name resolution scheme` | E0 (native sub-issue) | `M0 - Preparation` | `type:sub-issue`, `area:docs`, `tier:must-have`, `priority:p0`, `status:blocked` | — | 9; link 10; board item 11 | Sub-issue · Docs · P0 · Must-have · — · Blocked | assigned at creation |
| **S0.5** | issue, sub-issue | `docs(docs): record the mail relay and test mailbox decision` | E0 (native sub-issue) | `M0 - Preparation` | `type:sub-issue`, `area:docs`, `tier:must-have`, `priority:p0`, `status:blocked` | — | 9; link 10; board item 11 | Sub-issue · Docs · P0 · Must-have · — · Blocked | assigned at creation |
| **S0.6** | issue, sub-issue | `docs(docs): record the checkmk instance and the monitoring scope` | E0 (native sub-issue) | `M0 - Preparation` | `type:sub-issue`, `area:docs`, `tier:must-have`, `priority:p0`, `status:blocked` | — | 9; link 10; board item 11 | Sub-issue · Docs · P0 · Must-have · — · Blocked | assigned at creation |
| **S0.7** | issue, sub-issue | `docs(docs): record the owner's pass over the proposals and the implementation gate` | E0 (native sub-issue) | `M0 - Preparation` | `type:sub-issue`, `area:docs`, `tier:must-have`, `priority:p0`, `status:blocked` | — | 9; link 10; board item 11 | Sub-issue · Docs · P0 · Must-have · — · Blocked | assigned at creation |
| **S1.1** | issue, sub-issue | `chore(host): answer the spike questions sp-01 to sp-20 on a throwaway vm` | E1 (native sub-issue) | `M1 - Host & Firewall` | `type:sub-issue`, `area:host`, `area:docs`, `tier:must-have`, `priority:p0`, `status:blocked` | S0.3, S0.4, S0.7 | 9; link 10; board item 11 | Sub-issue · Host · P0 · Must-have · — · Blocked | assigned at creation |
| **S1.2** | issue, sub-issue | `chore(repo): add the platform file layout and the static gate script` | E1 (native sub-issue) | `M1 - Host & Firewall` | `type:sub-issue`, `area:repo`, `area:tests`, `tier:must-have`, `priority:p0`, `status:blocked` | S0.7, S1.1 | 9; link 10; board item 11 | Sub-issue · Repo · P0 · Must-have · — · Blocked | assigned at creation |
| **S1.3** | issue, sub-issue | `chore(ci): run the static gates and a pr title check on every pull request` | E1 (native sub-issue) | `M1 - Host & Firewall` | `type:sub-issue`, `area:ci`, `tier:must-have`, `priority:p1` | S1.2 | 9; link 10; board item 11 | Sub-issue · CI · P1 · Must-have · — · Backlog | assigned at creation |
| **S1.4** | issue, sub-issue | `feat(host,firewall): build the fcos vm with docker ce and the host-rule firewall stage` | E1 (native sub-issue) | `M1 - Host & Firewall` | `type:sub-issue`, `area:host`, `area:firewall`, `tier:must-have`, `priority:p0`, `status:blocked` | S0.3, S0.4, S1.1, S1.2 | 9; link 10; board item 11 | Sub-issue · Host · P0 · Must-have · — · Blocked | assigned at creation |
| **S1.5** | issue, sub-issue | `feat(firewall,compose): load the docker-user rules in two stages and prove them against a caddy stub` | E1 (native sub-issue) | `M1 - Host & Firewall` | `type:sub-issue`, `area:firewall`, `area:compose`, `tier:must-have`, `priority:p0`, `status:blocked` | S1.4 | 9; link 10; board item 11 | Sub-issue · Firewall · P0 · Must-have · — · Blocked | assigned at creation |
| **S2.1** | issue, sub-issue | `feat(web,compose): run wordpress and mariadb behind caddy with file-based secrets` | E2 (native sub-issue) | `M2 - Web & Mail` | `type:sub-issue`, `area:web`, `area:compose`, `tier:must-have`, `priority:p0`, `status:blocked` | S1.5 | 9; link 10; board item 11 | Sub-issue · Web · P0 · Must-have · — · Blocked | assigned at creation |
| **S2.2** | issue, sub-issue | `feat(mail,compose): run postfix for the single wordpress client and refuse other clients` | E2 (native sub-issue) | `M2 - Web & Mail` | `type:sub-issue`, `area:mail`, `area:compose`, `gate:ac-05`, `tier:must-have`, `priority:p0`, `status:blocked` | S2.1 | 9; link 10; board item 11 | Sub-issue · Mail · P0 · Must-have · AC-05 · Blocked | assigned at creation |
| **S2.3** | issue, sub-issue | `feat(mail,web): send wordpress mail through the external relay and trace it by queue id` | E2 (native sub-issue) | `M2 - Web & Mail` | `type:sub-issue`, `area:mail`, `area:web`, `gate:ac-04`, `tier:must-have`, `priority:p0`, `status:blocked` | S0.5, S2.2 | 9; link 10; board item 11 | Sub-issue · Mail · P0 · Must-have · AC-04 · Blocked | assigned at creation |
| **S3.1** | issue, sub-issue | `feat(logs,proxy): collect web and mail logs in loki and search them in grafana` | E3 (native sub-issue) | `M3 - Logs & Monitoring` | `type:sub-issue`, `area:logs`, `area:proxy`, `gate:ac-02`, `gate:ac-06`, `tier:must-have`, `priority:p0`, `status:blocked` | S1.1, S2.2 | 9; link 10; board item 11 | Sub-issue · Logs · P0 · Must-have · AC-02, AC-06 · Blocked | assigned at creation |
| **S3.2** | issue, sub-issue | `test(tests): prove automatic certificate renewal in a controlled trial` | E3 (native sub-issue) | `M3 - Logs & Monitoring` | `type:sub-issue`, `area:tests`, `area:proxy`, `gate:ac-03`, `tier:must-have`, `priority:p0` | S3.1 | 9; link 10; board item 11 | Sub-issue · Tests · P0 · Must-have · AC-03 · Backlog | assigned at creation |
| **S3.3** | issue, sub-issue | `feat(monitoring): alert in checkmk when a service stops and clear on recovery` | E3 (native sub-issue) | `M3 - Logs & Monitoring` | `type:sub-issue`, `area:monitoring`, `area:host`, `gate:ac-08`, `tier:must-have`, `priority:p0`, `status:blocked` | S0.6, S1.1, S3.1 | 9; link 10; board item 11 | Sub-issue · Monitoring · P0 · Must-have · AC-08 · Blocked | assigned at creation |
| **S5.1** | issue, sub-issue | `test(tests): run the firewall negative tests in full with all services up` | E5 (native sub-issue) | `v0.1.0 - Release Gate` | `type:sub-issue`, `area:tests`, `area:firewall`, `gate:ac-07`, `tier:must-have`, `priority:p0`, `status:blocked` | S3.3 | 9; link 10; board item 11 | Sub-issue · Tests · P0 · Must-have · AC-07 · Blocked | assigned at creation |
| **S5.2** | issue, sub-issue | `test(tests): prove services and firewall rules after a docker and a vm restart` | E5 (native sub-issue) | `v0.1.0 - Release Gate` | `type:sub-issue`, `area:tests`, `area:host`, `gate:ac-09`, `tier:must-have`, `priority:p0` | S3.2, S5.1 | 9; link 10; board item 11 | Sub-issue · Tests · P0 · Must-have · AC-09 · Backlog | assigned at creation |
| **S5.3** | issue, sub-issue | `test(tests): rebuild the vm from the repository and run the final acceptance pass` | E5 (native sub-issue) | `v0.1.0 - Release Gate` | `type:sub-issue`, `area:tests`, `area:host`, `gate:ac-01`, `tier:must-have`, `priority:p0`, `status:blocked` | S2.3 *(proposed edge, point 14, undecided)*, S5.2 | 9; link 10; board item 11 | Sub-issue · Tests · P0 · Must-have · AC-01 · Blocked | assigned at creation |
| **S5.4** | issue, sub-issue | `release(repo): cut 0.1.0` | E5 (native sub-issue) | `v0.1.0 - Release Gate` | `type:sub-issue`, `area:repo`, `area:release`, `tier:must-have`, `priority:p0`, `status:blocked` | S5.3 | 9; link 10; board item 11 | Sub-issue · Repo · P0 · Must-have · — · Blocked | assigned at creation |
| **S6.1** | issue, sub-issue | `feat(firewall): add the proxmox firewall layer with its own negative tests` | E6 (native sub-issue) | `M1 - Host & Firewall` | `type:sub-issue`, `area:firewall`, `tier:extra`, `priority:p2`, `status:blocked` | S5.3, unless the owner decides otherwise | 9; link 10; board item 11 | Sub-issue · Firewall · P2 · Extra · — · Blocked | assigned at creation |
| **S6.2** | issue, sub-issue | `feat(firewall,compose): prove docker network isolation and limit container egress` | E6 (native sub-issue) | `M1 - Host & Firewall` | `type:sub-issue`, `area:firewall`, `area:compose`, `tier:extra`, `priority:p2`, `status:blocked` | S5.3, unless the owner decides otherwise | 9; link 10; board item 11 | Sub-issue · Firewall · P2 · Extra · — · Blocked | assigned at creation |
| **S4.1** | issue, sub-issue | `feat(backup): back up and restore the stack with a measured restore trial` | E4 (native sub-issue) | `M4 - Backup, Restore & Update` | `type:sub-issue`, `area:backup`, `gate:ac-10`, `tier:optional`, `priority:p2`, `status:blocked` | S5.3, unless the owner decides otherwise | 9; link 10; board item 11 | Sub-issue · Backup · P2 · Optional · AC-10 · Blocked | assigned at creation |
| **S4.2** | issue, sub-issue | `feat(backup): add the controlled update procedure with a recorded trial` | E4 (native sub-issue) | `M4 - Backup, Restore & Update` | `type:sub-issue`, `area:backup`, `tier:optional`, `priority:p2`, `status:blocked` | S4.1 *(proposed edge, point 14, undecided)*, S5.3 (S5.3 unless the owner decides otherwise) | 9; link 10; board item 11 | Sub-issue · Backup · P2 · Optional · — · Blocked | assigned at creation |
| COMMIT-0 | commit on `main` | `docs: add architecture, diagrams, preparation package and agent tooling (#<S0.1>)`, no trailer; content = the frozen manifest of § 22.3 | S0.1 | — | — | S0.1 created; the scan of step 1 | 6 | — | assigned at creation (SHA) |
| PR-S0.2 | pull request, **not merged** | `chore(repo): add issue and pr templates, codeowners and dependabot (#<S0.2>)`, branch `chore/repo-github-scaffold`, body `Closes #<S0.2>`, no attribution line | S0.2 | — | — | COMMIT-0 pushed; S0.2 exists | 12 | Status of S0.2: In Review | assigned at creation |
| S0.C3 | issue, sub-issue (conditional) | `docs: add the licence chosen by the owner` | E0 | `M0 - Preparation` | proposed in r6, not in r5: `type:sub-issue`, `area:docs`, `tier:must-have`, `priority:p1` | the owner's licence answer | created only if the answer asks for it after publication | — | assigned at creation, if created |
| S0.C4 | issue, sub-issue (conditional) | `chore(repo): add the lab-access agent tooling after its closeout, review and scan` (the words after "tooling" are the steward's proposal, not an owner condition, § 7) | E0 | `M0 - Preparation` | `type:sub-issue`, `area:repo`, `priority:p2`, `status:blocked`; `tier:` per the owner's answer | the owner's later decision (§ 21.4; option C chosen, D-49) | not in Stage 2; created only when the owner asks for the publication pull request | — | assigned at creation, if created |

Row counts: 1 repository, 35 labels, 6 milestones, 1 board, 1 field row, 34 issues (U1, E0 … E6, 26 sub-issues; S0.1 among them), 1 commit, 1 pull request, 2 conditional sub-issues that exist only on the owner's answer. S0.C3 appears in the r5 table without labels; the labels shown here for it are an r6 proposal.

## 20. Dependency check

**Method.** A script written for this task, kept outside the repository, parses this file and nothing else: the table of § 7, the `Depends on` line of each of the 26 sub-issue paragraphs of § 9 (text in parentheses is ignored, so a note such as "S2.3 until r4" is not read as an edge), the three epic-level dependency lines (E3, E4, E6), the blocked rows of § 11 and the label table of § 4. It builds the graph and runs the checks below on the text as it stands in r6, and it generated the table of § 19. No `gh` command, no network and no git write was used. The script is not a repository file; the checks are repeatable by anyone who parses the same sections.

**Mutation test.** To show that the checks can fail, the script was also run on five altered copies of this file. Removing S2.3 from S5.3 failed the AC-04 check; pointing S3.1 at S2.3 failed three D-48 checks; adding S2.1 to S1.5 failed the cycle and step-order checks; making S0.1 depend on S0.2 failed the cycle check; giving S5.2 a second `gate:` label failed the "exactly one claimant" check. The unaltered file passes all of them.

**Result on r6.**

| Check | Result |
|---|---|
| Counts | 1 umbrella, 7 epics, 26 sub-issues |
| Every epic and sub-issue has a parent and a milestone; U1 has no milestone | pass; each sub-issue's milestone equals its epic's |
| Milestone sizes | M0 8 · M1 9 · M2 4 · M3 4 · M4 3 · v0.1.0 5 · none 1 (U1) |
| Dependency edges | 33 between sub-issues, 3 at epic level (E3 → S2.2; E4 → S5.3; E6 → S5.3), every target a known issue |
| Cycles | none, in the graph of sub-issue edges plus "an epic waits for its children" plus "U1 waits for the epics" |
| Order against implementation-plan § 3 | no sub-issue depends on one of a later step (S5.3, step D9, depends on S2.3, step D6: earlier, allowed) |
| Statuses at creation | 1 `Done`, 1 `Ready`, 2 `In Progress`, 8 `Backlog`, 22 `Blocked`, as § 7 states |
| Blocked set | the 22 `Blocked` issues of § 7 are exactly the rows of § 11 |
| Titles | every title with ` (#1)` appended matches the subject pattern of `.claude/hooks/check-commit-format.sh`; the first scope of each title equals the first `area:` label |
| Labels | 35; every label an issue uses exists |
| Priority and tier | no EXTRA or OPTIONAL issue is `priority:p0` |

**D-48.** S3.1 depends on exactly S2.2 and S1.1. S2.3 is not an ancestor of S3.1, S3.2, S3.3, S5.1 or S5.2, and neither S3.2 nor S5.1 has a direct dependency on it. S3.1 does not inherit S0.5 through S2.3. D-33 as a whole stays a proposal.

**AC-04 stays required for the release.** In r5 the requirement was carried by criteria alone: the E2 epic ("AC-04 and AC-05 are marked passed"), the E5 table (AC-01 … AC-09), the final pass of S5.3 ("every evidence file AC-01 … AC-09 has a PASS section"), S5.4 ("the table in E5 is complete") and the umbrella's success criteria. As edges, nothing ordered S2.3 before S5.3: with S3.1 cut loose from S2.3 by D-48, a reader of the dependency lines could conclude that the release does not wait for it. r6 therefore makes the edge explicit, **S5.3 depends on S2.3**, and S2.3 is now an ancestor of S5.3 and S5.4. It adds no new wait in practice (S5.3 already requires the AC-04 evidence) and is not a dependency of S3.2 or S5.1, which D-48 forbids. It is the steward's proposal (§ 15 point 14); dropping it is a one-line edit and the criteria still carry the requirement. A second added edge, **S4.2 depends on S4.1**, is stated because the update trial needs "a backup before"; S4.1 → S5.3 and S4.2 → S5.3 restate the rule of epic E4 per issue.

**If the owner drops a point-14 edge** (r9; the two edges are **proposed and undecided**, § 15 point 14; every place that carries them below is marked as proposed). *Dropping S5.3 → S2.3* changes: the `Depends on` line of S5.3 in § 9 (S2.3 removed, S5.2 stays); the Depends-on cell of S5.3 in § 19; the "Blocked by" line of the S5.3 body and the "Unblocks" line of the S2.3 body; the native dependency (S5.3 blocked by S2.3), which Stage 2 would not create; the sentence in § 11 that calls the requirement "also a dependency line"; the AC-04 row of the table below ("required before S5.3"); and the edge counts. The release would still wait for AC-04 through the E2 criteria, the E5 table, the PASS section demanded by S5.3 and S5.4's complete table, but nothing in the sub-issue graph would order S2.3 before S5.3. *Dropping S4.2 → S4.1* changes: the `Depends on` line of S4.2 in § 9 (S4.1 removed, S5.3 stays); the Depends-on cell of S4.2 in § 19; the Dependencies line of the S4.2 body and the Unblocks line of the S4.1 body; the native dependency (S4.2 blocked by S4.1), which would not be created; and the edge counts. The update trial would still name "a backup before" in its criteria, and nothing in the graph would order it after the restore trial. Milestones, labels, statuses at creation and issue counts are the same either way; the Stage 2 package has the two edges in separate, marked lines, so a drop is a two-line edit per edge.

**Acceptance checks.** Each of AC-01 … AC-10 is claimed by exactly one sub-issue, in the step where [implementation-plan.md](implementation-plan.md) § 3 lets it claim; all claimants of AC-01 … AC-09 are MUST HAVE; AC-10 is claimed only under E4; no epic and not the umbrella carries a `gate:` label. Partial results (AC-07 at S1.5, AC-02 at S2.1) carry no label.

| Check | Claimed by | Step | Evidence file (implementation-plan § 5) | Also touched |
|---|---|---|---|---|
| AC-01 Rebuild | S5.3 | D9 | `docs/evidence/ac-01-rebuild.md` | Docker CE proof block partial in S1.4 |
| AC-02 HTTPS | S3.1 | D7 | `docs/evidence/ac-02-https.md` | partial in S2.1; re-run in S5.2 and S5.3 |
| AC-03 Certificate lifecycle | S3.2 | D7 | `docs/evidence/ac-03-cert-renewal.md` | trial ends before S5.2 starts |
| AC-04 Mail | S2.3 | D6 | `docs/evidence/ac-04-mail.md` | required before S5.3 (the edge above) |
| AC-05 Relay protection | S2.2 | D6 | `docs/evidence/ac-05-relay-refusal.md` | re-run in S2.3 |
| AC-06 Log search | S3.1 | D7 | `docs/evidence/ac-06-log-search.md` | queue-ID search in S5.3 (D-48) |
| AC-07 Firewall | S5.1 | D9 | `docs/evidence/ac-07-firewall.md` | partial in S1.5; EXTRA sections in S6.1, S6.2 |
| AC-08 Monitoring | S3.3 | D8 | `docs/evidence/ac-08-monitoring.md` | — |
| AC-09 Restart | S5.2 | D9 | `docs/evidence/ac-09-restart.md` | — |
| AC-10 Restore (OPTIONAL) | S4.1 | D11 | `docs/evidence/ac-10-restore.md` | — |

AC-05 and AC-07 are unchanged: no criterion of S1.5, S2.2, S2.3, S5.1, S6.1 or S6.2 was edited in r6.

**Limits of the check.** It tests structure, not design. It does not read scheduling notes that are not dependencies (the D-48 notes on S2.3 and S3.2, the "trial ends before S5.2 starts" criterion), and it does not decide whether a dependency is the right one. The blocked IDs of § 11 are owner answers, not edges. S0.1 depends on the publication gate, which is not an issue. The check passing is a statement about this text; it is not a review and not an approval.

## 21. Outstanding publication decisions

For each decision: concrete options, **one recommendation**, a short rationale, and what changes in this plan if the owner chooses otherwise. None of them is adopted by this file. *(r8: § 21.4 is answered by the owner, D-49; its text stays as the record of the question. The other items are unchanged and open.)* A recommendation is the steward's; the plan must still read correctly under the other options, and the last paragraph of each item says how. The order in which the owner must answer is § 21.8. *(r9, 2026-11-16: items 2 to 6 of § 21.8 are answered by the owner, D-50 … D-53 and the approved proposals recorded in decision-log r8; each affected subsection below carries a dated note. The option tables and recommendations stay as the record of the questions. **The steward's recommendations I2 (§ 21.2) and the "owner to confirm" wording on the 28 files (§ 21.3) are not the decisions**; the decisions are in the notes. Item 7, the go-ahead, is open.)*

### 21.1 Licence (OQ-22)

| Option | Effect |
|---|---|
| L1. No licence, none later unless asked | the default for a public repository: others may view and fork it on GitHub, and no other right is granted. S0.C3 is never created |
| L2. No licence in the bootstrap commit; the owner decides later | as L1 now; S0.C3 is created if and when the owner chooses a licence |
| L3. A licence in the bootstrap commit | one more file in the commit (S0.1's criteria and the manifest of § 22.3 gain it). The owner names the licence; the steward does not choose it or write its text on its own initiative (agent definition, "Ask the owner first") |
| L4. One licence for code and configuration, another for documents | two files and two choices; more than a homework needs |

**Recommendation: L2.** Rationale: nothing in the scope lock needs a licence and OQ-22 blocks nothing; the reference repository has none; a licence cannot be recalled from copies already taken, while adding one later is a one-file pull request. The records also leave open the origin of some tracked material: [open-questions.md](open-questions.md) CQ-08 says that `excalidraw-diagram` states no origin or licence, and a blanket licence would claim rights over files whose provenance is not established. **If the owner chooses otherwise:** L1 removes S0.C3 from § 7; L3 adds one file to § 21.3 and one criterion to S0.1 and creates no S0.C3; L4 does the same with two files.

*Answered on 2026-11-16: L2 (D-53).* No project `LICENSE` file is added now; existing third-party licence and attribution obligations are preserved; OQ-22 stays open and blocks nothing; S0.C3 is not created now (§ 7). The steward's recommendation was L2, so it was adopted. D-53 grants no reuse right and claims none over material whose origin is not established (CQ-08).

### 21.2 Commit author address (OQ-21) and the identity of squash commits

The bootstrap commit carries the repo-local name and address, and both become public with the push (D-08). The name is published too; OQ-21 asks only about the address.

| Option | Effect |
|---|---|
| I1. Publish the repo-local address as it is | permanent in the public history and in the commit API. If the account's setting blocks pushes that expose an address, the push is rejected: stop and ask (step 6 of § 12) |
| I2. The owner switches the repo-local address to the GitHub-provided no-reply form before the first commit | the address is not exposed; the name is unchanged. The owner runs the change; the steward never does (mission § 2.1). The steward does not know the string and does not guess it |
| I3. As I2, and a different public name | the owner's choice; it changes what the name field of every commit shows, not the plan |

Squash merges made on GitHub are a separate matter (§ 12, "Commit identity"): such a commit is authored with the account's own identity and its email-privacy setting, not with the repo-local one (known GitHub behaviour, not observed here). **Recommendation: I2.** Rationale: the address is the one part GitHub offers a private form for; the account setting that keeps the real address private also governs the squash commits made later, so `main` then carries one form of address instead of two; the commit rule keeps the name as the only attribution. **If the owner chooses otherwise:** with I1 nothing in the plan changes, but the scan of § 22.3 records that the address is intended to be public; with I3 the same, plus the name check of the scan is run against the new name.

*Answered on 2026-11-16: I1 (D-52).* The owner approved the repo-local name and address appearing in public commit metadata as they are, configured for this repository only; a GitHub-provided no-reply address is not required. **The steward's recommendation, I2, was not adopted.** No value is written here or anywhere in the Stage 2 package (D-08): step 6 compares the repo-local identity with the owner's answer without printing it. The address is permanent in the public history once pushed. Account privacy settings are not changed; if a setting rejects the push, the specific blocker is reported (§ 12 step 6). The identity of squash merges made on GitHub is **not decided** (§ 15 point 6). OQ-21 is closed by D-52.

### 21.3 What the bootstrap commit contains

Counts are from the listing of `git ls-files -o --exclude-standard` on 2026-11-16 (08:07–08:13 CET, reported by the orchestrator session; the steward re-ran the total and the groups below at 08:15 CET and got the same figures, and the groups are listed from that run). Before the change the listing held **161** paths, of which **66** were the excluded group (61 paths under `lab-agent/`, 6 of them symbolic links under `lab-agent/tests/stubs/`, plus 5 other paths). After D-49 the group is excluded by `.gitignore` and the listing holds **95** paths. It is a listing, not the Stage 2 manifest: the manifest and its hashes are made by § 22.3 (§ 22.2). The earlier counts of this section (154 paths, 59 in the group) were from 06:10 and are superseded.

| Group | Paths | Proposed | Note |
|---|---|---|---|
| Root documents: `README.md` (Hungarian), `AGENTS.md`, `CLAUDE.md`, `.gitignore` | 4 | in | since D-49 `AGENTS.md` and `CLAUDE.md` name none of the excluded paths and no launcher name; they keep a general safety instruction about local, untracked lab tooling, which is intended (reported by the orchestrator session, § 21.4). `.gitignore` carries the six exact paths and `/CLAUDE.local.md` |
| `docs/architecture.md`, `docs/alternatives/swarm.md` | 2 | in | `README.md` and these are the Hungarian documents (D-12, D-46) |
| `docs/.prepare/**`, including `delegation/` | 14 | in | the mission publishes it unless the owner says otherwise; each document carries its own status |
| `diagrams/**`: seven diagrams in three formats, four generators, `SOURCES.txt` | 26 | in | regenerated per D-44; the label of diagram 03 changed after that without a recorded author (decision-log § 2, "Completed correction") |
| `.claude/rules/` (8), `.claude/references/` (1), `.claude/skills/` (5 skills, 7 files), `.claude/agents/` (`github-steward`, `repo-visibility-manager`), `.claude/hooks/check-commit-format.sh`, `.claude/settings.json` | 20 | in | `settings.json` holds only the commit-format hook since D-49; the guard-hook registration, the `mcp__pve__*` permissions and the two `Read(~/…)` deny entries were moved to the untracked `.claude/settings.local.json` (reported by the orchestrator session, § 21.4) |
| `.claude/commands/` (26 files) and two agent definitions `prp-quality-agent`, `prp-validation-gate-agent` | 28 | **owner to confirm** | D-45 does not name them. The tracked `.claude/references/herdr-orchestration.md` links to six of the command files and `upstream-claim-verify` names `prp-quality-agent`, so excluding them would break links in tracked policy files. File names only were looked at; their content was not read for this task |
| `.agents/plans/github-bootstrap-mission.md` | 1 | in | its "Current state" section describes an earlier scan (readiness-report § 10b item 9) |
| Lab-agent workstream: `lab-agent/**` (61 paths, 55 regular files and 6 symbolic links under `lab-agent/tests/stubs/`: the figures of the listing of 08:07–08:13; two test files were added to the directory later that day, 63 paths, which changes no listing because the group is excluded), `.mcp.json`, `.claude/agents/pve-lab.md`, `.claude/hooks/pve-guard.py`, `.agents/plans/proxmox-admin-agent-plan.md`, `.agents/plans/proxmox-admin-agent-governance.diff` | 0 of 66 | **out (D-49)** | excluded from the initial publication by six exact paths in `.gitignore` (no wildcard for the two plan files); the files stay on disk. A later inclusion needs a separate owner decision and a separate pull request |

Sum of the groups in the manifest: 4 + 2 + 14 + 26 + 20 + 28 + 1 = **95**. With the excluded group the listing held 95 + 66 = 161 before the change. The 28 command and agent files remain "owner to confirm" (item 2 of § 21.8): if the owner excludes them the manifest has 67 paths and the tracked links to them must be reworded.

**Stays out**, by `.gitignore` or by not existing: the lab-administration group of D-49 (the six exact paths, 66 paths in the listing), `CLAUDE.local.md`, `HANDOFF.md`, `.handoffs/`, `.claude/settings.local.json`, `.claude/worktrees/`, rendered `*.ign` (none exist), `secrets/`, `.env*`, `*.pem`, `*.key`, caches, and the ten generic skills, the copy under `.agents/skills/` and the `ai-engineer-doc-architect` prompt of D-45. No platform configuration exists: no `butane/`, `compose.yaml`, `Caddyfile`, `firewall/`, `scripts/`, `tests/`, `docs/evidence/`.

**Recommendation:** the proposed column as it stands; keep the 28 command and agent files, because tracked policy links to them; and ask the owner for one yes or no on `docs/.prepare/` being published (the mission's default is yes). **If the owner chooses otherwise:** an excluded group is added to `.gitignore` (by the owner or at the owner's request), and S0.1's criteria and the manifest of § 22.3 follow; no issue changes.

*Answered on 2026-11-16 (D-50).* The 28 command and agent files are **kept** (the "owner to confirm" in the table above is resolved: in); `docs/.prepare/` is **included in the initial publication**; OQ-35 is **not** a prerequisite for the initial publication and nothing is translated (D-46). The 95-path listing is the starting point, subject to the corrections the owner authorized on 2026-11-16 and to the verification of the final manifest (§ 22.3); the Stage 2 manifest, not this table, fixes the file set. References to the repository's owner and name may stand in the five candidate files identified on 2026-11-16 (D-06); there is no exception for personal or lab-private data. No licence file is added (D-53).

### 21.4 The Proxmox lab-agent workstream: in, later, or out

**Answered on 2026-11-16 with option C (D-49, [decision-log.md](decision-log.md) r7).** The lab-administration tooling is **excluded from the initial publication**. Including it later requires a separate owner decision and a separate pull request. The answer is about the scope of the initial publication only: both owner gates stay closed, § 5 of the decision log is unchanged, no authorization for the workstream is recorded, no result of it is accepted, the owner set no condition for a later inclusion, and D-20 is not amended (it stays a 15-scope proposal, § 21.6). Items 2 to 7 of § 21.8 are still open. *(r9: that was the state when D-49 was recorded. D-20 is approved since (decision-log r8), and items 2 to 6 are answered; item 7, the go-ahead, is open.)* Everything from the next paragraph down to and including the recommendation is **the record of how the question was put on 2026-11-16 before the answer**; it is kept as written, apart from the lines marked "r8". The part that describes the present state is the box "Carried out on 2026-11-16".

`lab-agent/**` (about 45 files in the packet, 54 paths by the dry run: the count is provisional), `.mcp.json`, `.claude/agents/pve-lab.md`, `.claude/hooks/pve-guard.py` and two plan files under `.agents/plans/` are a separate workstream: supporting tooling for the owner's lab, **not a homework deliverable**. No decision record names it, no authorization for it is recorded in this package (`AGENTS.md`, "Safety": present but not authorized), and it fails question 1 of the litmus test in `product-vision.md` (it is not a row of the scope lock). Whether it belongs in the public repository is the owner's decision. The content of `lab-agent/**` was not read or scanned for this task. *(r8: the sentence "No decision record names it" was true when it was written; D-49 now names it, and the other statements of this paragraph are the record of the question. The group, as D-49 lists it, is `lab-agent/`, `.mcp.json`, `.claude/agents/pve-lab.md`, `.claude/hooks/pve-guard.py`, `.agents/plans/proxmox-admin-agent-plan.md` and `.agents/plans/proxmox-admin-agent-governance.diff`.)*

**What else refers to it** (found by searching the files outside `lab-agent/`): `AGENTS.md` (the lab-access and guard-hook bullets of "Safety"), `.claude/settings.json` (a `PreToolUse` hook on every shell command and on `mcp__pve__*`, registered with `onFailure: block`; many `mcp__pve__*` entries under `permissions`; two `Read(~/…)` deny entries that name a private configuration directory and a key-file pattern), `.mcp.json` (launches a script under `lab-agent/`), and the two plan files. `CLAUDE.md` has its own guard-hook bullet ("Safety pointer") and points to `AGENTS.md` for the rest. Since 2026-11-16 four documents of `docs/.prepare/` also name or describe the set (source-register SR-31, readiness-report § 10d, a dated note in core-context § 5, and the Purpose of the index, which describes it without paths), and so does this plan (§ 21, § 22). Under options B, C and D they describe files that are not in the repository. They stay true as records of the working tree; whether they are published as they are belongs to decision 2 of § 21.8. *(r8: option C was chosen, so these documents describe files that are not in the initial publication. D-49 is itself one of the records that name the group; the question of publishing them as they are is still item 2 of § 21.8 and is open.)*

> **Consequence for every option except A.** `.claude/settings.json` is a tracked file that calls `pve-guard.py` and fails closed. In a clone without that script every shell command of a Claude Code session would be blocked. So excluding the workstream is not only a `.gitignore` change: the hook registration, the `mcp__pve__*` permissions and the two deny entries must leave the tracked `settings.json` (for example into the untracked `.claude/settings.local.json`; that hooks and permissions of both files then apply together is an assumption to be verified by the workstream, not by this plan), and the lab-agent lines of `AGENTS.md` and the guard-hook bullet of `CLAUDE.md` ("Safety pointer") must be reworded. Editing hooks, settings, `AGENTS.md` and `CLAUDE.md` needs the owner's say (`AGENTS.md`, "Stop and ask"). The steward writes none of them; the proposed text goes to the orchestrator. *(r8: this box describes the state earlier on 2026-11-16, before the change, in the present tense of the time it was written; what was done is in the next box.)*

> **Carried out on 2026-11-16** (reported by the orchestrator session at the owner's request; the steward did not observe these steps and did not re-read `.claude/settings.json`, `AGENTS.md` or `CLAUDE.md` in full; a case-insensitive search of the three files for `lab-agent` and `pve` at 08:15 CET found no hit):
> - `.gitignore` lists the six exact paths of the group (no wildcard for the two plan files) and `/CLAUDE.local.md`. The listing of untracked, non-ignored paths fell from 161 to 95 (§ 21.3).
> - `.claude/settings.json` holds only the commit-format hook. The guard-hook registration, every `mcp__pve__*` permission entry and the two `Read(~/…)` deny entries were moved verbatim to the untracked `.claude/settings.local.json`. Nothing was widened; whether `mcp__pve__*` is allowed for every session stays the owner's open question.
> - `AGENTS.md` ("Safety") and `CLAUDE.md` name no excluded path and no launcher name any more. They keep a general instruction: lab tooling may exist in a working copy as local, untracked files, it is not authorized, and nothing of it is to be run, started, applied or repaired. That is intended and is not a dangling reference.
> - **The assumption named in the box above** (hooks and permissions of both settings files apply together) **was checked by the orchestrator session**, not by this plan and not by the steward: in an isolated harness check on Claude Code 2.1.325 with no MCP server (a hook registered only in the local settings fired together with the project hook, its deny blocked, a local deny rule applied), and by a fresh-session guard probe in this checkout, in which the same harmless probe command was blocked by the guard before and after the move. The same session observed in isolation that a hook with `onFailure: "block"` blocks when it exits 1, and that a hook whose script file is missing blocks every shell command; the second is what a clone with the old tracked registration and no guard script would have met.
> - The commit-format hook keeps its project-directory form (`bash "${CLAUDE_PROJECT_DIR}/.claude/hooks/check-commit-format.sh"`); the owner approved retaining it on 2026-11-16. This is not a decision-log entry. Review note b of § 16 and the paragraph "Where commits run" in § 12 describe the earlier relative-path form; the steward still commits from the repository root and checks the message against the commit rule itself.

*(r8: the table is the record of the options put to the owner; the owner chose C. In row C the words "after its closeout, review and scan" are the steward's wording of the option, not a condition set by the owner (D-49). The candidate-file counts are those of 06:10 on 2026-11-16: 154 with the group, 95 without it. The listing after the change is in § 21.3.)*

| Option | Candidate files | Scopes and labels | Issue tree | Hook, settings, other files | Scan |
|---|---|---|---|---|---|
| **A.** Publish with the bootstrap commit | 154 | `lab-agent/**` has no scope in `commit-format.md`. A `lab-agent` scope exists only as an unapplied proposal. Using it means amending D-20 to 16 scopes **before step 3**: 16 `area:` labels, 36 labels in all, one more board Area option, the hook's scope list and `commit-format.md` (owner's files). Without it the files have no honest scope | unchanged (1 + 7 + 26); S0.1 covers it, so no issue or pull request ever reviews the workstream on its own | consistent as they are | the 59 paths enter the scan while the tree is still moving; the content has not been scanned; the history cannot be cleaned later without a force-push, which needs the owner |
| **B.** Keep local, excluded by `.gitignore` as D-45 did | 95 | none needed; labels stay 35 | unchanged; no S0.C4 | `settings.json` and `AGENTS.md` change as in the box above; `.gitignore` gains the five path groups | 95 paths |
| **C.** As B for the bootstrap; publish later in its own pull request after its closeout, review and scan | 95 now | as B now. At the later pull request the owner chooses between the `repo` scope and a new `lab-agent` scope (a D-20 amendment, then 36 labels) | unchanged at the bootstrap; conditional sub-issue **S0.C4** is created later, if the owner asks for the pull request (§ 7) | as B now; the later pull request restores the tracked entries | 95 now; the later pull request carries its own scan and its own authorization |
| **D.** A separate repository | 95 | none here | unchanged; none | as B; the other repository is its own publication-gate item: name, visibility, tree, scan | 95 here; a second scan for the other |

All counts in the table are those of 06:10 and are superseded by § 21.3 (161 before, 95 after).

**Recommendation: C** *(r8: the owner's answer of 2026-11-16 is C; this paragraph is the steward's reasoning at the time and is not part of D-49).* Rationale: the workstream is not a deliverable and nothing records it as part of the project; it is being edited now, so no scan of it can be claimed for a tree that will be published; the tests reported for it are reports, not results seen here; no authorization for it is recorded in this package; and publication is the one step that cannot be taken back cleanly, while publishing later costs one pull request. C keeps the choice open without touching the homework tree: B and D close it. **If the owner chooses otherwise:** A needs the scope decision first, one more manifest group and a changed S0.1; B and D never create S0.C4; D adds a second publication-gate item that this plan does not cover. In every case the `settings.json`, `AGENTS.md` and `CLAUDE.md` consequence above must be settled before the final scan.

### 21.5 Bootstrap procedure (D-28)

| Option | Effect |
|---|---|
| P1. One direct push of the bootstrap commit under issue #1, then pull requests only (D-28 as proposed) | the single exception to the branch rule, as the mission and § 12 describe; the contents are reviewed before the push through the frozen manifest and the scan |
| P2. An empty first commit pushed directly, then the bootstrap content as a pull request the owner reviews on GitHub and squash-merges | the direct push carries no content, and the content commit is then authored through the account's identity (assumed GitHub behaviour; the identity problem of § 21.2 then shrinks). Costs: an extra issue and commit; #1 would become "initialise" and S0.1 a second issue; the mission, D-28 and § 12 change; a 95-file first pull request |

**Recommendation: P1.** Rationale: it is what D-28 proposes and the whole plan is built on it (#1, S0.1, step 5 to step 7); the exception is the same size; and the owner's review of the contents happens before anything leaves the machine, at the gate. **If the owner chooses P2:** step 5 creates an "initialise main" issue as #1, S0.1 becomes the second issue and its subject names that number, step 6 pushes an empty commit, and the content arrives as the pull request of S0.1; § 19 is regenerated.

*Answered on 2026-11-16: P1 (D-28, approved as a procedure).* One direct push of the bootstrap commit under #1, then pull requests only. The owner's words: approving the procedure is **not yet permission to create a commit or to push**; that waits for the go-ahead.

**Exact order under P1** (the full table is § 12): 0 freeze, answers in hand, token scopes re-read · 1 final scan and manifest · 2 repository and settings · 3 labels · 4 milestones · 5 issue S0.1, which must be #1 · 6 `git add -A`, staged list and hashes equal to the manifest, commit with the subject of S0.1 and no trailer, remote, push · 7 tick the criteria of #1 with the SHA and close it · 8 board, fields, `Status` options replaced before any item · 9 U1, the epics, the other sub-issues · 10 native links · 10a number pass · 11 board items and fields · 12 the scaffold branch and pull request for S0.2, **not merged** · 13 read-only audit and the run log.

### 21.6 The structural proposals the tree makes public

D-35 proposes that the owner's go-ahead settles these five for the tree. D-48 says that D-33 as a whole stays a proposal and is not approved by that row; the go-ahead is therefore the first approval of D-33, and only for the tree.

| ID | What becomes public | Options | Recommendation | If amended |
|---|---|---|---|---|
| D-20 | 15 scopes → 15 `area:` labels and every issue title | confirm; add or remove a scope (for example `lab-agent`, or one for `scripts/validate.sh`, OQ-34) | **confirm 15**. *(r8)* The 16th scope `lab-agent` applied only under § 21.4 option A, which the owner did not choose (D-49 chose C), so D-20 stays a 15-scope proposal and D-49 does not amend it; a scope for `lab-agent/` is considered only if the owner later decides to include it | labels (35 ± n), § 4, § 19 and affected titles change before step 3; the hook and `commit-format.md` are the owner's |
| D-21 | AC-01 … AC-10 → 10 `gate:` labels, evidence file names | confirm; change the numbering | **confirm** | labels, § 19, § 20 and the E5 table change |
| D-22 | AC-01 … AC-09 gate v0.1.0; AC-10 only if the OPTIONAL tier is delivered | confirm; gate on all ten | **confirm** | AC-10 would move into E5 and the release milestone, and M4 before the gate |
| D-23 | umbrella → epic → sub-issue hierarchy and a board without estimate or score fields | confirm; add fields | **confirm**; add a field only when the owner states a deadline or a scoring rule (OQ-01) | § 5 gains fields |
| D-33 | the order of work; here with the D-48 exception for S3.1 | confirm for the tree; reject or amend | **confirm for the tree, with the D-48 exception** | the Step column, `Depends on` lines and § 20 are regenerated |
| D-35 | the go-ahead settles the five above | confirm the rule; settle each one by name | **settle each by name** in the owner's answer, so that the orchestrator can record it | none |

*Answered on 2026-11-16:* the owner approved **D-20, D-21, D-22, D-23** and **D-33 for the GitHub work tree, subject to the D-48 exception**, each by name, as recorded in decision-log r8 (§ 2, "Proposals of § 3 approved by the owner on 2026-11-16"). The recommendations "confirm" were adopted. Limits: D-33 settles the order the tree shows, **except the two added dependency edges of open point 14 (S5.3 on S2.3, S4.2 on S4.1), which are not decided (D-51)**, and it opens no gate; D-20 added no scope; D-23 adds no estimate or score field. **D-35 is not decided**: the owner named each proposal, so the rule was not needed.

Other items in § 15 and § 11, one line each (r9: answered where marked; the rest is still open):

| Point | Recommendation | Needed for Stage 2? |
|---|---|---|
| 1. Platform scaffold and CI in E0 or in E1 | E1, as r5 (§ 14 row 1). **Answered 2026-11-16, D-51: E1** | yes, as part of the tree |
| 2. E6 keeps M1 or gets a seventh milestone | keep M1; M1 then stays open until E6 is delivered or closed as "not planned". **Answered 2026-11-16, D-51: keep M1** | yes, as part of the tree |
| 3. D-41 and D-42 block the platform sub-issues | no; the criteria are written at outcome level. **Answered 2026-11-16, D-51: no** (neither the technical substance of D-41 and D-42 nor the implementation gate is approved by it) | yes, as part of the tree |
| 4. S1.2 may start before the spike if the inputs are late | no; keep the D-33 order. **Not decided** | no; at the implementation gate |
| 6. Identity of squash commits | § 21.2, I2. **Not decided** (D-52 settles the bootstrap commit only) | yes |
| 7. Who writes the pull requests of S0.3 … S0.7, which edit `docs/.prepare/` | the owner or a session at the owner's request, as the mission bounds it. **Answered 2026-11-16, D-51: the owner or a session the owner assigns** | yes, as part of the tree |
| 14. The two added dependency edges (S5.3 on S2.3, S4.2 on S4.1) | keep both, as § 20 explains. **Not decided; both stay as proposed and go to the owner with the go-ahead request** (§ 20, "If the owner drops a point-14 edge") | yes, as part of the tree |
| 10 … 13, 15 (r6) | § 21.3 to § 21.5, § 20 and § 21.7. Points 10 (D-49), 11 (D-50), 12 (D-52, D-53) and 13 (D-28) are answered; point 15 is a change for the orchestrator | as listed in § 21.8 |
| OQ-35 (which files are bilingual) | not needed before publication; D-46 keeps every file as it is until the owner answers | the owner says whether it is needed |
| OQ-01, OQ-24 | not needed | no |
| Branch protection on `main` | after the first CI run; not in the bootstrap | no |

### 21.7 Changes to files other than this plan

The steward writes only this file. These are proposals for their owners; the exact text is in the GH-6 report, not here.

| File | Change | Why | By |
|---|---|---|---|
| [implementation-plan.md](implementation-plan.md) D2 cell and R-21 | "a root `CLAUDE.md`" becomes an update of the existing root `AGENTS.md` and `CLAUDE.md`. r3 of that plan already carries a dated note (DOC-1) saying the files exist; the cell and R-21 were not changed when this was written | both exist since 2026-11-16 (§ 9, S1.2) | the orchestrator |
| [decision-log.md](decision-log.md) | record the owner's answers of § 21.8 before step 6. *(r8: the answer to item 1 is recorded as D-49, decision-log r7. r9: the answers to items 2 to 6 are recorded in decision-log r8 as D-50 … D-53 and in its approvals table; the go-ahead of item 7 is still to be recorded when it is given.)* | § 12 precondition; D-35 | the orchestrator |
| `.gitignore`, `.claude/settings.json`, `AGENTS.md`, `CLAUDE.md` | **done on 2026-11-16** (reported by the orchestrator session, § 21.4): the six paths and `/CLAUDE.local.md` in `.gitignore`; `settings.json` holds only the commit-format hook; `AGENTS.md` and `CLAUDE.md` name no excluded path | D-49 (option C) | the orchestrator session, at the owner's request |
| `.agents/plans/github-bootstrap-mission.md` | "Current state" and the file list of the first commit | stale after the files above | the steward in Stage 2, or the orchestrator now |
| [README.md](README.md) of `docs/.prepare/` | revision and hash of this plan | the index belongs to the documentation worker | that worker |

### 21.8 The smallest list of owner decisions that Stage 2 needs, in order

| # | Decision | Recommendation | Why in this place |
|---|---|---|---|
| 1 | The lab-agent workstream: A, B, C or D (§ 21.4) | C | **Answered on 2026-11-16: C (D-49).** It fixed the file set (95 paths in the listing, § 21.3), `.gitignore`, `settings.json`, `AGENTS.md` and `CLAUDE.md`; D-20 gets no 16th scope |
| 2 | The contents of the bootstrap commit (§ 21.3): confirm the groups; the 28 command and agent files; whether `docs/.prepare/` is published; whether OQ-35 is needed before publication | as proposed; keep the 28; yes; no | **Answered on 2026-11-16 (D-50): the 28 files are kept; `docs/.prepare/` is included in the initial publication; OQ-35 is not a prerequisite.** The 95-path candidate set is the starting point, subject to the authorized corrections and the final manifest. Originally: it fixes the manifest the final scan hashes. Item 1 no longer moves it; **this item can still change the file set**: excluding the 28 command and agent files leaves 67 paths and requires rewording the tracked links to them, and not publishing `docs/.prepare/` removes 14 paths and every link into it from the other tracked files. A bilingual decision (OQ-35) could add or change files |
| 3 | The structural proposals and the tree choices (§ 21.6): D-20, D-21, D-22, D-23, D-33 with the D-48 exception, each by name; open points 1, 2, 3, 7 and 14 | confirm all as recommended | **Answered on 2026-11-16, in part:** D-20, D-21, D-22, D-23 and D-33 (for the tree, subject to D-48) are approved by name; points 1, 2, 3 and 7 are answered as the plan proposes (D-51). **Point 14 is not decided** and goes to the owner with the go-ahead request; D-35 is not decided. Originally: they change labels, titles and dependencies, so before step 3 |
| 4 | The commit author address (§ 21.2) | I2, done by the owner before step 6 | **Answered on 2026-11-16 (D-52): I1, the repo-local name and address as they are. The recommendation I2 was not adopted.** No value is written. The identity of squash merges is not decided. Originally: independent of 1–3, but it must precede the first commit |
| 5 | The licence (§ 21.1) | L2 | **Answered on 2026-11-16 (D-53): L2, deferred; no `LICENSE` now.** Originally: independent; settled before step 6 so the manifest is final |
| 6 | The first-commit exception and the procedure (§ 21.5) | P1 | **Answered on 2026-11-16 (D-28): P1 approved as a procedure; "not yet permission to create a commit or to push".** Originally: the mission requires the owner's explicit agreement |
| 7 | The go-ahead, after seeing the final scan of § 22.3, the tree, and the settings, labels, milestones and board of §§ 3–6 | — | the publication gate itself; it is never implied by 1–6 |

*(r9: rows 2 to 6 are answered as marked in the table; **row 7, the go-ahead, is open and is never implied by 1–6**; point 14 of § 15 goes to the owner with that request.)* Originally: rows 2 to 7 are open and keep their recommendations as recommendations. Row 3 (the structural proposals) and row 5 (the licence) can change the file set or the tree as well: a licence adds one file (§ 21.1, L3), and an amended structural proposal changes labels and titles before step 3. Rows 4, 6 and 7 do not change the file set.

Not needed for Stage 2: the implementation gate, the open questions that do not touch publication (OQ-01 to OQ-20 and OQ-24 … OQ-34), branch protection and the board views. Once 1–6 are answered the orchestrator records them (§ 21.7) and the steward runs step 0.

## 22. Publication hygiene

### 22.0 What this section claims

Nothing here establishes that the tree is ready to publish. The tree changes: other sessions write in this checkout (in r6 two of them in the lab-agent workstream, which D-49 has since excluded from the initial publication). Every count in this section is a snapshot with a time. A scan result belongs to the snapshot it was taken on and to no other. **Publication readiness: not established.**

The records give three earlier figures, and none is a scan of the present snapshot: 220 paths (2026-11-14, before D-45), 91 paths (after D-45), and 94 paths (2026-11-16, about 04:22, the orchestrator's mechanical check in [readiness-report.md](readiness-report.md) § 10b, which that report says is not the steward's Stage 2 scan).

### 22.1 Preliminary scan of the present snapshot — reported by the orchestrator

**This is the orchestrator's result, recorded as reported (task GH-6b); the steward did not run it and did not verify it.** It is a pattern scan of a changing tree and **is not publication evidence**. It does not replace the final scan of § 22.3, which runs after the contents and the snapshot are settled.

| Field | Value as reported |
|---|---|
| Run by | the orchestrator session, on 2026-11-16 at 06:10, with a script over the read-only dry-run listing |
| Snapshot | 154 candidate paths; content snapshot aggregate `24e3d0981e7c3d9c` (SHA-256 over the per-file SHA-256 list). This agrees with the steward's dry-run count of § 22.2 |
| Scope | 147 text files scanned; 7 PNG files **not** text-scanned. Includes `lab-agent/**` (54 paths), as a pattern scan and not a reading of every file |
| By area | `.agents/plans` 3 · `.claude/agents` 5 · `.claude/commands` 26 · `.claude/hooks` 2 · `.claude/references` 1 · `.claude/rules` 8 · `.claude/settings.json` 1 · `.claude/skills` 7 · `.gitignore` 1 · `.mcp.json` 1 · `AGENTS.md` 1 · `CLAUDE.md` 1 · `README.md` 1 · `diagrams` 26 · `docs/.prepare` 14 · `docs/alternatives` 1 · `docs/architecture.md` 1 · `lab-agent` 54 (sum 154) |
| Zero hits | files of the never-publish list (handoff files, local settings, rendered Ignition, key and env files); mail addresses outside the allow-list (not counted, as the orchestrator states: example and test domains, the Proxmox realm suffixes of the form user at pve or pam, GitHub's no-reply form, and the vendor no-reply address that the commit rule quotes as a forbidden trailer; the final scan classifies them under its own check 4); absolute home paths; the local user and host name; the repo-local git identity; the former working name |
| Pattern hits, triaged with values masked, none judged a real secret | credentials-in-URL: 1 (the rule text that forbids the pattern) · token-or-key patterns: 24 hits in 10 files, and public-key patterns: 2 hits in 2 files (redaction regexes, rule and plan prose, placeholder keys, test fixture values under `lab-agent/tests` including the stub token value) · UUID-shaped values: 7 (lab-agent test stubs) · private-range addresses: 10 hits in 4 files (an illustrative firewall rule in diagram 03: generator, `.excalidraw`, `.svg`; sanitizer fixtures in one lab-agent test) |
| To confirm in the final scan | that every fixture secret is synthetic; the pixel content of the 7 PNG files; a token-ID-shaped name in the lab-agent plan's proposed decision text (flagged by the documentation worker, unjudged) |
| Changed after it, as far as known at 06:26 | the lab-agent Python core and its tests (corrections after review are in progress); `lab-agent/docs/l1-closeout.md`; seven files under `docs/.prepare` (documentation closeout, now `docs-baseline-r8`); and this plan, whose r6 text was not the version scanned |
| Result | no real secret or forbidden path found by the patterns used. **Not a clearance:** the scan predates those changes, did not read the PNG pixels, and covered a tree that is still moving |

*(r8: the snapshot of this table, 154 paths with the aggregate `24e3d0981e7c3d9c`, **is superseded again** by the change of 2026-11-16 (§ 22.2): the excluded group of 66 paths is out of the listing, and `.claude/settings.json`, `AGENTS.md`, `CLAUDE.md`, `.gitignore` and files of `docs/.prepare/` changed. The 154-path scan, including its pattern hits inside `lab-agent/**`, is a record and does not describe the 95-path listing.)*

The hits to be re-judged in § 22.3 fall under its checks 3 (fixture, placeholder and UUID-shaped values), 7 (private-range examples) and 9 (the images).

### 22.2 What changed since the earlier counts

Observed on 2026-11-16, the dry run at about 06:10, from the working tree and a read-only `git add -A --dry-run` listing. Times are file modification times; they show that a file was touched, not what changed. A file changed before the cut-off and not noticed here would be missed, which is why § 22.3 uses content hashes.

| Observation | Count | Detail |
|---|---|---|
| Paths the dry run listed at about 06:10 | 154 | 95 outside the lab-agent group, 59 in it |
| Paths new since the 94-path check (about 04:22) | 60 | 54 under `lab-agent/`, plus `AGENTS.md`, `CLAUDE.md`, `.mcp.json`, `.claude/agents/pve-lab.md`, `.claude/hooks/pve-guard.py`, `.agents/plans/proxmox-admin-agent-governance.diff`. Inferred, not compared: 154 − 94 = 60 equals this list exactly, and the 94-path list itself is not preserved in the records |
| Existing paths modified after it | 7 | `.claude/settings.json` (05:11, now with lab-agent entries), `.agents/plans/proxmox-admin-agent-plan.md` (05:15), and five files of `docs/.prepare/`: `implementation-plan.md`, `README.md`, `github-project-plan.md`, `decision-log.md`, `readiness-report.md` (05:00–05:13; the D-48 documentation change). The plan changes again with r6 |
| Paths modified between 2026-11-14 14:00 and 04:22 on the 16th | 14 | `diagrams/03-…` (three files), `diagrams/04-…` (two files) and `diagrams/generate_argue.py` (all 2026-11-14 14:44); the two Herdr policy files (03:35); `core-context.md`, `plan-review.md` (04:00); `delegation-manifest.md`, `source-register.md` (04:10); `.claude/rules/product-vision.md` (04:11); `open-questions.md` (04:21). The orchestrator's 94-path check covers them; the steward's scan has not |
| Ignored but present | — | `HANDOFF.md`, `.handoffs/`, `.claude/settings.local.json`, the D-45 tooling and caches are reported by `git status --ignored` as ignored; two `__pycache__` directories under `lab-agent/` exist and are ignored |
| Listing after D-49 (r8) | 95 | `git ls-files -o --exclude-standard` on 2026-11-16: 161 paths before the change, 66 in the excluded group (61 under `lab-agent/`, of them 55 regular files and 6 symbolic links under `lab-agent/tests/stubs/`, plus 5 other paths), **95** after. Reported by the orchestrator session at 08:07–08:13 CET; the steward re-ran the count and the groups of § 21.3 at 08:15 CET with the same result. Groups: root 4 · architecture and alternative 2 · `docs/.prepare/` 14 · `diagrams/` 26 · `.claude/` 20 + 28 · bootstrap mission 1 |
| Contents decision (r9) | — | D-50 (2026-11-16): the 28 command and agent files and `docs/.prepare/` stay in the candidate set; no path is added or removed by it, and no licence file is added (D-53). No scan was run in r9; the count of 95 is the orchestrator's check of 09:05 CET as reported, not re-run by the steward |
| Scanned snapshot (r8) | — | the 154-path snapshot of § 22.1 is **superseded again**; no scan of the 95-path listing exists, the final scan of § 22.3 is still to be run on the frozen manifest |

The packet that asked for this section calls the 94-path check a scan of 2026-11-14. The records date the 220- and 91-path scans to 2026-11-14 and the 94-path check to 2026-11-16; this file follows the records.

Content seen while counting at 06:10 (r6), which the final scan had to look at, reported without values: `.claude/settings.json` named, under `permissions`, a private configuration directory and a key-file pattern by their paths; `AGENTS.md` named the owner-only launcher by its script name, and `AGENTS.md` and `CLAUDE.md` mentioned the root key, with no key value or path. *(r8: **both are gone from those files**, as reported by the orchestrator session: the entries left the tracked `settings.json` and the two documents were reworded (§ 21.4); the steward's search at 08:15 CET for `lab-agent` and `pve` in the three files found no hit. The final scan still confirms it, on the frozen manifest.)* **Publication readiness stays: not established.**

### 22.3 The final scan, run by Stage 2

Run by the steward as step 1 of § 12, **after** the decisions 1 to 6 of § 21.8 are answered, the contents of the bootstrap commit are fixed and the checkout is quiet (step 0). It is not run before; a scan of a tree that is still being decided is a preliminary scan.

1. **Manifest.** The sorted list of `git add -A --dry-run`, with the SHA-256 of every file, its count and the hash of the list, kept outside the repository. Step 6 re-hashes the staged blobs against it; any difference stops the commit.
2. **Forbidden paths.** `HANDOFF.md`, `.handoffs/`, `.claude/settings.local.json`, `*.ign`, `secrets/`, `.env*`, `*.pem`, `*.key`, caches, any file over 5 MB.
3. **Secret patterns.** `-----BEGIN`, `ghp_`, `github_pat_`, `PVEAPIToken=`, `password=` or `api_key=` with a value, bearer tokens, credentials inside a remote URL.
4. **Personal data.** The repo-local name and address and their parts, read inside the command and never printed; relay account names; the names of the reviewer and the intermediary, supplied by the owner if the untracked handoff does not hold them, read inside the command and never printed; every mail address found, classified as fictional, quoted by a rule, or real.
5. **Paths.** Absolute paths under a home directory; `~/…` paths that name private files or directories.
6. **The former working name**, read from the untracked handoff inside the command.
7. **Lab-private data.** The Proxmox host name and address, internal host names, private-range addresses other than documented placeholders and the fictional range labelled as such in diagram 03.
8. **Exposure.** Any `ports:` entry other than Caddy's, once a Compose file exists (none exists today).
9. **Binary metadata.** Text chunks in every PNG.
10. **The text of every body before it is posted:** each issue body after step 10a, the board README, the pull-request body and every comment; and the commit message of step 6, which must carry no trailer.
11. **The commit identity** of step 6 is compared with the owner's answer to § 21.2, without printing it.
12. **Dangling references.** Every hook command and script path named in the tracked `.claude/settings.json` resolves to a path in the manifest. A hook registered with `onFailure: block` whose script is not in the manifest is a hit. *(r8: `.mcp.json` is not in the manifest under D-49 and is not part of this check; the check on hook commands stays. Under D-49 the tracked `settings.json` is to hold only the commit-format hook, whose script is in the manifest; the check confirms it.)*

Output: the file and line of each hit, never the value. A hit stops the sequence and is reported. A scan result is recorded with the manifest hash it belongs to; if any file changes afterwards, the affected files and every check that read them are run again.

### 22.4 What would let the steward say "scan clean"

All of: the manifest exists and its hash is quoted; the twelve checks above ran on exactly that manifest with zero hits, or with each hit explained and accepted by the owner in writing; the lab-agent group is out of the manifest (D-49) and its entries are gone from the tracked `settings.json`, `AGENTS.md` and `CLAUDE.md` (the branch "in the manifest and scanned in full" does not apply and is dropped); and no file changed between the scan and the commit. Until then this plan says only what was observed, and the publication gate stays closed.
