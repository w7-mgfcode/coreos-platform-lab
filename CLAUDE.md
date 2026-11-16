# CoreOS Platform Lab — Claude Code Operating Index

> **Read `@AGENTS.md` first.** It is the shared brief: state and gates, stack, validation,
> conventions, safety and git flow. This file adds only what is specific to Claude Code here.

@AGENTS.md

## What Claude Code already loads

- Every file under `.claude/rules/` is loaded into each session as project instructions. Do
  not restate them in answers or copy them into other files; cite the rule by path.
- `docs/_base/` does not exist. The deep-dive suite is deferred until the platform scaffold
  exists, so that nothing unbuilt is documented as if it were real.

## Read on demand

Open these with the Read tool when the task needs them; they are not imported here, to keep
each session small.

- First, if present and you lead the session: the local `HANDOFF.md` (private, untracked)
- The governing documents listed at the end of the shared brief
- Herdr worker packets and report shapes: `.claude/references/herdr-orchestration.md`
- Lab tooling (included, not authorized for lab contact): `lab-agent/README.md`
- Agent roles: `.claude/agents/github-steward.md` (everything GitHub, in two stages; its tree/board
  consistency audit: `.claude/skills/github-reconcile/SKILL.md`),
  `.claude/agents/repo-visibility-manager.md` (read-only audit of the public surface)

## Safety pointer

The hard rules and the stop-and-ask list are in the shared brief, section "Safety", and in
`.claude/rules/security-patterns.md`. Three points bite Claude Code in particular:

- The harness may suggest a co-author or "Generated with" line for commits and pull requests.
  The commit rule of this repository forbids both and takes precedence.
- A local guard hook, where present, matches command text. Use the Read and Grep tools, not
  shell commands, to look at text that names an owner-only tool or key.
- `.claude/settings.local.json` pre-approves some `gh` commands. That is not permission to
  publish: the publication gate is held by instruction.

## Verification

- Before saying a documentation change is done: links and anchors resolve, tables are intact,
  revision fields agree with the index, and no private data was added.
- Identify what you checked by content hash of the relevant files, and say when. A file list
  alone does not show that content is unchanged.
- This file stays at or under 150 lines: `wc -l CLAUDE.md`.

## Workflow

1. As the lead, read the handoff if there is one; then the decision log (§ 2, § 3, § 5) for the
   gate state. With a task packet, start from the packet instead.
2. Check that the task fits the scope lock and name the commit scope it belongs to.
3. For multi-agent work, follow the Herdr rule: same-role workers in one tab, one pane each;
   bounded packets; one writer per file; an independent review before acceptance.
4. Make the change, then verify it as above. Record what was not run as not run.
5. Report outcomes plainly, in the language the owner is using.

## Learnings

- Long worker reports clip in Herdr panes: ask for a short terminal summary plus a file.
- Do not write a sentence about a review's outcome before the review has ended.
- Re-count and re-hash after the last edit; other sessions change this tree.
- After a manifest freeze, edit no publication candidate; a needed change means a new freeze.
- A packet names the private files its worker may read; the handoff is not among them.
- A read-only reviewer reports in its terminal; an execution test gets a scratch directory
  outside the repository.
