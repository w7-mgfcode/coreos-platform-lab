# lab-agent/proposed: candidates for owner-controlled files

These are **proposals, not installed**. The gate compiles the candidate hook and the unit tests run it
(as a subprocess, with synthetic input and a temporary state directory), but nothing installs or
registers it: no settings file in this repository points at it and no session loads it. They are
tracked and tested, and registered nowhere. They are **not a safeguard of a clone**: a clone has no
guard hook until the owner installs one. The active guard hook and the active agent definition
(`.claude/hooks/pve-guard.py`, `.claude/agents/pve-lab.md`) are local, git-ignored files kept
outside the repository on the owner's workstation, unchanged by these candidates. (The tooling was
excluded from the initial publication, D-49, and is included by the owner's decision D-57; the
inclusion registers nothing and authorizes no contact with the lab.)

| File | Isolated copy of | What it adds |
|---|---|---|
| `hooks/pve-guard.py` | `.claude/hooks/pve-guard.py` | G-1 (internal errors and malformed events exit 2), G-2 (absolute-path and quoted forms of the owner-only names and of ssh, scp, sftp, ssh-add) and S-1g (inside `pve-lab` only `ssh [-T] pve-snip WORD...`), plus the further forms listed below |
| `agents/pve-lab.md` | `.claude/agents/pve-lab.md` | The source-address instruction of the L2 runbook, and the rule to write the words after the alias literally |

The two candidate files cite the design plan by a path under `.agents/plans/`. That plan is not
published, and the citations cannot be reworded, because the published patches must reproduce the
candidates byte for byte. Read these citations as historical background: the candidates do not
need the plan or that path to be tested. (The owner procedure in `../docs/l2-runbook.md` does
name one prerequisite that only the unpublished plan specifies, and says so.)

Both are tested where they are, offline, with synthetic input
(`lab-agent/tests/test_l1b_guard_candidate.py`). The shared hook tests run against the candidate
always; where a working copy also has the active hook (`HookTests` in
`lab-agent/tests/test_hook_and_repo.py`), they run against that file too. A clone has no active
hook, so there the candidate is the only one tested.

## What the guard is, and is not

**It is not a security boundary.** It matches command text. The boundaries are Proxmox RBAC
(routine token), the host's `from=` restriction and forced command on the snippet key, and the
root key never being usable inside an agent session. The guard prevents mistakes and writes an
audit line. A determined or merely creative command can get past a text match.

What the candidate denies that the active hook does not (all observed, offline, with synthetic
input): the names of the owner-only launcher and of the root key through quoting, a
backslash, `$'...'`, `${IFS}`, an empty `${name}`, a brace list or a glob with at least five
literal characters; the key's path variable; ssh, scp, sftp and ssh-add after `/`, a quote, `=`,
`{`, inside `bash -c`, a here-string and any wrapper; inside `pve-lab` any ssh option (also
without a space or after the alias), any word the shell expands before ssh sees it, the other
connection tools (`ssh-keygen`, `rsync`, `nc`, `/dev/tcp` and the like), `eval` and decoders
piped to a shell; and, everywhere, any event the hook cannot read (exit 2): invalid UTF-8, input over
4 MiB, a wrong field type (an explicit null counts as a wrong type), a decision it cannot deliver.
A command with a brace list that expands beyond 1024 words (or a word over 8 KiB that holds one) is
denied as too complex to inspect, never inspected in part. A redirect target after `ssh pve-snip`
may name a variable but not a command or process substitution.

**Not catchable by a text match** (the candidate passes these, and the tests record that):

- a name built by a command substitution, `printf`, or by joining variables (`x=host; y=-run`);
- a glob with fewer than five literal characters (`*root`, `*-run`);
- a payload decoded or assembled at run time, a script written first and run later, a program
  that opens a connection by another name, a language runtime (`python3 -c ...`) that does it;
- the module path `python3 -m lab_agent.hostrun`: it does not name the launcher. Its own refusals
  (no terminal, a Claude parent process) are the control, not the guard;
- any tool the hook is not registered for (the matcher decides), and any harness behaviour
  (`agent_type` reaching the hook inside `pve-lab`, `onFailure`) that is not verified here.

## Known false positives (costs of the candidate)

Each one below was **observed** on the candidate with synthetic input, together with a control that
passes. Every one **fails closed**: the call is denied (or, for the last two, blocked by exit
status 2), never passed. The call is not run; the user or agent rewrites it as shown.
**This list may not be exhaustive.** A text match that is strict enough to catch the forms above
will refuse some harmless commands that nobody thought of; the independent review found two of the
entries below after the first draft of this list, and says that no absence of false positives is
established.

