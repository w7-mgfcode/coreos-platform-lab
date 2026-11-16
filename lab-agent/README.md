# lab-agent — Proxmox lab tooling for CoreOS Platform Lab

Supporting development tooling: it prepares, operates and cleans the disposable Proxmox lab the
platform is built on. **It is not a homework deliverable.** Its results are not evidence for any
AC-NN (`docs/architecture.md` § 10), and it never configures the platform VM (Butane and Ignition
do). Its own gate, `lab-agent/tests/run.sh`, is **not** the repository's planned platform static
gate (`.claude/rules/test-requirements.md`, "Gates"), which does not exist yet.

The design plan this tooling was written against is kept outside the repository. Where a
statement below rests only on that plan, it is marked as a design intention.

## Status

> **Inclusion is not authorization.** The tooling was excluded from the initial publication
> (decision D-49) and is included by the owner's decision D-57 of 2026-11-16. That decision
> publishes verified, bounded tooling. It authorizes no further contact with the lab: stages
> L2 to L5 (host access, snippet writer, guest lifecycle) wait for the owner, and the
> implementation gate (D-09) stays closed until `docs/.prepare/decision-log.md` § 5 says
> otherwise. Both owner gates are described in `AGENTS.md`.

Five states, kept apart. Do not read one as another.

| # | State | What it covers |
|---|---|---|
| 1 | **The platform is planned and unbuilt** | The platform (Compose stack, Butane, firewall, tests) does not exist in this repository yet. This tooling supports development; nothing it does counts as a requirement being built, tested or passed. |
| 2 | **Verified offline** | Fixtures, stub Proxmox tools and fake transports, through `tests/run.sh` (seven checks) and `tests/run-netless.sh` (the whole unit suite in a container with loopback only). Both passed on the tree that was included, on 2026-11-16, before this documentation change. An offline pass says nothing about a real host. |
| 3 | **Verified live, once, read-only, 2026-11-16** | The API client's TLS verification against the CA file the owner supplied, with a host-name check; token authentication; read access to the version, the node list, the VM inventory and the token's effective permissions (audit privileges only). Five `GET` requests, under the two narrow dated owner approvals in `docs/.prepare/decision-log.md` § 5. Both approvals are used up. This is not evidence for any requirement. |
| 4 | **Never run against a host** | `lab-agent discover` as a command; a live `baseline verify`; every SSH path (the snippet writer included); the MCP server path and the `pve-lab` agent; every host-side action (`preflight`, `discover-host`, `backup-config`, `bootstrap`, `prepare`, `fcos-template`). Every host-side statement in these documents is **NEEDS-LIVE**. |
| 5 | **Disabled or blocked** | Cleanup execution is disabled in code; the `sentinel` action is blocked by an open review finding; the recorded limitations are listed below. |

The state-3 check exercised the API client only (its TLS handling, authentication and the
reads named above). The `lab-agent discover` command was not run, and the check says nothing
about the host side.

## What this version does and does not do

| Capability | State |
|---|---|
| `lab-agent classify`, `inventory verify`, `baseline save`, `sanitize`, `scan` | usable offline, on inventories and files you hand them |
| `lab-agent discover`, and `baseline verify` without `--inventory` | need the API token. State 4: neither has run as a command against a host. The API client they share is the state-3 part |
| Cleanup planning: `lab-agent manifest build`, `check`, `dry-run`, `hash` | usable. `build` and `check` recompute the classification from the settings, the inventory and the overrides and refuse a classification file that differs; pass `--overrides` with the file the classification was made with |
| Preview of a cleanup script: `host-run show apply-manifest` | usable as a **preview only**. The request is fully validated. In the printed script the manifest body's first command is the refusal (in an ordinary shell: exit 7 before any read), and the script contains no stop, backup, destroy or free command as executable text |
| **Cleanup execution: `host-run run apply-manifest`** | **DISABLED in code.** The request is validated, the plan is listed, and the run is refused (exit 2) before anything is rendered for approval or sent |
| `host-run run sentinel` | **BLOCKED** by an open review finding: the script does not check that the storage directory is the one `prepare` made, or that nothing is mounted beneath it. `show sentinel` still prints it |
| `host-run run preflight`, `discover-host`, `backup-config` (read-only), `bootstrap`, `prepare`, `fcos-template` | rendered and reviewed offline; never run on a host; every host-side claim is NEEDS-LIVE |
| `lab-agent mcp-install`, `mcp-launch`; the MCP server | the pinned server was never installed, started or contacted by this tooling; tested offline against mocks and throwaway local repositories only |
| `python3 -m lab_agent.privmatrix` (operation-to-privilege matrix from an API description file) | offline; it opens one local file. Tested on a synthetic fixture only: no real API description was processed |

