# MCP server review (L1, 2026-11-16)

Source code was read at the commits below. Nothing was run against a Proxmox host. The one live
check made with this tooling, a read-only API check on 2026-11-16 (README, state 3), used the
API client and did not involve the MCP server: the server was never installed, started or
contacted by it. Every statement here about the server's behaviour is offline (source reading,
mocks, throwaway local repositories) or NEEDS-LIVE. The deny list and the permission entries this
document discusses live in the owner's untracked local settings, outside the repository; the
candidates in `lab-agent/proposed/` are tracked and registered nowhere.

## Candidates

| | ry-ops/proxmox-mcp-server | RekklesNA/ProxmoxMCP-Plus |
|---|---|---|
| Commit reviewed | `69686b06347c89d85c3725cf4a730c979b0148b7` (v2.14.0, 2026-11-12) | `a8b5edb15e5803241a20d3c31629ec6d0454dc87` (2026-11-16) |
| Licence | MIT (`LICENSE`, `pyproject.toml`) | MIT (`LICENSE`) |
| Size | about 9.6k lines of Python | about 14.9k lines of Python |
| Runtime dependencies | `mcp`, `httpx`, `python-dotenv`, `starlette`, `uvicorn` | `mcp`, `proxmoxer`, `requests`, `pydantic`, `fastapi`, `uvicorn`, `mcpo`, `paramiko`, `asyncpg`, `opentelemetry-api`, `pydantic-monty`, … |
| Lockfile | `uv.lock` (hash-pinned), used with `uv sync --frozen` | `requirements/runtime.lock` |
| TLS | `PROXMOX_CA_BUNDLE` builds an SSL context from the CA file; a bad file stops the server (`client.py`). Default without a CA is unverified **with a warning**, so the launcher always sets the CA | verification on by default; off only in dev mode (`config/loader.py`) |
| Token handling | environment variables `PROXMOX_USER`, `PROXMOX_TOKEN_NAME`, `PROXMOX_TOKEN_VALUE`; the audit log redacts secret-looking fields | config file or environment |
| Subprocess or SSH code | none found (`grep subprocess\|paramiko\|asyncssh`) | `paramiko` SSH to nodes for container command execution |
| Clone into a pool | `clone_vm` takes `pool`, `newid`, `full`, `storage` | not confirmed in source |
| `cicustom`, `ipconfig0` | `set_vm_config` passes any config key; `create_vm` has `extra_config` | not confirmed in source |
| Restricting the surface | `PROXMOX_TOOLSETS`, `PROXMOX_READ_ONLY`, `PROXMOX_NO_DESTRUCTIVE`, `PROXMOX_PROTECTED_VMIDS`; tools carry `readOnlyHint` / `destructiveHint` | tool allowlist, approval token, command policy |
| Path safety | refuses `.`/`..` segments and `?#\` in API paths | not reviewed |

## Decision

**ry-ops/proxmox-mcp-server at `69686b06347c89d85c3725cf4a730c979b0148b7`.** It covers every routine operation the demo needs (clone into the pool, arbitrary config keys for `cicustom`/`ipconfig0`, snapshots, backup and restore, delete), has a small dependency set with a hash-pinned lockfile, contains no SSH or subprocess code, and can verify TLS against the cluster CA. ProxmoxMCP-Plus has more built-in governance, but brings SSH execution and a much larger dependency tree we would not use. In this design RBAC is the boundary, so built-in governance in the server adds little.

## How it is configured (`lab_agent/mcp.py`)

- Installed with `lab-agent mcp-install`: `git clone`, `checkout --detach <commit>`, a check that `HEAD` equals the pin, then `uv sync --frozen --no-dev`. Launched with `uv run --frozen --no-sync` from an empty working directory, so no stray `.env` is read.
  *Note of 2026-11-16.* "So no stray `.env` is read" overstated it. The server calls
  `load_dotenv()` in `proxmox_mcp/client.py` (observed in the source at the pin). python-dotenv's
  default search starts from the calling file's directory, not from the working directory (recalled
  from its documentation; the library is not installed here and was not read). The launcher now also
  sets `PROXMOX_PASSWORD` to empty, because python-dotenv does not override a variable that is
  already set, and refuses a working directory that holds an `.env*` entry. See "Update of
  2026-11-16" below.
  *Second note of 2026-11-16 (after an independent review).* `git` and `uv` are no
  longer looked up through whatever `PATH` the caller has. Paths are made absolute before the
  working directory changes, and `git` and `uv` run with an allow-listed environment. Details and
  limits in "Round 2" below.
- `PROXMOX_CA_BUNDLE` is always set. `PROXMOX_VERIFY_SSL` is never set to false.
- `PROXMOX_TOOLSETS=nodes,qemu,storage,pools,cluster`. Not loaded: access, firewall, disks, ceph, acme, sdn, notifications, appliances, lxc, pdm.
- `PROXMOX_PROTECTED_VMIDS` covers up to 100,000 IDs on each side of `PVE_VMID_RANGE`, so the server's own guard refuses writes outside the project range. This protects VMID hygiene; RBAC remains the boundary. The server caps each range at 100,000 IDs, so IDs further away are not covered.
- `PROXMOX_AUDIT_LOG` writes to `PVE_LAB_STATE/mcp-audit.jsonl`.
- The project's permission settings deny 39 host-level or out-of-scope tool names. When this review was written they were in the tracked `.claude/settings.json`; since 2026-11-16 they are in the untracked `.claude/settings.local.json` (see the note below). The names: (node services and power, network apply, storage and pool definitions, HA, replication, backup jobs, bulk actions, migrate, disk import from host paths, guest password changes).
  *Note of 2026-11-16.* These deny entries were moved verbatim to the untracked
  `.claude/settings.local.json` when the tooling was excluded from the initial publication
  (D-49). They stay there after the tooling's inclusion (D-57): a clone does not have them, and
  this repository supplies none. The count (39) and the names are unchanged.

## Checks performed (offline, 2026-11-16)

These rows are the first review's dated observations. This document does not record where the
`uv sync` was run or how the tool count was obtained, and **neither was re-verified** here: the
later "Update of 2026-11-16" read the upstream source only ("Nothing was cloned, executed or
installed, and `uv sync` was not repeated"; "a running server was not started"). Read the first two
rows as unconfirmed observations, not as evidence that the server was installed or started by
this tooling, which it never was against a host (see the opening paragraph).

| Check | Result |
|---|---|
| `uv sync --frozen --no-dev` at the pinned commit | reported as succeeded by the first review; not repeated, and the locked dependencies are listed as not verified below |
| Tools advertised with the chosen toolsets | reported as 141 by the first review. The later source reading counted 141 tool names **defined** by the loaded toolsets (38 + 46 + 14 + 5 + 37 + 1); a running server's advertised list was not observed |
| Deny-list names that do not exist in that set (a typo would make a rule a no-op) | none; all 39 exist (checked against the 141 defined names) |
| Guest-agent tools left allowed | `vm_agent_exec` and five read/status tools. RBAC limits them to pool guests (`VM.GuestAgent.Unrestricted` on pool members) |
| Destructive tools left allowed | 15 (stop, delete, rollback, …); RBAC limits them to pool guests |

## Not verified (LIVE, L2–L4)

- Behaviour against Proxmox VE 9.1 (the server targets the current API).
- That `clone_vm` with `pool` and `set_vm_config` with `cicustom` work with the routine token (probes K-1, K-2, K-7).
- The server's maintenance over time. Re-review it before moving the pin.

*Status after 2026-11-16:* the list above stands. The pin review that an earlier close-out
record (kept outside the repository) listed as not done is now partly done (licence, tool
names); what it still leaves open is in "Still not verified" at the end of this file.

## Update of 2026-11-16

This section adds to the review above; nothing above was deleted. Categories: **observed** means
run or read in the work this section records, with the command or file; **reported** means taken
from an earlier close-out record kept outside the repository; **proposal** is for the owner; **live check not run** is listed at the end. Every test
result is offline only: a mock does not show live permissions, routing, recovery or host behaviour.

### Pin review, re-done from the upstream source (observed)

Method: read-only `GET` requests to the public upstream repository, all with the pinned commit as
the ref (git tree listing; `LICENSE`; `pyproject.toml`; the sources `proxmox_mcp/{registry,server,
guards,client,audit}.py` and `proxmox_mcp/tools/{nodes,qemu,storage,pools,cluster,tasks}.py`).
Nothing was cloned, executed or installed, and `uv sync` was not repeated.

| Question | Result |
|---|---|
| Licence at the pinned commit | `LICENSE` is the MIT text (copyright 2024-2026, the author); `pyproject.toml` has `license = {text = "MIT"}` and version `2.14.0`. The tree listing (94 files) is not truncated |
| Entry point the launcher runs | `[project.scripts] proxmox-mcp-server = "proxmox_mcp.server:run"` |
| Tool names defined by the loaded toolsets (nodes, qemu, storage, pools, cluster, plus the always-loaded tasks tool) | 141, all distinct (38 + 46 + 14 + 5 + 37 + 1); matches the 141 the first review advertised |
| The 39 denied names exist in that set | **Yes, all 39, each defined exactly once.** Source of the names: the pre-relocation copy of the settings file's deny list, a copy kept outside the repository (observed), which agrees with the count the checker reports for the live local settings (39 `mcp__pve__` deny entries, observed by `tests/check_local_settings.py`; it does not print names, so equality of the two lists is not shown) |
| Tools left allowed | 102. Destructive by the server's own prefix and name rules: 15 (`stop_vm`, `shutdown_vm`, `reboot_vm`, `reset_vm`, `delete_vm`, `convert_vm_to_template`, `rollback_vm_snapshot`, `delete_vm_snapshot`, `unlink_vm_disk`, `delete_vm_firewall_rule`, `vm_agent_exec`, `delete_storage_volume`, `restore_vm_backup`, `restore_container_backup`, `stop_task`): the earlier count holds. Guest-agent tools: `vm_agent_exec` plus five others: the earlier count holds |
| Escape hatch (a tool that takes a raw API path) among the allowed 102 | None found by name. The server refuses `.` / `..` segments and `?#\` in paths (`client.py`) |
| Server limits the launcher relies on | `PROXMOX_PROTECTED_VMIDS` accepts IDs and ranges and rejects a range with `hi - lo > 100000` (`guards.py`); `PROXMOX_CA_BUNDLE` set means the SSL context is built from that file and a bad file stops the server; without a CA bundle and without `PROXMOX_VERIFY_SSL=true` the default is **unverified** (warning only), so the launcher must always set the bundle |

