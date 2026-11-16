# Dependencies and attribution

Written 2026-11-16. Every third-party component that `lab-agent/`
uses, installs or pins, with its origin, its version or pin, and its licence where known.
**"Not verified"** means that this document could not confirm the fact on this machine: the
work that wrote it used no network and fetched no upstream file. A licence shown with a source other than
"recorded" is general knowledge, not a check.

This document chooses no licence for this repository. The owner deferred that choice
(decision D-53 in [`docs/.prepare/decision-log.md`](../../docs/.prepare/decision-log.md)).
The lab-administration tooling was excluded from the initial publication (D-49 in the same
log) and is included by the owner's decision D-57 of 2026-11-16; the inclusion changes no
licence position. Nothing here grants a reuse right, and it claims none over material whose origin is not
established. Existing third-party licence and attribution obligations stay in force.

## 1. What is bundled and what is not

| Question | Answer | State |
|---|---|---|
| Is third-party source code copied into `lab-agent/`? | Not known to be. `lab_agent/` uses only the Python standard library; the snippet writer uses only Perl core modules. The MCP server is **not** vendored: `lab-agent mcp-install` clones it into the owner's state directory at one pinned commit | observed by reading the imports; no by-content comparison with any upstream was done |
| Is upstream text copied into scripts or documents? | Not verified. Scripts follow upstream procedures (§ 4) but were written here; no text comparison was made | not verified |
| Are binaries or images committed? | No. Container images are referenced by tag and pulled by the owner, never by the gate | observed |

## 2. Third-party components

| Component | Role | Origin | Version or pin | Licence | State |
|---|---|---|---|---|---|
| `ry-ops/proxmox-mcp-server` | the MCP server the `pve` entry launches (`lab_agent/mcp.py`) | `https://github.com/ry-ops/proxmox-mcp-server.git`, cloned at `mcp-install` | commit `69686b06347c89d85c3725cf4a730c979b0148b7`, v2.14.0 (the pin in `lab_agent/mcp.py`) | MIT, as recorded by the L1 review in [`mcp-server-review.md`](mcp-server-review.md) (`LICENSE` and `pyproject.toml` at the commit) | licence **recorded** by the L1 review and **observed on 2026-11-16**, from read-only requests to the public upstream repository at the pinned commit: `LICENSE` is the MIT text and `pyproject.toml` says MIT ([`mcp-server-review.md`](mcp-server-review.md), update of 2026-11-16). Limits: this document did not re-check that observation; nothing was cloned or installed; the licences of the server's dependencies were not checked |
| Dependencies of that server: `mcp`, `httpx`, `python-dotenv`, `starlette`, `uvicorn` | installed by `uv sync --frozen --no-dev` from the server's own hash-pinned `uv.lock` | PyPI, through `uv` | versions fixed by that lockfile (not read) | not verified | not verified; no install of the server was run |
| `RekklesNA/ProxmoxMCP-Plus` | **not used.** Reviewed and rejected in `mcp-server-review.md` | GitHub | commit `a8b5edb15e5803241a20d3c31629ec6d0454dc87` (reviewed only) | MIT, as recorded in the review | recorded; listed so the review's reference resolves |
| `uv` | installs the MCP server and runs it at every launch (`uv run`); the launch also uses `git` to check the pin | the owner's workstation | 0.12.7 observed on the development machine; no minimum known | not verified | version observed, minimum not verified |
| `koalaman/shellcheck` image | gate check 4 (`tests/run.sh`) | Docker Hub | `docker.io/koalaman/shellcheck:v0.10.0`, by tag. Local digest observed on the development machine: `sha256:2097951f02e735b613f4a34de20c40f937a6c8f18ecb170612c88c34517221fb` | not verified (upstream is commonly cited as GPL-3.0) | tag pin only; the digest is an observation, not an enforced pin |
| `coreos/butane` image | gate check 5 and `demo/render.sh` | Quay | `quay.io/coreos/butane:v0.23.0`, by tag. Local digest observed on the development machine: `sha256:22bccae5281ad82a705e45f85dd08f880eb37847586acdf8e0ef3658fcec12e3` | not verified (upstream is commonly cited as Apache-2.0) | tag pin only; the digest is an observation, not an enforced pin |
| `python` image | the network-less run of the unit suite (`tests/run-netless.sh`); a local image that the script never pulls | Docker Hub | `python:3.12.14-slim`, by tag; no digest observed | not verified | tag pin only; used offline, from a local copy, with no network |

The shellcheck and Butane images are **pinned by tag** in `tests/run.sh` and, for Butane, in
`demo/render.sh`; the two are left on the tag so that they stay in step, and the digests above are
information only. Both run with `--network none`; the gate never pulls them. A tag can be re-pointed by its publisher, so
a digest pin would be stronger; that is a possible later change to the gate and to `render.sh`
together, not made here.

## 3. Tools the tooling expects but does not ship