**Why execution is disabled.** Removing guests and volumes safely needs guarantees this tooling
does not have: the window between the last check and the command is open; that the guest and
volume listings are complete, and that no other volume depends on a removed one, is unproven; an
inactive storage hides its volumes. So three things hold, independently: `host-run run` refuses the
action; in an ordinary shell `host/lib.sh` stops at `cl_destructive_gate` (exit 7), and the body of
every rendered manifest script calls that gate as its first command; and the destructive commands
stand in the library only as `# DISABLED-COMMAND:` comments, which is what still holds in a shell
whose `exit` has been replaced (such a shell runs past the gate and reads the host, but finds
nothing destructive to run). This is not containment against code injected into the shell. No
setting or argument turns execution back on; re-enabling it is a code change that needs its own
review and an owner decision.
The stub-tool tests of the guards run a test-only copy (`tests/fixtures.py`, `for_stub_run`) in
which the gate is a no-op and the comments are commands again. A stub pass is not evidence that
execution is safe.

### Recorded limitations (state 5)

None of these is fixed. Each is a known gap, stated so nobody relies on the opposite.

- `lab-agent manifest dry-run` accepts a manifest whose `reason` is not a string (a list, for
  example) and prints it instead of refusing it; it checks the structure only, and
  `manifest check` is the validation.
- The snippet writer removes its temporary file when it ends after a refusal or a handled
  signal, but one instant is not covered: between entering the `END` phase of the Perl script
  and the point where it starts ignoring the four signals. A signal in that instant, like
  `SIGKILL`, an out-of-memory kill or a power loss, can leave a stale `.corelab-tmp-*` file
  (never listed; the owner may delete it).
- The test guard (`tests/__init__.py`) is a text screen on direct child commands and a block on
  in-process Python network use. It is **not containment**; the evidence that the suite makes no
  external connection is `tests/run-netless.sh`.
- `for_stub_run` in `tests/fixtures.py` recognises the shipped gate definition by the prefix of
  its line and replaces the whole line, whatever follows the prefix.
- The settings file is loaded (and its mode checked) before a blocked action is refused, so a
  broken settings file is reported first.
- The disablement is not containment against code injected into the shell (see above).

## Three modes, three credentials

| Mode | Who acts | Credential | Boundary |
|---|---|---|---|
| **A — Routine** | Claude Code subagent `pve-lab` through the pinned MCP server, plus `lab-agent` | pool-scoped API token; the snippet-writer SSH key | Proxmox RBAC; the forced command on the host |
| **B — Host administration** | the owner, with `host-run`, in their own terminal | passphrase-protected root key, never loaded into an ssh-agent | the key is unusable inside an agent session; the owner reads the script and types its hash |
| **C — Recovery** | the owner only | GUI `root@pam` login, offline recovery key | not on the workstation; never touched by automation |

This is the design. Mode A was exercised once, and only as the read-only API check of state 3;
modes B and C have not run (state 4). The `pve-lab` subagent definition and the guard hook are
kept as local, owner-controlled files outside the repository; the tracked, tested candidates
are in [`proposed/`](proposed/README.md) and are registered nowhere.