The snapshot of the 141 names and the 39 denied names is a fixture in `tests/test_l1b_mcp.py`
(`PinReviewFixtureTests`), so a typo in the deny list or a drift between this document and the
code fails offline. The fixture is a copy and does not replace reading the source again when
the pin moves.

Not part of this re-check, still open: the `uv.lock` hashes and the transitive dependencies
(`mcp`, `httpx`, `python-dotenv`, `starlette`, `uvicorn` at the locked versions), whether the
names in the deny list match the names a **running** server advertises (the source defines them;
a running server was not started), and the server's maintenance over time.

Observation, not a finding against the pin: `set_vm_config` passes any configuration key (the
reason it was chosen, for `cicustom` and `ipconfig0`). Which keys the routine token may set on a
pool guest is decided by Proxmox permissions and was not tested (live check not run: K-1, K-2, K-7).

### Launcher and install code: defects found and fixed (observed, offline)

All changes are in `lab_agent/mcp.py`; the tests are `tests/test_l1b_mcp.py` (45 tests in round 1;
round 2, below, adds more). Most tests replace `subprocess.run`, `os.execve` and `os.chdir`. The
exceptions, named in round 2, run only local `git init` and `git commit` on throwaway repositories
in a temporary directory and use the real `chdir` there; none clones, installs or touches a network.
*Corrected in round 2:* round 1 said every test replaced these, and that nothing passed an
environment to a child; the first was too broad for round 2 and the second was wrong (see below).

