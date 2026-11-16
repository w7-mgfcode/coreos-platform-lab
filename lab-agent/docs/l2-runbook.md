# lab-agent L2 runbook (owner)

> **This runbook authorizes nothing.** L2 (access to the Proxmox host) waits for the owner's
> recorded decision and a dated approval line in `docs/.prepare/decision-log.md` § 5 that covers
> L2. Including the tooling in the repository (decision D-57) is not that approval. Until the
> approval exists, the implementation gate (D-09) holds and nothing here is run. Every step is
> **owner-only**, in the owner's own terminal: not an agent session, not a `!` command, not an
> agent-controlled pane. Values are the setting names of [`../env.example`](../env.example); real
> values live only in the owner's private files, never in this repository.

Written 2026-11-16, offline. **No step of this runbook has been run against a host.** The only
live result for this tooling is the single read-only API check recorded in the README
([state 3](../README.md#status)): TLS verification against the owner's CA file, token
authentication and five `GET` reads, under two narrow owner approvals that are used up. It
exercised none of the steps below. "Offline pre-check" means a check that opens no connection to
`${PVE_HOST}`. "Live acceptance" means a check that can only pass in L2 itself; every live
statement here is **NEEDS-LIVE**.

## Why the source address needs its own step

The workstation may have more than one network interface, and the address the kernel picks
towards `${PVE_HOST}` need not be the intended fixed address. `PVE_WORKSTATION_ADDR` names the
intended one. The setting alone binds nothing: what binds is the code below, and the route is
a separate matter. The table describes the code as it is in this version.

| Path | What decides the source address now | Where `PVE_WORKSTATION_ADDR` is used | From the wrong address |
|---|---|---|---|
| Owner path: `host-run` → `ssh root@${PVE_HOST}` (`lab_agent/hostrun.py`, `ssh_command`) | `-o BindAddress=<validated PVE_WORKSTATION_ADDR>` with `-F none`, so no inherited `Host *` entry (`BindInterface`, `ProxyJump`, `ProxyCommand`, another `BindAddress`) can change it | the bind, and the root key's `from=`, which the owner types by hand in the GUI shell | the bind fails loudly (`Cannot assign requested address`) if the address is not on this machine; a wrong source with a correct `from=` is refused (`Permission denied (publickey)`) |
| Snippet path: `ssh pve-snip …` (the `pve-lab` agent, `demo/render.sh`, the README) | the `Host pve-snip` stanza in the owner's own `~/.ssh/config` (step 7). **No alias is defined anywhere in the repository**: without one, `pve-snip` is looked up as a host name and the default keys, agent and `known_hosts` apply | the stanza's `BindAddress`, and `prepare` writes it into `restrict,from="…",command=…` for the `corelab-snip` key (`host/actions/prepare.sh`) | refused by `from=`, loudly. The user exists only after `prepare` (L4) |
| API: `lab-agent` (`lab_agent/pveapi.py`, urllib) | `PVE_WORKSTATION_ADDR` is **required**: `Client.from_config` binds the connection to it, uses no proxy, never follows a redirect, and refuses if an environment HTTPS proxy would carry the connection (`PVE_HOST` not in `no_proxy`). Without the setting it refuses to connect (an unbound form exists only for a caller that passes `allow_unbound=True` in code; no command-line option sets it) | the bind | the tooling sets no source restriction on the API itself (token plus TLS with the pinned CA). A host firewall or a `pveproxy` allow-list would refuse or time out |
| API: the pinned MCP server (httpx) | the kernel's route lookup. `mcp.server_env` passes no proxy variables (only `PATH`, `HOME`, `LANG`, `TMPDIR` and the server's own settings) | not used | as above. The server documents no source-address setting (not checked in its source), so it can be bound only by the route |

Silent cases to avoid: a pattern or list in `from=` (a subnet, `*`, two addresses) accepts both
addresses. So does a `from=` set to the address that happens to work. A jump host or proxy changes
the address the host sees. NAT between workstation and host does the same. Each `from=` must be
exactly `${PVE_WORKSTATION_ADDR}`, one literal address.

## Address, interface and route

- **`BindAddress`** makes ssh `bind()` its socket to that local address before `connect()`.
  The host then sees that source address, unless NAT or a proxy sits in between. If the address
  is not configured on this machine, the bind fails (`Cannot assign requested address`) and the
  connection fails loudly.
- **What `BindAddress` does not do:** choose the outgoing interface or route. Linux picks the
  route by destination (and by source only where policy-routing rules exist). A packet with
  source `${PVE_WORKSTATION_ADDR}` can leave through a different interface. Replies may then be
  dropped by reverse-path filtering, a stateful firewall or asymmetric routing. The symptom is a
  timeout, not a refusal.
- **`BindInterface`** (the OpenSSH release that introduced it was not verified offline) uses the address of the named interface as the source
  address. Like `BindAddress`, it does not force the route. It also names an interface, which
  belongs only in the owner's private configuration. `BindAddress` is preferred.
- **Pinning the interface or route** needs a host route or policy rule with a source (for
  example a route to `${PVE_HOST}` with `src ${PVE_WORKSTATION_ADDR}`). That is **workstation
  networking: the owner's decision, outside this tooling and outside this runbook.** It is also
  the only way to make the MCP server, a browser on the GUI, `ssh-keyscan` or any other unbound
  client use the fixed address.

## What the code does about it

| Path | Behaviour | Kind | Notes |
|---|---|---|---|
| Owner path | `ssh_command` adds `-F none` and `-o BindAddress=<validated address>`. `config.workstation_addr()` accepts exactly one IP address, of the same family as an IP-literal `PVE_HOST`, and refuses a wildcard, loopback, link-local, multicast, IPv4-mapped or reserved address. `run()` checks before the confirmation prompt that the address is assigned locally (a `bind()` without `connect()`; no packet is sent) and that `PVE_KNOWN_HOSTS` exists. Host-key pinning (`StrictHostKeyChecking=yes`, `UserKnownHostsFile=${PVE_KNOWN_HOSTS}`, `GlobalKnownHostsFile=/dev/null`, `UpdateHostKeys=no`, `VerifyHostKeyDNS=no`), public-key-only authentication (keyboard-interactive, password, host-based and GSSAPI off), the passphrase-protected key, `IdentitiesOnly`/`IdentityAgent=none`, no multiplexing, no forwarding, and port 22 only (there is no ssh port setting; a `PVE_HOST` that carries a port and a `PVE_SSH_PORT` line are refused) | code (`lab_agent/hostrun.py`, `lab_agent/config.py`; tests in `tests/test_closeout_source_addr.py`) | offline only. An address that validates but is not this machine's is caught by the bind check, not by validation |
| Snippet path | A `Host pve-snip` stanza in the owner's own `~/.ssh/config` (step 7). It has to be in the default configuration because the agent calls the plain alias. **The older active guard does not hold the agent to the plain form**: it takes the first word that does not start with `-` as the destination, so an option written without a space (`-oBindAddress=…`, `-F/path`, `-b…`, `-J…`) passes, and so does any option placed after the alias (`ssh pve-snip -o … list`). What fixes the source address of this path is the host side: `from="${PVE_WORKSTATION_ADDR}"` on the `corelab-snip` key refuses any other source or a jump host, and the forced command limits what the key can do. The candidate guard in [`../proposed/hooks/pve-guard.py`](../proposed/hooks/pve-guard.py) denies every option inside `pve-lab`; installing it is the owner's decision ([`../proposed/README.md`](../proposed/README.md)) | configuration (owner, by hand) | not done |
| API, `lab-agent` | `Client.from_config` binds, uses no proxy and refuses an environment proxy, as in the table above | code (`lab_agent/pveapi.py`) | offline tests against fixtures. The README's state-3 check is the one live use of this client; it is not a test of the source-address binding |
| API, MCP server | None in configuration. Only a route (owner networking), or no source restriction on the API | none | owner decision |

`prepare` keeps writing `from="${PVE_WORKSTATION_ADDR}"` for the snippet key. With the validation
in `config.py`, a value that is not exactly one IP address (a pattern, a list, a quote) is refused
before anything is rendered.

## Actions this runbook does not cover (disabled or blocked)

- `host-run run apply-manifest` is **disabled in code** and always refuses. It needs
  `--manifest FILE --sha256 HASH --inventory INV --overrides OV`, validates them, prints the
  dry-run plan and then refuses with exit 2 before anything is rendered for approval or sent. No
  setting or argument changes this. `host-run show apply-manifest` prints a preview only.
- `host-run run sentinel` is **blocked** by an open review finding and is refused (exit 2) after
  the terminal checks. `host-run show sentinel` still prints the script.
- The disablement is not containment against code injected into the shell; the other recorded
  limitations are listed in the README.

Neither action is a step below. L3 and L4 (guest lifecycle, cleanup, sentinel) are not authorized
and depend on re-enabling or unblocking code that needs its own review and an owner decision.

## Steps

| # | Step (owner-only) | Offline pre-check (no connection to the host) | Live acceptance (L2), NEEDS-LIVE |
|---|---|---|---|
| 0 | Confirm the authorization (the owner's decision recorded, a § 5 line covering L2) and that every item in "Remaining prerequisites" below is met or explicitly accepted by the owner | Read the decision log. Run `lab-agent/tests/run.sh` and expect `RESULT: PASS (all 7 checks ran)`, exit 0. In the owner's working copy also run `python3 lab-agent/tests/check_local_settings.py` (see the note below the table) | — |
| 1 | Settings: `install -d -m 700 ~/.config/corelab-lab-agent`, copy `env.example` to `env` there, fill it in, `chmod 600` | `stat -c %a` gives 700 on the directory and 600 on `env` | — |
| 2 | **Source address.** Set `PVE_WORKSTATION_ADDR` to the one intended address. Decide whether the route towards `${PVE_HOST}` must change (owner networking; out of scope) | `ip -br addr` lists the address on this machine. `ip route get ${PVE_HOST}` shows the kernel's default `src` and `dev`. `ip route get ${PVE_HOST} from ${PVE_WORKSTATION_ADDR}` shows the route a bound socket uses. Look for a jump host, proxy or NAT on the path | Steps 6, 9 and 11 |
| 3 | Keys: `ssh-keygen -t ed25519 -f ~/.ssh/corelab-pve-root` (passphrase required), and `ssh-keygen -t ed25519 -N '' -f ~/.ssh/corelab-pve-snip`. Never `ssh-add` the root key | `ssh-keygen -y -P '' -f ~/.ssh/corelab-pve-root` must **fail** (encrypted). `ssh-add -l` lists neither key | The key audit of step 8 |
| 4 | GUI node shell (`root@pam`): add the root public key to `/root/.ssh/authorized_keys` with `from="${PVE_WORKSTATION_ADDR}"`, the literal address, one only | Proof-read the line: no pattern, no list, the same value as in `env` | Step 6 |
| 5 | Pin the host key: compare `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` (GUI shell) with `ssh-keyscan -t ed25519 ${PVE_HOST}`, then save the line to `PVE_KNOWN_HOSTS`. Get `/etc/pve/pve-root-ca.pem` into `PVE_CA_FILE` through the GUI and compare its fingerprint | Fingerprints match the GUI. `ssh-keyscan` authenticates nothing and its source address does not matter | — |
| 6 | `lab-agent/bin/host-run run preflight` | The owner-path tests pass (`tests/test_closeout_source_addr.py`: `-F none` and `BindAddress` in the argument list; its `ssh -G` resolution shows `bindaddress ${PVE_WORKSTATION_ADDR}` and no `proxyjump`/`proxycommand`/`bindinterface`). `host-run` checks the root key (a private file, passphrase-protected) after you type the hash and before anything is sent; a missing or unencrypted key is refused. `lab-agent/bin/host-run show preflight` prints the script and makes no connection | Preflight succeeds. The host's sshd log shows `Accepted publickey for root from ${PVE_WORKSTATION_ADDR}`. Negative: the same key from the other local address is refused (`Permission denied (publickey)`) |
| 7 | Add the `pve-snip` stanza below to the **top** of `~/.ssh/config` (first match wins), with real values, and exclude the alias from every other `Host` or `Match` block (`Host * !pve-snip`) | `ssh -G pve-snip` (no connection) shows exactly the checklist under the stanza. The owner runs this one deliberately without `-F`, so that it resolves the same user and system configuration as the agent's real call. Also check that the key file it names exists: `ls -l ${PVE_SNIP_KEY}` (ssh passes over a missing identity file with only a warning and offers other keys; `ssh -G` does not check the file) | Step 11 |
| 8 | Workstation key audit (a design intention recorded outside the repository: no unencrypted key on the workstation may be accepted for root on the host) | `ssh-add -l`; fingerprints of the unencrypted keys on disk | No match in the host's root `authorized_keys` except the encrypted root key and the offline recovery key (preflight prints the fingerprints) |
| 9 | `lab-agent/bin/host-run run bootstrap` | The parent directory of `PVE_TOKEN_FILE` is mode 700 and the token file does not exist (`host-run` refuses an existing token file and a parent that is not private). Keep `PVE_TOKEN_EXPIRE_DAYS` at 365 or less: `host-run` accepts up to 3650, but the host script refuses a value above 365 (exit 3) | Token file mode 600, secret never printed. `curl --cacert ${PVE_CA_FILE} --interface ${PVE_WORKSTATION_ADDR} https://${PVE_HOST}:${PVE_PORT}/api2/json/version` gives 401 without the token, and with the token header read from the file it gives 200. A different CA file fails TLS |
| 10 | `lab-agent/bin/lab-agent mcp-install`, then start Claude Code and approve the `pve` server (a download from the pinned repository) | The pin in `lab_agent/mcp.py` is a full commit, and the pin review is done as far as it goes (prerequisite 9 below) | The server lists nodes with the Auditor token. Its source is the kernel's choice (see the path table) |
| 11 | After `prepare` in **L4** (not L2): `ssh pve-snip list` | The stanza check of step 7 | The writer lists the `corelab-*.ign` files and exits 0. Negative: `ssh -o BindAddress=<the other local address> pve-snip list`, run by the owner, is refused by `from=`. The agent is instructed never to add an option, but the older active guard does not stop every form; the host's `from=` does |

*Note on step 0.* The guard registration and the lab permission entries are not in the tracked
settings; they live in each checkout's untracked local settings file. `check_local_settings.py`
reports, by names, counts and booleans only, whether the checkout it lives in has exactly one
guard registration with the intended form. In the owner's working copy it was observed on
2026-11-16 to print `RESULT: PASS` with `deny entries starting mcp__pve__: 39` and
`deny entries starting Read(~/: 2`; compare the two deny counts yourself, because the script
passes even if they differ. In a clone, or any session without that file, it prints
`RESULT: FAIL` with zero guard registrations: that is the expected, honest answer, and no
lab-related work belongs there. At step 10 the `pve` server's tool names are to be checked
against the deny list in the same local file.

### The `pve-snip` stanza (step 7)

The owner writes real values for the `${…}` names by hand, in their own `~/.ssh/config` only. Put
the stanza **first** in the file. ssh takes the first value it finds, so a block above the stanza
overrides it: placed below a `Host *` block, the stanza loses its host-key and multiplexing
settings. Then **exclude the alias from every other block** that could match it. Write
`Host * !pve-snip` instead of `Host *`, and add `!pve-snip` to any wide pattern or `Match` block.
This is needed because some settings accumulate, or are not set by the stanza, and a later block
still adds them: a second `IdentityFile`, a `CertificateFile`, a `BindInterface`, a `LocalCommand`.
Set `AddressFamily` to `inet` for an IPv4 `${PVE_HOST}` and `inet6` for an IPv6 one.

```
Host pve-snip
    HostName ${PVE_HOST}
    Port 22
    User corelab-snip
    AddressFamily inet
    BindAddress ${PVE_WORKSTATION_ADDR}
    IdentityFile ${PVE_SNIP_KEY}
    IdentitiesOnly yes
    IdentityAgent none
    UserKnownHostsFile ${PVE_KNOWN_HOSTS}
    GlobalKnownHostsFile /dev/null
    KnownHostsCommand none
    HostKeyAlias ${PVE_HOST}
    StrictHostKeyChecking yes
    VerifyHostKeyDNS no
    UpdateHostKeys no
    PubkeyAuthentication yes
    HostbasedAuthentication no
    GSSAPIAuthentication no
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    PermitLocalCommand no
    ProxyJump none
    ProxyCommand none
    ControlMaster no
    ControlPath none
    ForwardAgent no
    ForwardX11 no
    ClearAllForwardings yes
    RequestTTY no
    BatchMode yes
```

`HostKeyAlias ${PVE_HOST}` makes the host-key lookup use the same name as the pinned line in
`${PVE_KNOWN_HOSTS}` (step 5), so an inherited alias cannot redirect the lookup.

`ssh -G pve-snip` must show:

- the destination: `hostname ${PVE_HOST}`, `port 22`, `user corelab-snip`, `addressfamily inet`
  (or `inet6`), `bindaddress ${PVE_WORKSTATION_ADDR}`;
- the key: **exactly one** `identityfile` line, naming `${PVE_SNIP_KEY}`, a file that exists (check
  it separately with `ls -l`); `identitiesonly yes`, `identityagent none`;
- host-key pinning: `userknownhostsfile ${PVE_KNOWN_HOSTS}`, `globalknownhostsfile /dev/null`,
  `hostkeyalias ${PVE_HOST}`, `stricthostkeychecking true`, `verifyhostkeydns false`,
  `updatehostkeys false`;
- authentication: `pubkeyauthentication true`, `hostbasedauthentication no`,
  `gssapiauthentication no`, `passwordauthentication no`, `kbdinteractiveauthentication no`;
- no other connection behaviour: `permitlocalcommand no`, `controlmaster false`,
  `forwardagent no`, `batchmode yes`;
- **no** `certificatefile`, `knownhostscommand`, `localcommand`, `proxyjump`, `proxycommand` or
  `bindinterface` line at all.

The forced command and `restrict` on the host side are unchanged. The stanza only decides where the
connection goes from and which key and host key it uses.

## What was shown offline (2026-11-16, throwaway configuration, RFC 5737 placeholders)

These used `ssh -G` with an explicit `-F <scratch file>` every time. `ssh -G` resolves options and
opens no connection (OpenSSH 10.2). Without `-F`, ssh would read the account's real configuration:
it takes the path from the account's home directory, not from `HOME`.

- The hardened stanza above, under a hostile `Host *` block, resolves to the checklist except for
  four lines the hostile block still adds: a second `identityfile`, a `certificatefile`, a
  `localcommand` and a `bindinterface`. The hostile block set port, address family, global
  known-hosts file, known-hosts command, host-key alias, DNS host-key verification, host-based
  and GSSAPI authentication, local command, bind interface, bind address, jump host, a known-hosts
  file and multiplexing. With the same block written as `Host * !pve-snip`, nothing is added.

- A `Host pve-snip` stanza with `BindAddress` wins over a later `Host *` `BindAddress`. Without
  `ProxyJump none`, it still inherits a `Host *` `ProxyJump`: the host would see the jump host's
  address.
- An `ssh` argument list without `-F none` inherits `BindAddress` and `ProxyJump` from a `Host *`
  entry. Adding `-o BindAddress=… -o ProxyJump=none` still inherits a `ProxyCommand` and a
  `BindInterface` from the configuration. With `-F none -o BindAddress=…`, the resolution shows
  only `bindaddress` and no proxy or interface settings. That is why `ssh_command` uses `-F none`.

## Portability: what another workstation needs

Written 2026-11-16 by reading the code and by running the offline tests on a scratch copy of the
tooling. Third-party components, licences and pins are in
[`dependencies-and-attribution.md`](dependencies-and-attribution.md). Nothing here was tried on a
second machine: **observed** below means observed on the development machine, and a second
machine is a live check not run.

| Need | What the code asks for | State |
|---|---|---|
| Operating system | Linux. `hostrun.process_ancestors` reads `/proc/<pid>/stat`; on a system without `/proc` the list of ancestors is empty and only the `CLAUDECODE` environment check still refuses an agent session. The code also uses `os.getuid`, `O_NOFOLLOW` and directory file descriptors | read from the code; not tried elsewhere |
| Python | the standard library only, no third-party module. Annotations such as `str \| None` sit behind `from __future__ import annotations`; a parenthesised `with (…)` appears in `pveapi.py`. 3.14.4 was the only version run, and no minimum was established | observed on 3.14.4 only |
| Perl | the snippet writer needs `Cwd`, `Digest::SHA`, `Fcntl`, `IO::Handle` and `JSON::PP` (all core). It runs on the Proxmox host; the tests also run it locally | observed on perl 5.40.1 |
| OpenSSH client | `-F none`, `BindAddress`, `IdentityAgent=none`, `IdentitiesOnly`, `ControlPath=none`, `StrictHostKeyChecking=yes`, and `ssh -G` in the tests. The release that introduced each option was not checked | observed on OpenSSH 10.2 only |
| Shell and coreutils | `bash` (the gate and the host actions use `[[ … ]]` and `10#` arithmetic), `mktemp`, `install`, `sha256sum`, `tar`, `xz`, `curl`, `awk`, `timeout`, `stat -c`. The development machine's `sort` is the uutils implementation | observed; GNU coreutils not tried |
| Docker | only for gate checks 4 and 5, `tests/run-netless.sh` and `demo/render.sh`. The images are named by tag, `docker.io/koalaman/shellcheck:v0.10.0` and `quay.io/coreos/butane:v0.23.0` (gate), and a local `python:3.12.14-slim` image (network-less run); the gate runs them with `--network none` and never pulls: without the image the check is `SKIP` and the result is `INCOMPLETE`, exit 2, not a pass | tag pins; the digests observed locally are in the attribution document |
| `uv` and `git` | for `lab-agent mcp-install` (clone at the pinned commit, `uv sync --frozen --no-dev`) **and** for every launch: `bin/mcp-launch` checks that `HEAD` equals the pin through `git` and starts the server with `uv run`. Removing either after installation breaks the launch. Not run | not run |
| Filesystem | `tests/stubs/` holds six symbolic links to `pvestub.py`, and the stubs, `bin/*`, `demo/render.sh`, `tests/run.sh` and the snippet writer need the executable bit. A checkout without symlink support, or a mount that drops file modes, breaks the stub tests | observed on this machine; no other filesystem tried |

What is tied to this machine, observed by a pattern search of the published tooling on 2026-11-16
(by pattern only; the owner's private values are unknown to the search, so a by-value
comparison was not possible): no absolute home path, user name or host name is written in any
file under `lab-agent/`. The only `/home/` text is the pattern in a test that forbids it. Default
locations are `~/.config/corelab-lab-agent/` for settings, the token, the CA copy and the pinned
host key, `~/.ssh/corelab-pve-root` and `~/.ssh/corelab-pve-snip` for the keys, and a state
directory under `~/.local/state/` (the `env.example` values; `PVE_AGENT_ENV` overrides the
settings path). A project `.mcp.json` finds the launcher through `$CLAUDE_PROJECT_DIR`.
`.mcp.json` is ignored by git, so a clone has none: `lab-agent/mcp.example.json` is the same
entry kept inside `lab-agent/` (the gate validates it), and the owner copies it to the
repository root. The three values the owner must fill in for their own lab (`PVE_HOST`,
`PVE_NODE`, `PVE_WORKSTATION_ADDR`) are RFC 5737 placeholders in `env.example`. The placeholder
node name `pve1` is a generic Proxmox default, not a lab value.

What a fresh clone lacks, by design:

- **The working copy's local files.** `.mcp.json`, the active guard hook and the active `pve-lab`
  agent definition are not in a clone. Tracked, tested candidates for the last two are in
  [`../proposed/`](../proposed/README.md) and are registered nowhere.
- **The guard registration and the lab permission entries.** They live in the untracked local
  settings file, not in the tracked settings. **This repository supplies none of them** in a
  worktree, a second clone or a session started without that file. Whether such a session has a
  guard hook, `mcp__pve__*` deny rules or `Read(~/…)` deny entries then depends on its other
  settings layers (user, managed or another project file), which were not examined. Check the
  target session's effective settings before any lab-related work; do not assume either way. On a
  scratch copy with only the tracked settings, observed 2026-11-16:
  `python3 lab-agent/tests/check_local_settings.py` printed `RESULT: FAIL` with
  `guard registrations, total: 0` and exit 1. Do not do lab-related work from such a copy.
- **The owner's private files.** The settings file with the real values, the keys, the token,
  the CA copy, the pinned host key, the `pve-snip` stanza in the SSH configuration, and the state
  directory (inventories, run logs, approvals, host backups, the MCP clone). The runbook steps
  above create them on the owner's machine.

## Remaining prerequisites before owner-authorized SSH/API setup

1. The owner's recorded decision for L2 and a dated § 5 approval line that covers it. The
   implementation gate (D-09) stays closed until then. The tooling's own proposed decisions are
   recorded nowhere: they live in the design plan, which is kept outside the repository, and have
   no decision IDs.
2. Re-run `lab-agent/tests/run.sh` if anything in `lab-agent/` has changed since the last
   recorded pass (README, state 2). A pass is offline only.
3. The guard and the alias form: the older active guard does not restrict the alias to its plain
   form. This runbook states it and relies on the host's `from=` and forced command for that
   path. Installing the candidate guard is the owner's decision. The stanza hardening of step 7
   is the owner's, applied by hand.
4. Before **L3 or L4** (not needed for L2): no agent-side sentinel protection when
   `PVE_SENTINEL_VMID` is missing or `0`; the volume-usage check has no positive control and
   misses some kinds of reference (`cicustom` volumes, a snapshot's vmstate volume); a few
   malformed inputs still end in a traceback instead of exit 2 (all fail closed). Cleanup
   execution stays disabled and the `sentinel` action stays blocked until the owner decides
   otherwise.
5. The owner's decision on routing: whether the kernel's default source towards `${PVE_HOST}`
   must become `${PVE_WORKSTATION_ADDR}` (needed for the MCP server, the GUI and any unbound
   client, or if replies return the wrong way). This is workstation networking, the owner's own.
6. Confirmation that no NAT, proxy or jump host sits between the workstation and the host, or the
   `from=` values are wrong.
7. The `pve-snip` stanza in the owner's SSH configuration, with the alias excluded from every other
   block, checked with `ssh -G` against the full checklist (step 7).
8. The design plan makes L1's acceptance "every offline acceptance check passes" (a design
   intention recorded outside the repository). Two of them are not closed: the snippet writer
   check under a real sshd is partial (the offline tests and a throwaway-container harness exist;
   the real `corelab-snip` identity, the root-owned directory and the forced command have not been
   exercised), and the operation-to-privilege matrix is incomplete (the generator ran on a
   synthetic fixture only). The owner either accepts that explicitly or has them closed.
9. The MCP server pin review, before step 10 downloads it. Done at source level on 2026-11-16: the
   licence at the pinned commit and the tool names, read from the public upstream repository
   ([`mcp-server-review.md`](mcp-server-review.md)). Still open: the server's locked dependencies,
   whether a **running** server advertises the names in the owner's deny list, and its maintenance
   over time. The licences are listed in [`dependencies-and-attribution.md`](dependencies-and-attribution.md) § 2.
10. The harness behaviour the guard relies on, verified before the `pve-lab` agent is used:
    - whether `"onFailure": "block"` is honoured;
    - whether the subagent name reaches the hook inside `pve-lab`;
    - whether the agent definition's frontmatter fields behave as intended.

    All are unverified. An isolated local check on synthetic hooks, outside `pve-lab`, reported
    that `onFailure: "block"` blocked a hook that exited 1; it does not settle the other two and
    is not an L2 check.
11. The owner's decisions on the proposed changes:
    - the guard-hook patches (`pve-guard-fail-closed.patch`, `pve-guard-absolute-path-ssh.patch`
      and `pve-guard-ssh-alias-form.patch`) and the source-address patch for the `pve-lab` agent
      (`l2-source-address-pve-lab-agent.patch`), all in `lab-agent/docs/proposed-patches/` and
      none applied;
    - SET-1 (`mcp__pve__*` allowed for every session), see [`mcp-server-review.md`](mcp-server-review.md);
    - proposed changes to the design plan and to the project's decision records are kept
      outside the repository with the plan; none is applied.
12. A recovery path and a list of manual host steps that the design plan requires. The plan is
    not published, so **this prerequisite cannot be completed from the repository alone, and the
    procedure after it is not executable as published** until the owner supplies and accepts that
    list. What the published documents themselves ask the owner to do on the host by hand is the
    GUI node-shell work of steps 4 and 5 (add the root public key with `from=`, compare the host
    key fingerprint and the CA fingerprint), each never run. The plan also names a GUI
    `root@pam` recovery login with its password stored off the workstation; the repository
    states no procedure for it. Whether the host actions need any further manual preparation is
    not established here: their header comments describe what each script checks and creates
    itself, but this runbook does not claim that nothing else is needed.