What is **not** a boundary, by design: the guard hook, the TTY and Claude-ancestry checks in
`host-run`, and the approval record. They prevent mistakes and leave an audit trail. The code
says why in the docstring of `lab_agent/hostrun.py`: git state proves nothing about review, the
approval record lives under the owner's user like everything else, and the same user can still,
for example, drive a terminal pane. The design plan makes the same argument for same-user
sockets and `ptrace_scope`; that part is a design intention recorded outside the repository.

## Layout

What is published in this repository:

```
lab-agent/
├── bin/lab-agent          routine CLI: discover, classify, inventory verify, manifest, baseline, sanitize, scan, mcp-install, mcp-launch
├── bin/host-run           owner-only privileged runner (Mode B)
├── bin/mcp-launch         starts the pinned MCP server (what a project `.mcp.json` entry runs)
├── env.example            settings template: documentation-range addresses and placeholders only
├── mcp.example.json       the `pve` entry for a project `.mcp.json`; the gate validates it. The working
│                          copy's own `.mcp.json` is kept outside the repository
├── lab_agent/             Python standard library only
│   ├── config.py          KEY=VALUE settings, private-file checks, token secret loading
│   ├── pveapi.py          API client: CA-verified TLS only, injectable transport, bound source address
│   ├── inventory.py       GET-only discovery and normalisation
│   ├── classify.py        PRESERVE / REUSE / MODIFY / REMOVE_CANDIDATE / UNKNOWN; VMID-range check
│   ├── manifest.py        cleanup manifest: schema, canonical hash, dry-run, revalidation, rendering
│   ├── baseline.py        record and compare the prepared state
│   ├── hostrun.py         render → review → hash confirmation → ssh with the root key
│   ├── mcp.py             pin, install and launch of ry-ops/proxmox-mcp-server
│   ├── privmatrix.py      operation-to-privilege matrix from an API description file (offline)
│   └── redact.py          redaction (logs), sanitization and scanning (public evidence)
├── host/lib.sh            helpers prepended to every host script
├── host/actions/*.sh      preflight, bootstrap, discover-host, backup-config, prepare, sentinel, fcos-template
├── host/snippet-writer/   corelab-snippet-put (Perl, forced command) and its config template
├── demo/                  demo Butane and render script (pinned Butane container)
├── docs/mcp-server-review.md             why this MCP server, and what was and was not checked
├── docs/l2-runbook.md                    owner procedure for L2 (authorizes nothing), and what another workstation needs
├── docs/dependencies-and-attribution.md  third-party components, pins, licences and what is not verified
├── docs/proposed-patches/                the patches the candidate tests apply (hook and agent candidates)
├── proposed/              candidates for owner-controlled files: hook, agent definition, settings fragment
└── tests/                 offline tests, fixtures and stub Proxmox tools; run.sh is the gate
```

Kept **outside** the repository, on the owner's workstation only: the design plan and the
governance diff proposed for the project's own decision records, the working copy's `.mcp.json`,
the active guard hook and `pve-lab` agent definition, the dated close-out record of the first
offline stage, the owner's settings, state, logs, raw inventories and reports. Nothing published
here links to or depends on them; where a document needs the reader to know one exists, it says
so in words.

What a second workstation or a fresh clone needs and lacks (no local settings, so no guard
registration; symbolic links under `tests/stubs/`; file modes; Linux only) is in
[`docs/l2-runbook.md`](docs/l2-runbook.md), section "Portability". Third-party components and
their licences, with what is not verified, are in
[`docs/dependencies-and-attribution.md`](docs/dependencies-and-attribution.md). No project
licence is chosen (decision D-53 deferred it).

## Testing (offline)

```bash
lab-agent/tests/run.sh
```