| Finding | Before | After |
|---|---|---|
| "Empty working directory" was stated, never checked | `mcp-run` was created if missing; a pre-existing directory of any mode, a symlink, or one holding an `.env` was used as is | `run_dir()` refuses a symlink, a directory owned by another user or writable by group or others (round 3: any mode but exactly 700), and any `.env*` entry. It does not require the directory to be empty, because what the server itself writes there is unobserved |
| Stray `.env` could fill in settings | Only the variables the launcher sets were fixed | `PROXMOX_PASSWORD` is also set (empty), because the server would use a password if one were present and python-dotenv does not override a set variable. `PROXMOX_VERIFY_SSL` stays unset on purpose: with the CA bundle set it has no effect, and an existing test pins its absence |
| Protected VMID ranges at the ends of the ID space | The upper range ran past 999,999,999; a range at the top produced IDs that cannot exist | Both sides are clamped to 100 … 999,999,999 and a side with nothing to protect is left out; a range that fills the space yields `""`. Limits the server enforces (`hi - lo <= 100000`) are checked in the tests with a copy of its parser |
| Install failures | `git`/`uv` failing raised `CalledProcessError`, which the CLI does not catch, so a traceback | A non-zero exit of a step (`git clone`, `git checkout`, `uv sync`), and any `OSError` raised while starting one, become `ConfigError` naming the step; the message holds neither the command line nor the program's output. The programs' own stdout and stderr are inherited and appear unfiltered on the terminal. Other `OSError`s (for example creating the install directory) are not converted here; the CLI reports them with exit 2 |
| Missing `git` at launch | `FileNotFoundError` from `installed_commit` | Round 1: treated as "not installed". Round 2: `git` is resolved by `find_executable` first, so a missing or untrusted `git` is a `ConfigError` saying so; a `git` that fails to start is still "not installed" |