None of these is distributed with the repository. Versions are those observed on the
development machine on 2026-11-16; "minimum" is stated only where the code or its tests give
one. Details of what a second workstation needs: [`l2-runbook.md`](l2-runbook.md) § "Portability".

| Tool | Used for | Observed | Minimum | Licence |
|---|---|---|---|---|
| Python 3 standard library | `lab_agent/`, `bin/*`, the guard hook, the tests, the stub tools | 3.14.4 | not established; only 3.14 was run | PSF, not verified |
| Perl 5 with `Cwd`, `Digest::SHA`, `Fcntl`, `IO::Handle`, `JSON::PP` | the snippet writer, on the Proxmox host (and in its tests) | perl 5.40.1, `JSON::PP` 4.16, `Digest::SHA` 6.04 | not established; the plan states Perl and `JSON::PP` ship with Proxmox VE | Perl licence, not verified |
| OpenSSH client | `host-run`, the `pve-snip` alias, `ssh -G` in tests | OpenSSH_10.2p1 | the options in use are `-F none`, `BindAddress`, `IdentityAgent=none`, `IdentitiesOnly`, `ControlPath=none`; the host side uses `authorized_keys` options `restrict`, `from=`, `command=`. The version that introduced each was not checked here | BSD-style, not verified |
| GNU or compatible coreutils, `bash`, `curl`, `tar`, `xz`, `sha256sum`, `mktemp`, `install`, `awk`, `timeout` | the gate and the host action scripts | bash 5.3.9; `sort` here is the uutils implementation | not established | various, not verified |
| Docker | the two pinned images in the gate and `demo/render.sh` | 29.9.3 | not established | not verified |
| `git` | `mcp-install` (clone and detached checkout) | not queried | not established | GPL-2.0, not verified |
| Proxmox VE tools on the host: `pvesh`, `pveum`, `qm`, `pct`, `pvesm`, `vzdump`, `pveversion` | invoked by the host action scripts, never installed by them | not available here (stubs in `tests/stubs/`) | the plan targets 9.1 and reads the 9.2.14 schema | AGPL-3.0 for the Proxmox VE packages, not verified |

## 4. Upstream procedures and documents the scripts follow

| What | Followed by | Origin | Version or retrieval | Licence | State |
|---|---|---|---|---|---|
| Fedora CoreOS on Proxmox VE: import the `proxmoxve` image, add a cloud-init drive and a serial console, convert to a template; Ignition delivered through `cicustom` | `host/actions/fcos-template.sh` | `coreos/fedora-coreos-docs`, `modules/ROOT/pages/provisioning-proxmoxve.adoc`, recorded as SR-22 in [`docs/.prepare/source-register.md`](../../docs/.prepare/source-register.md) | repository head `e3e27608d9` of 2026-11-03, retrieved 2026-11-14 (reported by the source register; not re-fetched) | not verified | the lab procedure itself was never tried |
| Butane configuration, variant `fcos` 1.6.0 | `demo/fcos-demo.bu`, `demo/render.sh` | the Butane specification shipped with the pinned image | v0.23.0 per the image tag | not verified | `butane --strict` passes in the gate when the image is present (offline only) |
| Proxmox VE API schema and the `pveum` chapter (privileges per operation, token handling) | the design plan's rows R-01 … R-24 (the plan is kept outside the repository), `bootstrap`, the routine ACLs | Proxmox VE documentation | docs version 9.2.14 (built 2026-11-06), as stated in that plan | not verified | live behaviour on 9.1 is unverified |
| OpenSSH `authorized_keys` options and forced commands | the snippet writer's access model | the OpenSSH manual pages | not recorded | not verified | the real sshd behaviour (test S7 and the other host-side checks) is unverified; the offline tests do not run a real sshd |
| Claude Code hooks, permissions and sub-agent documentation | the guard hook and the `pve-lab` agent definition (the active copies are kept outside the repository; tracked candidates are in [`../proposed/`](../proposed/README.md)), and the settings entries | `code.claude.com/docs/en/{hooks,permissions,sub-agents}` | read 2026-11-16, per the design plan (kept outside the repository); client 2.1.325, per the same plan | not verified | the harness behaviour the guard relies on is unverified (README, "Open items") |

## 5. Authorship of the tooling itself

The code, scripts, tests and documents under `lab-agent/` were written for this repository by
Claude Code sessions on the owner's requests of 2026-11-16 (design plan header; the plan is kept
outside the repository). No licence is chosen
for them. The IDs, hashes and tags quoted above are not secrets. No real name, mail address,
host name or lab address appears in this document.

## 6. What would change this document

- Moving the MCP pin (re-review first, per `mcp-server-review.md`), or adding any vendored
  file or image: add a row in § 2.
- The owner choosing a licence (D-53 is deferred): update § 1 and § 5 only after that
  decision is recorded.
- Fetching the licences listed as "not verified": this requires network access, which the
  work that wrote this document did not use. (A separate review made read-only requests to the
  public upstream repository of the MCP server; see § 2.)