The gate runs the Python unit tests, `perl -c`, `bash -n`, shellcheck (pinned container),
`butane --strict` (pinned container) and JSON checks. Every Proxmox interaction is a fixture
(`tests/fixtures.py`) or a stub tool (`tests/stubs/`). No secret file is needed.

The unit tests install a guard (`tests/__init__.py`) that prevents in-process Python network
use and screens direct child commands. The screen is a text match, not containment. The evidence
that the suite makes no external connection is a separate acceptance command,
`lab-agent/tests/run-netless.sh`: the whole suite in a container whose only interface is loopback
(local image, never pulled).

The gate never pulls or installs anything. If Docker or a pinned image is missing, that
check is `SKIP` and is named in the summary, and so is any skipped unit test. Exit status:
`0` with `RESULT: PASS` only when all seven checks ran and passed; `1` with `RESULT: FAIL`
when any check failed; `2` with `RESULT: INCOMPLETE` when nothing failed but something was
skipped. `tests/test_gate_run.py` proves this with an isolated `PATH`.

Two checks stay outside the gate. `python3 lab-agent/tests/check_local_settings.py` reports,
by hand, whether the checkout it lives in has exactly one guard registration in its Claude Code
settings (names, counts and booleans only); a fresh clone has none and the script says so.
`lab-agent/tests/o4/run-o4.sh` runs the real snippet writer behind a real sshd in a throwaway
container with no network, from images already present locally; it never pulls or installs.

## Setup for L2 (owner, only after L2 is authorized)

L2 is the first stage that contacts the host. It is **not authorized**: it needs the owner's
recorded decision and a dated approval line in `docs/.prepare/decision-log.md` § 5 that covers
it. The ordered owner procedure, including the explicit source address
(`PVE_WORKSTATION_ADDR`), the `pve-snip` SSH alias, the offline pre-checks and the live
acceptance checks, is [`docs/l2-runbook.md`](docs/l2-runbook.md). It authorizes nothing and none
of its live steps has run. The summary below is not a substitute for it.

1. Create the settings directory private, then copy `env.example` into it, fill it in, `chmod 600`:
   `install -d -m 700 ~/.config/corelab-lab-agent && cp lab-agent/env.example ~/.config/corelab-lab-agent/env`.
   `host-run` refuses to write the token into a directory that is a symlink, belongs to another user
   or grants any group or other permission (it must be mode 700); this is checked before anything
   runs on the host.
   `PVE_WORKSTATION_ADDR` is required: one literal IP address of this machine (no name, pattern
   or list, same family as an IP-literal `PVE_HOST`). The owner-run ssh binds to it
   (`-F none -o BindAddress=…`). `host-run` refuses before the confirmation prompt if the address
   is not assigned locally. `lab-agent` also binds its API connection to it, never uses a proxy and
   refuses if an environment HTTPS proxy would carry that connection; without the setting the API
   client refuses to connect. Binding sets the source address only, not the route: see
   [`docs/l2-runbook.md`](docs/l2-runbook.md).