What the tests now prove, which was stated before but never tested: the launcher refuses when the
server is not installed, when `HEAD` is another commit, when it is a prefix of the pin, and when
`git` fails or is missing, and it launches (positive control) at the pin; `PROXMOX_CA_BUNDLE` is set
on every launch and `VERIFY_SSL` appears nowhere in the module; the toolset list equals the reviewed
one; the protected ranges at both ends, at the 100,000 cap and for invalid `PVE_VMID_RANGE` values
(each refused before any `chdir` or `exec`); the token secret appears only as
`PROXMOX_TOKEN_VALUE` in the server environment (not in argv, in the CLI's output, in a log
record, in any exception message, or in `repr` of the configuration); install does not read the
token file at all; install clones with `--no-checkout`, checks out `--detach` the full pin commit,
refuses a checkout that lands elsewhere before `uv` runs, and runs `uv sync --frozen --no-dev`
without any floating reference; `.mcp.json` carries no `env` block and no secret. Mutation check
(observed, on a scratch copy outside the repository): nine hand-made mutations of `mcp.py` were run
against the new tests and all nine were detected. They were: pin check removed, verification
switched off, an extra toolset, lockfile not frozen, a short commit in the checkout, the caller's
working directory kept, the secret copied into a second variable, the old unclamped VMID function,
and install errors not converted. This is a spot check, not a coverage claim.

Kept limitations (`KEPT-LIMITATION`): the launcher checks `HEAD` only. A modified tracked file or an
extra file in the install directory is not detected, so the install directory (mode 700 under the
state directory) is as trusted as the token file next to it. The launcher does not pass proxy
variables to the server; a host that needs one cannot use this launcher unchanged.

### Round 2: findings of the independent review (observed, offline)

The review of round 1 ended with three blocking findings and two should-fix findings. Each was
checked against the code and was real. State after the fixes:

