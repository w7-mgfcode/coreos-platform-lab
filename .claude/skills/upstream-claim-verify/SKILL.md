---
name: upstream-claim-verify
description: Verify claims about upstream tool behaviour (a Butane field, an rpm-ostree command, a Docker or Compose option, a Caddy directive, a Postfix parameter, an Alloy or Loki component, a Checkmk plugin requirement) against the real tool or its primary documentation before they land in a plan, a PRP or the docs. Triggers on "verify this Butane field", "does docker-ce pull in the compose plugin", "check the cited upstream claims", "is this Caddy directive real", or whenever a plan cites specific behaviour of Fedora CoreOS, rpm-ostree, Docker CE, Compose, Caddy, Postfix, Alloy, Loki, Grafana or Checkmk. Do NOT use for general questions or for facts about this repo's own files.
---

# upstream-claim-verify

## Why this skill exists

This project is configuration glued to other people's tools, and most of its risk sits in assumptions about them: which packages `rpm-ostree --install docker-ce` pulls in, whether Fedora CoreOS ships Python for the Checkmk Docker plugin, which iptables backend Docker uses and whether `DOCKER-USER` exists, how `tls internal` renews. A claim that is wrong for the version in use is cheapest to catch before a VM is built on it. This skill checks the claim against the tool itself, or against primary documentation, instead of trusting memory.

## When to use

- During plan or PRP authoring, before submitting to `prp-quality-agent`
- Before a sentence about upstream behaviour is written into `docs/`
- During execution, when a citation starts to look wrong

## When NOT to use

- General questions with no decision riding on them
- Facts about this repository (use `Grep` + `Read`)
- Claims already verified for the same pinned version; re-verify only when the pin changes

## Verification methods, strongest first

1. **Run it on the lab VM** — the only proof for host behaviour (packages, rpm-ostree state, firewall chains, SELinux). Read-only commands only, for example `rpm -q docker-ce docker-compose-plugin`, `rpm-ostree status`, `iptables -S DOCKER-USER`, `command -v python3`.
2. **Run the tool in its pinned container** — good for parsers and defaults that do not depend on the host: `butane --strict`, `docker compose config`, `caddy validate` / `caddy adapt`, `postconf -d <parameter>`.
3. **Read primary documentation** — the project's own docs or source for the version in use. When a docs site blocks automated fetches, read the raw source instead (the Fedora CoreOS docs are AsciiDoc under `github.com/coreos/fedora-coreos-docs`).
4. **Secondary sources** (forum threads, blog posts) support a claim but never settle it alone.

Record which method was used. Method 3 or 4 alone yields `REPORTED`, never `VERIFIED`.

## Inputs

A YAML block of claims:

```yaml
claims:
  - tool: rpm-ostree / docker-ce
    version: "FCOS stable stream in use; Docker CE repo for that Fedora release"
    claim: "installing docker-ce also installs docker-compose-plugin"
    method: lab
    verify: |
      rpm -q docker-ce docker-compose-plugin docker-buildx-plugin
  - tool: docker engine
    version: "the installed docker-ce"
    claim: "the DOCKER-USER chain exists and is evaluated before Docker's own forwarding rules"
    method: lab
    verify: |
      sudo iptables -S DOCKER-USER; sudo iptables -S FORWARD
  - tool: caddy
    version: "the pinned caddy image"
    claim: "`tls internal` is accepted in a site block and needs no ACME server"
    method: container
    verify: |
      docker run --rm -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro,Z" <pinned-caddy-image> caddy validate --config /etc/caddy/Caddyfile
  - tool: fedora coreos docs
    version: "main branch, fetched today"
    claim: "the documented Docker CE method is a first-boot unit ordered before zincati.service"
    method: docs
    verify: |
      fetch raw modules/ROOT/pages/docker-ce.adoc and quote the unit
```

The `verify` commands are written per claim. The examples above show the shape; check a command's own syntax before relying on it.

## Outputs

A Markdown table:

| Tool | Version checked | Claim | Method | Command or source | Result | Verdict |
|------|-----------------|-------|--------|-------------------|--------|---------|
| rpm-ostree / docker-ce | *(as observed)* | compose plugin comes with docker-ce | lab | `rpm -q …` | *(output)* | ✅ VERIFIED / ❌ REFUTED |
| fedora coreos docs | main @ date | first-boot unit before zincati | docs | raw `docker-ce.adoc` | *(quoted lines)* | ⚠️ REPORTED |

Verdicts:

- `✅ VERIFIED` — observed on the lab VM or in the pinned container, with the output shown
- `⚠️ REPORTED` — stated by primary documentation but not run; names the source and the fetch date
- `❌ REFUTED` — the tool or its documentation contradicts the claim
- `⏭️ UNVERIFIED` — could not be checked; says what access is missing

For each `REFUTED` or `UNVERIFIED` row, emit a "Known Gotchas" snippet the plan author can paste, and name the open question it belongs to.

## Implementation outline

1. Parse the input YAML block.
2. For each claim, pick the strongest method that is actually available. If the lab is unreachable, do not downgrade silently — mark the row `REPORTED` or `UNVERIFIED`.
3. Run the command or fetch the source. Capture the output and the version it applies to.
4. Compare the result with the claim.
5. Render the table, then the gotcha snippets.

## Constraints

- Lab commands are read-only. Never change packages, firewall rules, containers or files on the VM from this skill.
- Never print secrets or tokens. Follow `.claude/rules/security-patterns.md` for Proxmox API access.
- Never use `-k` or disable verification to make a fetch or a check succeed.
- State the version every verdict applies to. A verdict without a version is not reusable.

## Cross-links

- Architecture: `docs/architecture.md` § 2 (Docker CE on FCOS), § 6 (firewall), § 7 (Checkmk on CoreOS)
- Sibling: `prp-quality-agent` (this skill runs upstream of its Phase 4.5 upstream-claim check)