2. Create the keys. The root key **must** have a passphrase; `host-run` refuses one without.
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/corelab-pve-root      # passphrase required
   ssh-keygen -t ed25519 -N '' -f ~/.ssh/corelab-pve-snip
   ```
   Never `ssh-add` the root key.
3. In the Proxmox GUI node shell (`root@pam`), add the root public key to
   `/root/.ssh/authorized_keys` with `from="${PVE_WORKSTATION_ADDR}"` (the literal address, one only).
4. Pin the host key: compare `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` (GUI shell)
   with `ssh-keyscan -t ed25519 <host>`, then save the line to `PVE_KNOWN_HOSTS`.
5. Copy `/etc/pve/pve-root-ca.pem` to `PVE_CA_FILE` and compare its fingerprint with the GUI.
   The API client trusts only this file and checks the host name. It clears one flag on its
   own TLS context, `VERIFY_X509_STRICT` (set by default from Python 3.13): the CA a Proxmox
   host generates has no key usage extension, and strict verification refuses it (OpenSSL
   verify code 92). Chain, validity and host name are still verified; there is no unverified
   fallback. `tests/test_tls_strict_compat.py` shows this with real fixture certificates
   (their provenance is in [`tests/README.md`](tests/README.md)), and
   the read-only API check of state 3 is the one live use of this setting.
6. In **your own terminal** (not a `!` command, not an agent-controlled pane):
   ```bash
   lab-agent/bin/host-run run preflight
   lab-agent/bin/host-run run bootstrap     # writes the read-only token to PVE_TOKEN_FILE
   ```
7. `lab-agent/bin/lab-agent mcp-install`, then start Claude Code and approve the `pve` server.

## Routine commands

```bash
lab-agent/bin/lab-agent discover                                       # GET-only inventory → PVE_LAB_STATE; exit 1 if incomplete
lab-agent/bin/lab-agent classify --inventory INV --overrides OV --out CLS
lab-agent/bin/lab-agent inventory verify --inventory INV --raw RAW     # is INV exactly what RAW gives?
lab-agent/bin/lab-agent manifest build --inventory INV --classification CLS --overrides OV --out M.json
lab-agent/bin/lab-agent manifest check M.json --inventory INV --classification CLS --overrides OV
lab-agent/bin/lab-agent manifest dry-run M.json
lab-agent/bin/lab-agent manifest hash M.json
lab-agent/bin/host-run show apply-manifest --manifest M.json --inventory INV --overrides OV   # preview only
# host-run run apply-manifest ... is DISABLED in this version: it validates, lists the plan and refuses (exit 2)
lab-agent/bin/lab-agent baseline save --inventory INV --out BASELINE
lab-agent/bin/lab-agent baseline verify --baseline BASELINE            # live read; add --inventory FILE to compare offline
lab-agent/bin/lab-agent sanitize RAW.txt docs-ready.txt && lab-agent/bin/lab-agent scan docs-ready.txt
```

Overrides are the only way to propose a removal; each needs written evidence:

```json
{"vm/105": {"class": "REMOVE_CANDIDATE", "evidence": "old k8s lab node, stopped since 2025, owner confirmed"}}
```

`discover` writes `raw.json` and `inventory.json` (mode 600) into `--out-dir`, or by default into
`inventory-<timestamp>` under `PVE_LAB_STATE`, where the timestamp has a resolution of one second.
A missing directory is created mode 700 (with its missing ancestors); an **existing** one is
reused, and its two files are replaced, if it is a real directory of this user with mode exactly
700 and no symlink at the destination files, otherwise `discover` refuses. So an existing private
`--out-dir`, or a second default run in the same second, overwrites the earlier files of the same
name. It writes the inventory even when an
endpoint was refused or a storage was inactive;
the gaps are listed under `errors` and the exit status is 1. `classify`, `manifest build`/`check`
and `baseline save`/`verify` then refuse (exit 2) and name the unread endpoints their result
depends on. `host-run apply-manifest` needs the inventory the manifest was built from (its
`inventory_digest` must match) and the overrides file: it recomputes the classification and
refuses any item that is not REMOVE_CANDIDATE, before anything is rendered or sent.
Each inventory section accepts only ids of its own form. Malformed input is refused with exit 2.
Four malformed values that an earlier version of this file listed as ending in a Python traceback
were tried again on 2026-11-16 with synthetic inputs: an object as a manifest field (`manifest
check`), a non-string override evidence (`classify`), a classification entry without `reason`
(`manifest build`) and a stored baseline that is not an object (`baseline verify`) are all refused
with exit 2. One laxness was seen in the same trial and is not fixed: `manifest dry-run` prints a
manifest whose `reason` is a list instead of refusing it (exit 0); see the recorded limitations.
`apply-manifest` also needs `PVE_SENTINEL_VMID` and `PVE_POOL` (default `corelab`), and the
script carries both. **Execution is disabled in this version** (see the table above); what
follows describes the guards the previewed script contains, which run only in offline stub tests.
In an enabled version, before anything is removed, the script would check on the host that:

- a guest is not the sentinel, still exists, and its live pool equals the pool recorded in the
  bound inventory;
- a volume does not belong to the sentinel and is not used by a guest outside the pool.

Any of these stops the script with exit 6. The pool check compares with the recorded pool, not
with `PVE_POOL`, so owner-evidenced leftovers outside the pool can still be removed.

## Data handling

- Raw inventory, run logs, approvals, host backups and audit logs live in `PVE_LAB_STATE`
  (mode 700/600), outside the repository. Host backups contain `/etc/pve/priv`, so treat
  them as secrets.
- The token secret is read only by the MCP launcher and the API client, is never printed,
  and is redacted from every log line. `bootstrap` output is intercepted by `host-run` and
  written straight to `PVE_TOKEN_FILE`.
- Evidence for the repository goes through `sanitize`, and `scan` must report nothing.

## Open items (owner)

Still open after inclusion; none is settled by this document or by the inclusion decision.

- **SET-1.** Whether the `mcp__pve__*` permission should be allowed for every session in a
  checkout. Options and consequences, all conditional on unanswered harness questions, are in
  [`docs/mcp-server-review.md`](docs/mcp-server-review.md) ("SET-1 and B-S1"); the recommended
  option is a proposal in [`proposed/settings/`](proposed/settings/README.md).
- **Installing the candidates.** The hook and agent candidates in [`proposed/`](proposed/README.md)
  are tracked and tested but registered nowhere and installed nowhere. Installing them, and
  registering the guard hook in a given checkout, is an owner action. A clone has no guard hook
  and no `mcp__pve__*` deny rules until the owner supplies them.
- **Review coverage.** The tooling was reviewed in independent rounds before inclusion. The last
  small change before inclusion (moving the four TLS test fixtures and the test module's path
  constants) was reviewed independently with no blocking finding. That verdict is by reading and
  by hash and certificate inspection only: the reviewer's read-only sandbox could not execute the
  test. **Not independently confirmed:** that the source-address and SSH-option statements of
  [`docs/l2-runbook.md`](docs/l2-runbook.md) are handled in code, which is the documentation
  author's own reading and goes to a final review; and the full suite, which no reviewer has
  executed (the gate and the network-less suite were run by the authoring side). Treat the
  offline pass as covering the tree it ran on.
- **O-4 is partial.** The snippet writer is tested as the current user, and a harness exists
  for a real sshd in a throwaway container, but the real `corelab-snip` user, the root-owned
  directory and the forced command on the host (the `from=`/`restrict` path) have not been
  exercised on a host.
- **O-7 is incomplete.** The operation-to-privilege matrix generator exists and runs on a
  synthetic fixture. It has not processed the real API description for the Proxmox version in
  use, and the role contents it assumes were not confirmed on a host.
- **Harness behaviour unverified:** whether a hook's `onFailure: "block"` is honoured, whether
  the subagent name reaches the hook inside `pve-lab`, and whether the agent definition's
  frontmatter limits its tools as intended.
- **Pin review.** The MCP server pin was re-read at the pinned commit (licence, tool names), but
  its locked dependencies, a running server's advertised tool list and its maintenance over time
  are not verified.
- **Before L3 or L4** (guest lifecycle and cleanup): no agent-side sentinel protection when
  `PVE_SENTINEL_VMID` is missing or `0`; the volume-usage check lacks a positive control and
  misses some kinds of reference; a few malformed inputs still end in a traceback instead of
  exit 2 (all fail closed).
- **L2 to L5** themselves, the decisions about re-enabling cleanup execution or unblocking the
  `sentinel` action, and any contact with the lab.