| Finding | Check and fix | What the tests do | Still open |
|---|---|---|---|
| Relative `PVE_CA_FILE` or `PVE_LAB_STATE` changes meaning after `chdir` | Confirmed: `cfg.path()` only expands `~`, the CA was checked in the caller's directory and then passed as a relative name to a process whose directory was `mcp-run`. Now the state directory, install directory, audit log and CA bundle are absolute before any check and before `chdir`; the token file is read before `chdir` too | `RelativePathTests` use the real `chdir`, a relative CA, state and token setting, and competing files at the place the relative name would mean after the change (a different `ca.pem`, a different install directory). They assert the changed directory, that the trap is in place, and that the paths passed on are absolute and point at the intended files. A relative CA that exists only after the change is refused before it | `PVE_TOKEN_FILE` and others are read by `config.py` in the caller's directory; other callers of `cfg.path()` are not covered |
| Git environment redirects the pin check | Confirmed in principle (a `git -C` call honours `GIT_DIR`, `GIT_WORK_TREE`, and so on). `git` and `uv` now run with an allow-listed environment: `PATH` (validated), `HOME`, `LANG`, `TMPDIR` (the last two only when absolute), `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null` (git 2.32 or later), `GIT_TERMINAL_PROMPT=0`; for install steps also proxy and CA-file variables. Nothing named `GIT_*`, `UV_*` or `PROXMOX_*` is inherited. `.git` must be a real directory: a gitfile or symlink that redirects git elsewhere makes the directory "not installed" | `RealGitRegressionTests` run the real local `git` on throwaway repositories in a temporary directory: the premise (an unsanitized call reports the other repository's `HEAD`), `GIT_DIR`, `GIT_DIR` with `GIT_WORK_TREE`, `GIT_COMMON_DIR` and `GIT_OBJECT_DIRECTORY` no longer redirect, a redirecting gitfile is refused, and `launch` refuses a checkout whose `HEAD` is not the pin although `GIT_DIR` makes another repository look like the pin (with a positive control). `ToolEnvTests` fix the exact variable set | `uv` still reads user and project configuration files; the options in the user's own git configuration are ignored only on git 2.32 or later |
| Caller-controlled `PATH` picks the program that receives the token | Confirmed: `execvpe("uv")` used the caller's `PATH`. Now `find_executable` is used for `git` and `uv`, and `launch` runs `os.execve` with the absolute path. It refuses an unset or empty `PATH`, an empty or relative entry, an entry that resolves inside the install tree or the run directory, a program that resolves inside them (also through a symlink), a program or its directory owned by someone other than root or this user, and one writable by group or others. (Round 2 as first written checked only the resolved file and its immediate directory and returned the unresolved path; corrected in round 4, below.) The server's own `PATH` is the same validated list | `ExecutableResolutionTests` on real files and directories (planted `uv` in the run directory, `.`/empty/relative entries with the working directory set there, entries and symlinks that resolve inside, unsafe modes, another owner by patching the uid, the first match wins); `LaunchResolutionTests` run `launch` with the real lookup and check which file is passed to `execve`; `ServerEnvPathTests` | The caller still chooses which absolute directories are searched: an attacker who controls a directory that is root- or user-owned and not writable by others is out of reach of this check. A directory writable by the group (for example some package-manager prefixes) is refused |
| SET-1 text states unverified behaviour as fact | Rewritten below, and in the proposal README: each consequence is an intention conditional on a numbered harness question | `SetOneFragmentTests` assert the README names the reviewed commit | The harness questions are unanswered |
| Snapshot not bound to a commit | `REVIEWED_COMMIT` is written out in the test module and compared with `mcp.PIN["commit"]`; the fragment README must name it too | `test_the_snapshots_belong_to_the_pinned_commit`, `test_the_fragment_is_checked_against_the_snapshot_of_the_pinned_commit` | The comparison catches a moved pin. It does not show where the copied names came from: that provenance is this document (read-only requests of 2026-11-16) |
| Three unsupported claims | (a) "install passes no environment to git or uv" was wrong: a child with no `env` argument inherits everything. Fixed in code (allow-listed environment) and in the test, which now checks the environment actually passed. (b) "which failures become refusals": only a non-zero exit and `OSError`s from starting a step become `ConfigError`; other `OSError`s (the install directory cannot be created) reach the CLI's `OSError` handler, which also exits 2. Stated in the table above. (c) Child stdout and stderr are inherited, so "no command line in diagnostics" holds only for the messages `mcp.py` itself raises | tests named above | |

Also corrected: the entry for `.claude/settings.json` in "How it is configured" said the deny list
is in the tracked file; it now says where the list was and where it is.

New file, no change to anything active: [`../mcp.example.json`](../mcp.example.json) is a
example of the project MCP entry, with the same structure as the working copy's own
`.mcp.json`, which is git-ignored and kept outside the repository. `ExampleEntryTests` check its
shape, that it carries no value, and that it equals the local entry when one exists.

Mutation spot check of round 2 (observed, scratch copy outside the repository): see the report.
This section does not claim more than the tests above show. Mocks never proved live behaviour; the
real-git and real-file tests prove the behaviour of git and the file system on this machine only.

### Round 3: validated host and port, descriptor-based private directories (observed, offline)

Requested by the lead after the transport work finished. `mcp.py` now uses `cfg.host()` and
`str(cfg.port())` for `PROXMOX_HOST` and `PROXMOX_PORT`, so a malformed `PVE_HOST` or `PVE_PORT`
(white space, a port, a user, a path, an option-like leading `-`, a wildcard address, a non-ASCII
or signed port) is a `ConfigError` before any launch step, and the server receives the canonical
form (an IPv6 literal compressed, a port without leading zeros). Directories are created through
`config.open_private_dir` and `config.open_private_subdir`: the install parent `mcp` and the run
directory `mcp-run` are made as mode 700 whatever the umask, and a symlink, another owner or any
mode other than exactly 700 is refused. This is stricter than round 2, which accepted a directory
that others could not write. `launch` also keeps the descriptor of the checked `mcp-run` and
changes into it with `os.fchdir`, then closes it, so the path cannot be swapped between the check
and the change. Tests: `HostAndPortTests`, and additions to `RunDirTests` (umask 000, 022, 077 and
277; modes 770, 750, 755 and 707 refused; no descriptor leaked after a refusal) and `InstallTests`.

Limits: the directory the checkout is cloned into (`proxmox-mcp-server-<commit>`) is created by
`git clone`, not by this module, and its mode is not checked. The `uv` process started afterwards
resolves paths by name again.

### Round 4: executed path and ancestry, install parent (observed, offline)

The recheck of the round 2 and 3 fixes found one blocking and one should-fix problem in the round 2 and 3 fixes.
Both were real in the code:

| Finding | Fix | Tests | Still open |
|---|---|---|---|
| `find_executable` checked the resolved file and its immediate directory but returned the unresolved candidate; a symlink in a directory others can write could be swapped between the check and the exec; directories higher up were not checked | `find_executable` now returns the **resolved target**, and `launch` and `install` execute exactly that path. The target must be a regular file owned by root or this user and not writable by group or others, and so must every directory from its parent up to `/`. A sticky directory owned by root (such as `/tmp`) is the only exception; a sticky bit on a directory of ours is not | `ExecutableResolutionTests`: a symlink in a world-writable directory returns the target, and a later swap of the link does not change the returned file; group-, world- and sticky-writable ancestors are refused with a positive control; a link whose own directory is private but whose target's ancestry is not is refused; `LaunchResolutionTests`: the file passed to `execve` is the resolved target | The executable is not held open by descriptor: root or the current user could still replace the file or a directory above it, which is outside what this check can exclude. A multi-call binary that needs its own name does not work. Group-writable ancestors (some home-directory setups, package-manager prefixes) are refused |
| The install parent `<state>/mcp` was validated only when `HEAD` differed from the pin, and never on launch | `install` validates it first, always; `launch` validates it before git or the project is used, and a parent that does not exist is "not installed" and is not created by `launch` | `InstallTests` (already-pinned checkout under mode 755 and 770, and under a symlink: refused with no process started); `LaunchRefusalTests` (modes 755, 770, 750, a symlink: refused and git never asked; positive control; a missing parent is not created) | The directory `git clone` creates for the checkout (not made by this module); the parent is checked, not the checkout inside it |

Corrections to earlier wording: round 2 said the program's directory was checked ("owned by another user
or writable"); that meant the immediate directory only. Round 3 said an existing wrong install parent stops
`install`; that held only when the checkout was not already at the pin.

### SET-1 and B-S1: options for the owner (proposal)

State on 2026-11-16 in the owner's working copy (observed): `.claude/settings.local.json` holds the allow entry
`mcp__pve__*`, 39 `mcp__pve__` deny entries, the guard registration and two `Read(~/…)` deny
entries (`tests/check_local_settings.py`). That it also holds `enableAllProjectMcpServers` is
**reported** by an earlier close-out record kept outside the repository; the file itself was
not read. The two reasons the SET-1 row
gave for "no effect today": (1) the launcher refuses while the server is not installed. This is now
**tested offline** (`LaunchRefusalTests`, and the CLI path returns exit 2 with nothing on stdout; it
shows the launcher's logic, not what the harness does with the failed start). (2) "a project MCP
server needs approval": with `enableAllProjectMcpServers` present it may not hold (B-S1); what the
harness does with that key is unobserved here (question 1 below).

Every consequence below is **conditional**: it describes what would follow if the harness behaves
as the Claude Code documentation is remembered to say. None was tested in this checkout. The
conditions are the numbered questions in "Questions for the harness test".

| Option | What it does | Consequences, if the conditions hold |
|---|---|---|
| A. Keep as is | `mcp__pve__*` allowed for every session, all project MCP servers pre-approved | If an allow entry covers the call without a prompt (question 2), then after L2 installs the server **any** session in this checkout (a worker, a reviewer, a session that read untrusted text) could call the 102 non-denied tools without a prompt, including 33 that are not read-only (clone, delete, stop, restore, guest-agent exec, config changes). The Proxmox permissions of a pool-scoped token would bound the damage (live check not run). If a hook runs for such calls (question 4), the guard still inspects them. If `enableAllProjectMcpServers` approves every project server (question 1), any future entry in `.mcp.json` starts without approval too |
| B. No allow entry | Remove `mcp__pve__*`; every call would prompt; keep the deny list | The safest of the allowing options if unlisted calls prompt (question 2). A `pve-lab` run of many read calls becomes a stream of prompts, which invites approving without reading |
| **C. Reads allowed, writes prompt (recommended)** | Replace the wildcard with the 69 read-only tools by exact name; keep the 39 denies; replace `enableAllProjectMcpServers` with `enabledMcpjsonServers: ["pve"]` | If an unlisted call prompts (question 2), inventory and status work without prompts while the 33 other tools (writes, `vm_agent_exec`, console tickets) ask, in the main session and, if the same rules apply there (question 2), in `pve-lab`. If `enabledMcpjsonServers` approves only the listed servers (question 1), other project servers ask again. Costs: a maintenance step when the pin moves (moving the pin makes the fixture tests fail until the snapshot is re-read, which prompts the step; the tests show consistency with the pin, not the origin of the names), and a prompt for every write during a lab build |
| D. Server off by default | `disabledMcpjsonServers: ["pve"]`; the owner enables it for a deliberate lab session only | Strongest separation if the setting works as remembered (question 1); most friction; the deny list and, if question 4 passes, the guard hook stay as further layers |

**Recommendation: C**, on the condition that questions 1 to 4 are answered as hoped. It keeps the
read-only part automatic and would make every state change a visible owner decision. It does not
rely on wildcard matching of tool names: the names are explicit. If question 2, 3 or 4 fails (an
unlisted call does not prompt, deny does not beat allow, or the hook does not run for approved
calls), prefer D. The proposed fragment, with a README stating that it is not installed, is
[`../proposed/settings/set1-option-c.fragment.json`](../proposed/settings/set1-option-c.fragment.json);
it is tested in `SetOneFragmentTests` (valid JSON, only reviewed read-only tool names, none denied,
exactly the 69, no wildcard, no `enableAll…`; and the snapshot's commit equals the pin).

Unverified (recalled from the documented settings behaviour, not read or run here): the
precedence of local over project settings and the merge of `allow` lists; `deny` before `allow`;
`enabledMcpjsonServers` and `enableAllProjectMcpServers` semantics; the `mcp__server__tool` rule
form.

### Questions for the harness test (to be run in a scratch project, with a stub MCP server)

1. With `enableAllProjectMcpServers` set in local settings and a project `.mcp.json` server, does
   the server start with no approval prompt? Does `enabledMcpjsonServers: ["x"]` start only `x`
   and still ask for a second server?
2. With an allow entry for exact tool names and nothing for the others, does a call to an
   unlisted tool prompt in the main session, in a subagent, and under `acceptEdits` and
   `bypassPermissions`?
3. Does an exact-name deny entry beat a wildcard allow entry for the same tool, and is the deny
   honoured in a subagent session?
4. Does a PreToolUse hook with matcher `mcp__<server>__.*` run before and independently of an allow
   rule, and does `onFailure: block` stop an MCP call when the hook exits non-zero?
5. Does the hook input for an MCP call carry the tool name and arguments, and does it carry the
   subagent name inside a subagent (C-05)?
6. Do the `tools` and `mcpServers` frontmatter fields of an agent definition limit the tools the
   subagent can call, or only list them, when the session allow entries differ?
7. Is `CLAUDE_PROJECT_DIR` set for the command of a `.mcp.json` server, and what working directory
   does that command get?
8. When the server's command exits at startup (the launcher's refusal), what does the session
   show, and does anything retry?
9. Is a project `.mcp.json` server pre-approved by a user-scope setting, and is that visible to a
   worker started with `--strict-mcp-config`?

### Still not verified (live check not run)

- Everything under "Not verified (LIVE, L2–L4)" above.
- That the 39 names are the live local deny list (the checker prints a count only).
- The dependencies at the locked versions, and a running server's advertised tool list.
- python-dotenv's search path in the locked version, and what the server writes into its working directory.
- All harness behaviour in the question list, and `enableAllProjectMcpServers` in this checkout.