| Where | What is denied or blocked | Why | What to do instead |
|---|---|---|---|
| Inside `pve-lab` | A here-document, even a quoted one (`cat <<'EOF' > n.txt`), whose text contains `ssh other id` or similar | The guard reads text and cannot tell data from a command; any `ssh`, `scp` or `sftp` word outside `ssh [-T] pve-snip WORD...` is denied, wherever it stands | Write the file with the Write tool instead of a here-document, or leave the words `ssh`, `scp` and `sftp` out of the text (observed: the same heredoc without them passes) |
| Inside `pve-lab` | `ssh pve-snip put demo < 'draft(1).ign'`: a redirect target with literal parentheses in a quoted file name | A redirect target may name a variable but may contain no `(`, `)` or backtick, because the guard cannot tell a literal `(` in a quoted name from a command or process substitution | Use a file name without parentheses: copy it first (`cp 'draft(1).ign' draft1.ign`, observed to pass), then `ssh pve-snip put demo < draft1.ign` (observed to pass). A quoted name without parentheses (`'draft 1.ign'`) passes |
| Inside `pve-lab` | Any word `ssh`, `scp` or `sftp` outside the allowed form (for example `ls ssh`); a `$`, glob or brace in a word after the alias other than a redirect target | An expansion can produce an option, and the guard does not evaluate the shell | Write the words after `pve-snip` literally, as the agent file says |
| Main session | A compact JSON heredoc with eleven two-field objects on one line (`[{"a":1,"b":2},{...},...]`) | After quoting is undone, each `{a:1,b:2}` is a comma brace group; eleven sequential groups would expand to 2048 words, over the limit of 1024, and a command that is too large to inspect completely is denied rather than inspected in part | Write the file with the Write tool; or put one object per line, or put a space after each comma (both observed to pass); ten two-field objects on one line pass |
| Main session | `mkdir -p {a,b}{a,b}...` with eleven brace groups in one word | Same limit: 2^11 = 2048 words | Split the command: two words (`{a,b}` x 5 then x 6) or two `mkdir` commands (both observed to pass); ten groups in one word pass |
| Main session | A single word over 8 KiB that holds a comma brace group (for example a large one-line JSON object passed as one quoted argument) | A word that long is not expanded; because part of it cannot be inspected, the guard denies it | Put the data in a file with the Write tool and pass the file name; the same shape under 8 KiB passes, and a one-line object with 70 fields passes |
| Any session | A valid event larger than 4 MiB (for example a command with a multi-megabyte inline payload): blocked, exit status 2 | The hook reads at most 4 MiB so that it cannot be made to read without bound; above that it does not inspect | Do not put the payload in the command; write it to a file with the Write tool. A 3 MiB command passes |
| Any session | An event in which an optional field (`tool_input`, `agent_type`, `permission_mode`) is present with an explicit `null`: blocked, exit status 2 | A present key of the wrong type is not an absence. A harness check observed that the main session sends these keys absent, not null (one client version); a different client version that sends null would have every call blocked | Nothing to do in a command. If it happens, the candidate must not be installed or must be changed: report it, do not work around it (this is the one entry that depends on the harness version, and it is NEEDS-LIVE) |
| Everywhere | A command that names the owner-only launcher or the key's path variable, even to read about it | By design | Use the Read and Grep tools, as the guard's message says |

## How the owner would install each one

Nothing here is done for the owner. These are the steps, each from the repository root, in the
owner's own terminal.

1. **Check that the active files are the ones the patches were written against.** The sha256 of
   each target is in the patch header (`lab-agent/docs/proposed-patches/`). If a target moved,
   the patch must be reconciled again first.
2. **Hook.** `.claude/hooks/` is on the stop-and-ask list. Apply the three patches in this
   order, checking each first: `pve-guard-fail-closed.patch`, `pve-guard-absolute-path-ssh.patch`,
   `pve-guard-ssh-alias-form.patch` (`git apply --check`, then `git apply`). The result is
   `hooks/pve-guard.py` of this directory, byte for byte; compare with `cmp`. Alternatively copy
   that file over the active one. Whether an already running session reloads the file, and
   when, is **not verified**: after changing it, check it with a fresh session and
   `python3 lab-agent/tests/check_local_settings.py`.
3. **Agent.** Apply `l2-source-address-pve-lab-agent.patch` the same way, or copy `agents/pve-lab.md`.
4. **Tests after installing.** The unit tests need none of the local-only files. They test this
   directory's candidates always, rebuild the baseline by applying the patches backwards to the
   candidates, and compare with the active files only where this checkout has them
   (`tests/test_hook_and_repo.py`: `CandidateHookTests` always, `HookTests` when the active hook
   exists). Installing a candidate leaves them passing. They fail on purpose if an active file is
   neither the baseline nor the candidate, because then the patches must be reconciled again.
5. **Registration is separate.** Neither candidate changes the registration in the local settings.
   `python3 lab-agent/tests/check_local_settings.py` checks it by hand (names, counts and booleans
   only).

Independence: the first two hook patches each apply to the active file alone; the third needs the
second. Applying all three in the order above is the only combination that produces the candidate.
