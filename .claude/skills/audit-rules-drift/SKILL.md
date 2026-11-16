---
name: audit-rules-drift
description: Detects drift between CoreOS Platform Lab policy artifacts and the repository. Compares .claude/rules/*.md and .claude/hooks/*.sh against root README.md, CLAUDE.md and AGENTS.md when present, and against the governing docs/architecture.md. Surfaces orphan rules, dangling references, unused/undeclared scopes, hook-vs-rule mismatch, and stale paths. Read-only; triggers on "audit rules", "find rule drift", "are the rules current", "/audit-rules-drift", or before a docs-refresh PR. Do NOT use for configuration review, security audits, or rewriting rules.
---

# audit-rules-drift

Detect drift between `.claude/rules/`, root markdown anchors, and the repo state they describe. Read-only.

## Scope

- `.claude/rules/*.md`
- `.claude/hooks/*.sh`
- Root `README.md`, `CLAUDE.md`, `AGENTS.md` — each only if present
- `docs/architecture.md` §§ 2, 6, 10 — the governing requirements, firewall model and acceptance table
- `.claude/agents/github-steward.md` and `.claude/skills/commit-format-check/SKILL.md` — only for the lists that must mirror the rules

## Procedure

1. **List rule files**: `find .claude/rules -name '*.md'`.
2. **List hooks**: `ls .claude/hooks/*.sh`.
3. **Build the path authority**: union of existing files and the planned layout the rules name (`butane/`, `compose.yaml`, `Caddyfile`, `firewall/`, `scripts/`, `tests/`, `docs/`, `docs/evidence/`, `diagrams/`, `.gitignore`, `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `.github/`). Planned files need not already exist.
4. For each rule file, extract:
   - Every concrete file path it mentions (`butane/...`, `firewall/...`, `tests/...`, `docs/...`, `.github/...`)
   - Every shell command it cites (`butane --strict`, `docker compose config`, `caddy validate`, `shellcheck`, `git tag`)
   - Every scope/type/keyword it constrains (scope allow-list in `commit-format.md`, branch prefixes in `branch-naming.md`, acceptance IDs in `test-requirements.md`)
5. For root `README.md` / `CLAUDE.md` / `AGENTS.md` (when present), extract every rule path it references. When none of the three exists yet, report the orphan check as `⏭️ SKIP (no anchor docs yet)` instead of flagging every rule.
6. Run the checks below.

## Checks

1. **Orphan rules** — a `.claude/rules/<name>.md` that is referenced from NEITHER `README.md` NOR `CLAUDE.md` NOR `AGENTS.md`. Flag `⚠️ ORPHAN`. Skipped while none of the anchor docs exists.
2. **Dangling references** — `README.md` / `CLAUDE.md` / `AGENTS.md` cites a rule file (or section heading) that does not exist. Flag `❌ DANGLING`.
3. **Path / command drift** — a rule cites a concrete path that is neither on disk nor in the path authority from step 3. Flag `❌ PATH-DRIFT`. The most likely drift in this repo is a leftover from the previous project's tooling: `app/`, `demo/`, `pyproject.toml`, `uv run`, `pytest`, `ruff`, `docs/.prepare/`, `.env.example`, `QG-0x` gate names, `EC2`.
4. **Empirical-vs-declared scope drift** (commit-format.md only; skipped when the repo has no git history) —
   - Run: `git log --pretty=%s -200 main | grep -oE '^[a-z]+\(([a-z,]+)\)' | sed 's/.*(\([a-z,]\+\))/\1/' | tr ',' '\n' | sort -u`
   - Diff vs. the scope allow-list in `commit-format.md` (and the `SCOPE_ALLOW` regex in `.claude/hooks/check-commit-format.sh`).
   - Scopes used but not declared → ❌ `UNDECLARED`.
   - Scopes declared but never used → ⚠️ `UNUSED` (low-value to fix; report only).
5. **Hook ↔ rule consistency** — the `SCOPE_ALLOW` regex in `check-commit-format.sh` MUST exactly mirror the scope allow-list table in `commit-format.md`. The same set MUST appear in `.claude/skills/commit-format-check/SKILL.md` and as the `area:` label values in `.claude/agents/github-steward.md`. Flag `❌ HOOK-DRIFT` on divergence.
6. **Architecture ↔ rule consistency** —
   - The `product-vision.md` scope lock must agree with the requirements table in `docs/architecture.md` § 2 and with the three binding scope decisions.
   - The AC table in `test-requirements.md` must have one row per row of the acceptance table in `docs/architecture.md` § 10, in the same order.
   - Flag a missing, weakened or reordered check as `❌ SPEC-DRIFT`. Skipped with `⏭️` while `docs/architecture.md` does not exist.
7. **Layout drift** — once the scaffold exists, a scope whose "planned path" in `commit-format.md` does not match where the files actually live. Flag `⚠️ LAYOUT-DRIFT`.

## Report format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🧭 Rules Drift Audit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Rules inventory
  ✅ 7 rule files discovered

📋 Orphan rules
  ⏭️ SKIP — no README.md / CLAUDE.md / AGENTS.md yet

📋 Dangling references
  ✅ none

📋 Path / command drift
  ❌ .claude/rules/test-requirements.md:21 — cites `uv run pytest` (previous-project leftover)

📋 Commit-format scope drift
  ⏭️ SKIP — no git history yet

📋 Hook ↔ rule consistency
  ✅ SCOPE_ALLOW matches commit-format.md, commit-format-check and the area: labels

📋 Architecture ↔ rule consistency
  ✅ scope lock and AC table match docs/architecture.md

────────────────────────────────────────────
  ❌ Result: 1 error, 0 warnings
────────────────────────────────────────────

👉 Next steps:
  1. Replace the `uv run pytest` reference in test-requirements.md:21
```

## Constraints

- **Read-only.**
- Cap report at 80 lines.
- Do NOT propose textual rewrites — list findings, the main session decides.
- The 200-commit window for empirical scope analysis is a deliberate limit: longer windows are noisy. Adjust if the user explicitly asks.
- If a `.claude/rules/` file is generic (e.g., `output-formatting.md`), it may legitimately reference no repo-specific path — don't flag it as PATH-DRIFT for that reason alone.
