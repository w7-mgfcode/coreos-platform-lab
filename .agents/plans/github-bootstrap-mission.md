# Mission — GitHub bootstrap for CoreOS Platform Lab

> **Agent:** `github-steward` (`.claude/agents/github-steward.md`). Read it in full first. It defines the taxonomy, templates, gates and operating rules this mission uses.
> **Status:** revised on 2026-11-14 after the planning material was migrated; the "Current state" section was corrected on 2026-11-16. Stage 1 may run. **Stage 2 has not run**: no GitHub object named here exists yet, and it must not run before the publication gate opens.
> **Decided by the owner (2026-11-14):** the repository is **public**; its name is `w7-mgfcode/coreos-platform-lab`; the git identity is repo-local.
> *Note of 2026-11-16 (D-54, D-57): "Stage 2 has not run" above is the state of 2026-11-14/16 before the publication run. Stage 2 has since run in part, under the owner's go-ahead of 2026-11-16 (D-54), which is used up. Step 12 (the GitHub scaffold) was not run, and the board field this mission calls `Type` is `Work Type`. The body below is unchanged.*

## Current state

*Note of 2026-11-16 (D-54, D-57): the list below is the state before the publication run. `main` now carries the bootstrap commit and later pull-request commits, and the repository has a remote; the GitHub tree and the board exist (numbers up to #41 at the time of this note; the tree on GitHub is the record); no `.github/` directory exists yet, because S0.2 (#10) is open. Nothing platform-related is built or tested. The list is left as written.*

- The workspace is an initialised git repository on `main` with **no commits** and no remote. The repo-local identity is set.
- `.gitignore` exists. It excludes `HANDOFF.md`, `.handoffs/`, `.claude/settings.local.json`, `.claude/worktrees/`, rendered `*.ign`, `secrets/`, `__pycache__/` and editor files; since 2026-11-14 the generic toolkit of decision D-45; and since 2026-11-16 the lab-administration tooling of decision D-49 and a local instruction file.
- Two earlier checks exist, and neither is the scan you run in Stage 2. A first pre-publication scan ran over `git add -A --dry-run` on 2026-11-14, before `docs/.prepare/` was written (220 paths; 91 after D-45); its result is recorded in `docs/.prepare/readiness-report.md`. The orchestrator session ran local mechanical checks on 2026-11-16. The tree has changed since the first scan: `docs/.prepare/` was written, root `AGENTS.md` and `CLAUDE.md` exist, and a lab-administration tooling set is in the working tree only and is excluded from the initial publication (D-49). The candidate set and the checks that are still to be run are in `docs/.prepare/github-project-plan.md` § 21.3 and § 22.
- The owner's publication-preparation decisions of 2026-11-16 are recorded in `docs/.prepare/decision-log.md` § 2 (D-49 to D-53 and the approved proposals). The go-ahead itself is a separate, later answer.
- The migrated material is in place: `README.md`, `docs/architecture.md`, `docs/alternatives/swarm.md`, seven diagrams with their generators under `diagrams/`, and the preparation package under `docs/.prepare/`.
- There is no platform configuration yet: no Butane file, no `compose.yaml`, no `Caddyfile`, no firewall rules, no tests, no evidence. Nothing is built or tested.
- The scope is decided (`.claude/rules/product-vision.md`): one VM, Docker Compose, Docker CE, host firewall mandatory.
- There is no `.github/` directory in this workspace yet.

## Stage 1 — Prime and plan (read-only on GitHub)

Allowed writes: `docs/.prepare/github-project-plan.md` only. No commit, no branch, no remote, nothing created on github.com.

### 1a. Prime

1. Read the rules, the architecture sections and the `docs/.prepare/` documents listed under "Read before acting" in your agent definition. Note the baseline label in `docs/.prepare/README.md` and the status of each document.
2. Study the references:
   - `gh api 'repos/w7-mgfcode/cvforge-ai/milestones?state=all'`
   - `gh issue view 129 -R w7-mgfcode/cvforge-ai`, then the same for 130 and 135
   - `gh project view 2 --owner w7-mgfcode` and `gh project field-list 2 --owner w7-mgfcode`
   - `gh api repos/w7-mgfcode/ForecastLabAI/contents/.github/ISSUE_TEMPLATE`, then `.github/PULL_REQUEST_TEMPLATE.md`, `.github/dependabot.yml` and `.github/workflows/ci.yml`; `gh label list -R w7-mgfcode/ForecastLabAI`; `gh api repos/w7-mgfcode/ForecastLabAI`
3. Check that the name is still free: `gh repo view w7-mgfcode/coreos-platform-lab` should fail with "not found".
4. Check the token: `gh auth status` must list the `repo`, `project` and `workflow` scopes. If one is missing, report the exact output and ask the owner to refresh the token. Do not work around it.
5. Report what you found and stop. Do not write the plan until you are asked to.

### 1b. Draft the project plan

Write `docs/.prepare/github-project-plan.md` from the integrated baseline (`core-context.md`, `decision-log.md`, `open-questions.md`, `implementation-plan.md`) and `docs/architecture.md` § 2 and § 10. Give it the same metadata block as the other documents in that directory, with status `draft`. It contains:

1. Repository settings, labels (name, colour, description) and the board fields.
2. The milestones, mirroring architecture § 10, each with its exit.
3. One umbrella, the epics, and **every** sub-issue. For each sub-issue: title in commit grammar, labels, tier, the acceptance checks it proves, dependencies, files in scope, and acceptance criteria that a command, a test script or an evidence file can verify.
4. Anything that waits on the owner marked `status:blocked`, with the decision-log or open-question ID it waits on.
5. The bootstrap sequence of Stage 2, including the first-commit exception described below.
6. What you verified, what you assumed, what you propose, and what is still open.

The plan is a proposal. It is reviewed by the orchestrating session and then shown to the owner.

### 1c. Present and wait

When asked, show the owner, in your session:
- a fresh pre-publication scan over `git add -A --dry-run` (see Operating rules in your agent definition), with every hit listed by file and line;
- the issue tree from the plan, compact enough to read in one screen, with the blocked items marked;
- the decisions the owner must make at the gate (listed under "Owner decisions at the publication gate").

Then **wait**. Do not start Stage 2 until the owner gives the go-ahead in your session or the orchestrating session relays it.

## Stage 2 — GitHub execution (only after the publication gate)

### 2.1 Repository and first commit

1. Re-run the pre-publication scan. On any hit, **stop** and report.
2. Create `w7-mgfcode/coreos-platform-lab` as a **public** repository with a one-line description, with **no** `--source`/`--push` yet. Set topics, disable the wiki, allow squash merge only, turn on auto-delete of head branches, and enable secret scanning with push protection.
3. Labels: the full taxonomy from the agent definition, created idempotently.
4. Milestones: `M0 - Preparation`, `M1 - Host & Firewall`, `M2 - Web & Mail`, `M3 - Logs & Monitoring`, `M4 - Backup, Restore & Update`, `v0.1.0 - Release Gate`. Each description states its exit and cites `docs/architecture.md` § 10.
5. **Issue #1:** `docs: add architecture, diagrams, preparation package and agent tooling`. Put it in milestone `M0 - Preparation` with labels `type:sub-issue`, `area:docs`, `area:repo`, `tier:must-have` and `priority:p1`. The body lists what the commit contains and what was deliberately left out, as acceptance criteria. It is linked under the M0 epic once that epic exists.
6. First commit on `main`: `git add -A` (only after the scan passed), then `git commit -m "docs: add architecture, diagrams, preparation package and agent tooling (#1)"`. Do **not** add any trailer; the hook checks this. Then `git remote add origin https://github.com/w7-mgfcode/coreos-platform-lab.git` and `git push -u origin main`, using gh's credential helper. Never embed a token in the URL.
7. Tick the criteria of #1 with the commit SHA as proof, then close it with a comment giving the SHA.

**First-commit exception.** `branch-naming.md` says every change reaches `main` by PR. The bootstrap commit is pushed directly, because an empty repository has no `main` to open a PR against. This is the only direct push. It needs the owner's explicit agreement at the publication gate, and the decision is recorded in `docs/.prepare/decision-log.md`.

**Commit identity.** The commit carries the repo-local name and mail address, and both become public with the push. If the owner's GitHub account blocks pushes that expose a private address, the push is rejected. In that case stop and ask; do not change the identity yourself.

### 2.2 Projects v2 board

1. Create `CoreOS Platform Lab Delivery` (owner `w7-mgfcode`), make it public, and link it to the repo.
2. Create the fields from the agent definition and replace the `Status` options. Write the board README and a short description.

### 2.3 Decomposition (the core of this mission)

Create the tree exactly as the reviewed `docs/.prepare/github-project-plan.md` describes it. If the plan and this mission differ, the reviewed plan wins; report the difference.

Source: `docs/architecture.md` § 2 (requirements), § 10 (steps and acceptance table), the AC table in `.claude/rules/test-requirements.md`, and `docs/.prepare/implementation-plan.md`. Planning is done; nothing is built or tested.

1. **Umbrella U1:** `feat(repo): coreos platform lab v0.1.0 — single-vm compose stack with proven acceptance checks`. Success criteria are AC-01 … AC-09. Out of scope lists the EXCLUDED rows of the scope lock with their reasons. The umbrella carries no milestone.
2. **Epics** (native sub-issues of U1), each with its milestone:
   - E0 `M0 - Preparation`: Proxmox capacity and version check, DNS or hosts plan, SMTP relay or test mailbox, Checkmk access, repo scaffold with the static gates. Items waiting on an owner answer get `status:blocked` and name the question.
   - E1 `M1 - Host & Firewall`: FCOS VM from Butane with the Docker CE first-boot unit; boot-time Compose start; host `DOCKER-USER` rules with negative tests. The EXTRA layers (Proxmox firewall, Docker-network isolation) are separate sub-issues labelled `tier:extra`.
   - E2 `M2 - Web & Mail`: WordPress, MariaDB and Caddy with `tls internal`; Postfix relay and the WordPress mail integration.
   - E3 `M3 - Logs & Monitoring`: Alloy, Loki and Grafana; Checkmk agent and checks.
   - E4 `M4 - Backup, Restore & Update`: `tier:optional`.
   - E5 `v0.1.0 - Release Gate`: evidence complete, CHANGELOG, tag.
3. **Sub-issues** under each epic, one per service or layer brought up and proven:
   - Each needs a scope from the commit allow-list, its files, `gate:` labels for the acceptance checks it proves, a `tier:` label, and acceptance criteria that a command, a test script or an evidence file can verify.
   - One branch and one PR each. Minor steps are checkboxes.
   - The early spike in E1 answers the open technical questions before anything depends on them: which packages the Docker CE install pulls in, the iptables backend and the `DOCKER-USER` chain, and whether Python is present for the Checkmk Docker plugin.
   - The platform scaffold (file layout and `scripts/validate.sh`) is one sub-issue in E0. The CI workflow with the static gates is a separate sub-issue and PR that depends on it. Use commit type/scope `chore(ci)`.
   - Clarification items follow the rule in the agent definition: a docs PR for a non-private outcome, an epic checkbox for a lab-private answer.
4. Link everything as native sub-issues, add every issue to the board, and set Type, Area, Priority, Tier, Gate and Status:
   - `Blocked` for anything waiting on an owner decision
   - `Ready` for E0's actionable items
   - `Backlog` for the rest

Every issue is created while the implementation gate is still closed. Creating an issue is planning, not permission to build: no sub-issue that produces platform configuration moves to `In Progress` before the owner's approval line exists in `docs/.prepare/decision-log.md`.

### 2.4 GitHub scaffold PR (opened, not merged)

This is the *GitHub scaffold* (`.github/` only). It is not the *platform scaffold*, which creates the platform file layout and waits for the implementation gate.

1. Cut `chore/repo-github-scaffold` from `main`, with an issue under E0 first.
2. Add `.github/ISSUE_TEMPLATE/` (umbrella, epic, sub-issue, bug, `config.yml`), `PULL_REQUEST_TEMPLATE.md`, `CODEOWNERS` and `dependabot.yml`. **No** CI workflow yet; it belongs to the scaffold sub-issue.
3. Commit, push, and open the PR with `Closes #n` and a title in commit grammar. No "Generated with" line in the PR body. **Do not merge.** Leave it for the owner's review.

## Owner decisions at the publication gate

Ask for these together with the go-ahead; none of them is yours to decide:

1. Go-ahead to create the public repository and push.
2. Agreement to the first-commit exception (one direct push to `main`).
3. Whether the commit author address may become public, or a GitHub no-reply address should be used instead. The owner changes the identity; you do not.
4. Whether the repository gets a licence, and which.
5. The structural proposals the tree rests on, which become public with it: the scope list (D-20), the AC numbering (D-21), the release gate (D-22), the hierarchy and board without budget fields (D-23) and the work order (D-33). All are proposals in `docs/.prepare/decision-log.md`.

*Note of 2026-11-16.* Items 2 to 5 were answered by the owner on 2026-11-16 and are recorded in `docs/.prepare/decision-log.md` § 2: D-28, D-52, D-53, and the approval of D-20 … D-23 and of D-33 for the GitHub work tree, subject to the D-48 exception. Item 1, the go-ahead, has not been given.

Unless the owner says otherwise, `docs/.prepare/` is published with the rest of the tree: it is tracked, and its documents carry their own draft status.

## Out of bounds for this mission

- Platform configuration (`butane/`, `compose.yaml`, `Caddyfile`, `firewall/`, `scripts/`, `tests/`)
- Any contact with the lab VM or the Proxmox host
- Edits to `.claude/rules/` or to the scope decisions in `docs/architecture.md`
- Edits to any file under `docs/.prepare/` other than `github-project-plan.md`
- Branch protection, tags or releases
- Deleting anything
- Merging the PR
- Marking any document approved

## Done when

**Stage 1** ends with the plan written, the scan and the tree shown to the owner, and the session waiting.

**Stage 2** ends with a final report (in `output-formatting.md` style) that contains:
- the repo URL
- the board URL
- the 🔗 table of every created object with URLs
- the issue tree (U1 → E0…E5 → sub-issues with numbers)
- the PR URL
- `👉 Next steps` for the owner

Then wait in the session for owner feedback.
