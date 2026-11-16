---
name: repo-visibility-audit
description: Audits the CoreOS Platform Lab public-facing surface — README.md, CHANGELOG.md, docs/architecture.md and the other docs/ pages, the diagrams they embed, and the evidence index. Detects broken internal links, dead anchors, CHANGELOG↔tag version drift, documented-vs-pinned component version drift, missing evidence behind "passed" claims, stale docs (>90d unchanged), orphan docs, badge failures (HTTP probe), and outdated diagram renders. Read-only — produces a scannable report. Triggers on "audit the README", "check the docs", "find stale docs", "find orphan docs", "/repo-visibility-audit". Do NOT use for configuration review, dependency audits, security scanning, or rewriting docs.
---

# repo-visibility-audit

Read-only audit of the CoreOS Platform Lab public-facing surface. **You print a scannable report. You NEVER edit files.**

## Scope

Audit ONLY these paths:

- Root: `README.md`, `CHANGELOG.md`
- `docs/architecture.md` and the other `docs/**/*.md` pages, including the evidence index under `docs/evidence/`
- Diagram files under `diagrams/` that those pages reference
- Cross-checked against (read-only, not audited themselves): `compose.yaml`, `butane/*.bu`, the file names under `tests/` and `scripts/`

Anything else: skip. A scope file that does not exist yet is reported as `⏭️ SKIP (not created yet)`. The docs are written in Hungarian; audit structure and consistency, not language.

## Procedure

1. Build the scope list:
   ```bash
   { ls README.md CHANGELOG.md 2>/dev/null; find docs -name '*.md' 2>/dev/null; } | sort
   ```
2. For each file, extract:
   - Markdown links: `grep -nE '\]\([^)]+\)' "$f"`
   - Headings: `grep -nE '^#+ ' "$f"`
   - Image refs: `grep -nE '!\[[^]]*\]\(([^)]+)\)' "$f"`
   - Badge URLs (README only): first 30 lines
3. Run checks 1–9 below.
4. Cap HTTP probes at 5s timeout. Use `xargs -P 8` for parallelism.
5. Use `git log -1 --format=%cs -- <file>` per scope file for freshness. Without git history, report freshness checks as `⏭️ SKIP`.

## Checks

1. **Broken internal links / anchors** — resolve every `](path)` and `](#anchor)` relative to the source file. Miss = ❌.
2. **Badge sanity** — README badges (if any): probe via `curl -sI -o /dev/null -w "%{http_code}" --max-time 5 <url>`. 2xx/3xx = ✅, 4xx/5xx = ❌, transient 5xx may be ⚠️.
3. **Stale anchor list** — every `## Heading` produces a slug (lowercased, spaces→`-`, punctuation stripped). Cross-check incoming `#anchor` links against the slug list.
4. **Version drift** — the top `CHANGELOG.md` section and `git describe --tags --abbrev=0` (if any tag exists) must agree. Mismatch = ❌.
5. **Component-version drift** — image tags and digests in `compose.yaml`, and package or stream pins in `butane/*.bu`, vs. the versions the docs state. Mismatch = ❌; a version stated in docs but pinned nowhere = ⚠️.
6. **Rebuild-path drift** — every repo path or script the README and install notes name must exist on disk. Miss = ❌.
7. **Evidence drift** — every acceptance check (AC-01 … AC-10) a doc marks as passed must link to an existing file under `docs/evidence/`. A "passed" claim without evidence = ❌. Evidence that exists while the doc still says "planned" = ⚠️.
8. **Diagram drift** — every embedded image resolves; a `.png` or `.svg` older than its `.excalidraw` source = ⚠️.
9. **Stale docs** — `now - git-mtime > 90 days` → ⚠️ STALE (warning only; not a failure).

## Report format

Use `.claude/rules/output-formatting.md` exactly:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🔍 Repo-Visibility Audit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Internal links & anchors
  ✅ README.md — 12/12 links resolve
  ❌ docs/architecture.md:14 — link to diagrams/01-compose-dark.svg not found

📋 Badges (README)
  ✅ 2/2 badges return 2xx

📋 Version drift
  ⏭️ SKIP — no tag yet

📋 Component-version drift
  ❌ docs/install.md:22 says caddy 2.8 but compose.yaml pins caddy:2.10.2

📋 Rebuild-path drift
  ✅ all 6 referenced paths exist

📋 Evidence drift
  ❌ docs/architecture.md:139 marks AC-05 passed but docs/evidence/ac-05-*.md is missing

📋 Diagram drift
  ⚠️ diagrams/09-tuzfal-dark.png is older than its .excalidraw source

📋 Stale docs (>90 days, unchanged)
  ✅ none

────────────────────────────────────────────
  ❌ Result: NOT CLEAN — 3 errors, 1 warning
────────────────────────────────────────────

👉 Next steps:
  1. Fix the diagram link at `docs/architecture.md:14`
  2. Align the Caddy version in `docs/install.md:22` with `compose.yaml`
  3. Add the AC-05 evidence file or remove the "passed" mark
```

The paths and versions in the example are illustrations, not facts about this repo.

## Constraints

- **Read-only.** If a check needs to write, ABORT with `❌ Tool restriction violated`.
- Cap output at 80 lines. If more findings, append `(+N more)` footer.
- Do NOT call the network for anything beyond the README badge probe list. Never contact the lab VM or the Proxmox host.
- Do NOT review configuration beyond the cross-check reads named in Scope — markdown only.
- Do NOT propose textual rewrites — that's the operator's call.
