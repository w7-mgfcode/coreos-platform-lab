# Commit Message Format

Every commit in this repository MUST follow this format:

```
type(scope): description (#issue)
```

## Rules

- **type** — one of: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `release`
- **scope** — one of the CoreOS Platform Lab scope allow-list (below). Comma-pairs are allowed when a change cuts across two scopes (e.g., `compose,proxy`).
- **description** — lowercase, imperative mood, no trailing period
- **#issue** — a valid GitHub issue number. Every commit MUST reference one.

### Scope allow-list

Scopes follow the platform's concerns in `docs/architecture.md`. The paths are the planned layout; the scaffold change fixes them, and this table is updated in that same change if a path differs. CI changes use `chore(ci)`; `ci` is a scope, not an allowed type.

| Scope        | Use for |
|--------------|---------|
| `host`       | `butane/**` and VM provisioning — Butane/Ignition, systemd units, the Docker CE first-boot install, Zincati, Proxmox VM creation |
| `compose`    | `compose.yaml` — service wiring, networks, volumes, secret declarations, image pins |
| `proxy`      | `Caddyfile` — TLS (`tls internal`), reverse-proxy routes, access logging |
| `web`        | WordPress and MariaDB configuration, including the mail integration on the WordPress side |
| `mail`       | Postfix relay configuration |
| `logs`       | Alloy, Loki and Grafana configuration and provisioning |
| `monitoring` | Checkmk agent, plugins and local checks |
| `firewall`   | `firewall/**` — host `DOCKER-USER` rules, Proxmox firewall rules, network isolation |
| `backup`     | Backup, restore and update procedures and their scripts |
| `tests`      | `tests/**` — acceptance and negative checks |
| `docs`       | `docs/**`, root `README.md`, `CHANGELOG.md`, evidence files |
| `diagrams`   | `diagrams/**` — Excalidraw sources, rendered images, generator scripts |
| `ci`         | `.github/workflows/**` |
| `repo`       | Repo-wide hygiene (`.gitignore`, `.claude/`, `.agents/`, `.github/` templates) |
| `release`    | Version bumps and tags |

### No AI co-author trailer — ever

Do NOT include any of the following in commit messages — past, present, or future model versions:

- `Co-Authored-By: Claude <noreply@anthropic.com>`
- `Co-Authored-By: Claude <any-version> <noreply@anthropic.com>`
- `Generated with [Claude Code]` lines
- `🤖 Generated with …` lines
- Any other AI-attribution line

The session is already attributed via `git config user.name`. That is the only attribution we keep.

## Examples

Good:
- `feat(host): install docker ce with a first-boot unit (#4)`
- `feat(firewall): drop non-443 traffic in docker-user (#9)`
- `fix(proxy): persist caddy data so the internal ca survives restarts (#12)`
- `chore(repo): adapt .claude/ rules to coreos platform lab (#1)`
- `docs(docs): record the relay rejection evidence (#7)`
- `feat(compose,mail): add postfix relay on a fixed subnet (#10)`
- `test(tests): add negative check for the database port (#11)`
- `release(repo): cut 0.1.0 (#20)`

Bad:
- `fixed bug` — no type, scope, or issue
- `feat: add new feature` — missing issue reference
- `feat(proxy): Add Grafana route.` — capitalized + trailing period
- `feat(misc): X (#17)` — `misc` is not in the allow-list
- `feat(rag): X (#17)` — `rag` belonged to the previous project's tooling, not this repo

## Scope exception

`docs` and `release` types may omit scope when the change is project-wide (e.g., root README, CHANGELOG bump).

## Before committing

Verify, in this order:
1. Message matches `type(scope): description (#issue)`
2. The issue exists and is open: `gh issue view <N> --json state`
3. The scope matches the primary path being changed
4. The type accurately reflects the change (`feat`=new, `fix`=bug, `chore`=non-functional, `release`=tag-cut)
5. There is NO AI co-author or "Generated with" trailer

If a user-supplied message doesn't match, reformat it. If no issue number is provided, ask — never commit without one.

A `commit-format-check` skill and a `PreToolUse` hook (`.claude/hooks/check-commit-format.sh`) enforce this rule deterministically.
