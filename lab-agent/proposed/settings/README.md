# Proposed settings for SET-1 (proposal, not installed)

Everything in this directory is a **proposal for the owner**, not installed. It is tracked and
tested, and registered nowhere: nothing here is read by Claude Code, nothing was copied into
`.claude/`, and no active setting was changed. Applying it is the owner's decision (SET-1,
still open; options and consequences in
[`../../docs/mcp-server-review.md`](../../docs/mcp-server-review.md), "SET-1 and B-S1"). The
settings it would change are the owner's untracked local settings, kept outside the repository:
a clone has none of those entries, so the fragment is not a safeguard of a clone either.

## Files

| File | What it is |
|---|---|
| `set1-option-c.fragment.json` | The recommended option (C), as keys to **merge** into the owner's local settings file. |

## What option C would change

Merge the fragment into the untracked local settings of this checkout (the file that holds the
`mcp__pve__*` entries today), and make two removals by hand, because a JSON merge cannot
delete:

1. Remove the `"mcp__pve__*"` entry from `permissions.allow`. The fragment lists, in its place,
   69 tools of the pinned server by exact name (no wildcard): those that its own
   classification marks read-only and that are not on the deny list. The other 33 non-denied
   tools are not listed.
2. Remove `enableAllProjectMcpServers`. The fragment adds `enabledMcpjsonServers: ["pve"]`.

Keep the 39 deny entries, the guard hook registration and the two `Read(~/…)` deny entries
exactly as they are.

## What it is meant to achieve, and on what condition

These are intentions. None is established behaviour of Claude Code in this checkout: each depends
on a check in the review document ("Questions for the harness test"), which has not been run.

- The 33 unlisted tools would prompt, in every session, **if** a call that no `allow` entry
  covers prompts (question 2) and **if** the exact-name list is honoured the way the tool name
  rule is documented (question 2, 3).
- Only `pve` would be pre-approved **if** `enabledMcpjsonServers` approves exactly the listed
  servers and a second server still asks (question 1).
- The guard hook would still inspect every call **if** a PreToolUse hook runs for a call an
  `allow` entry already approves (question 4).
- Removing the wildcard changes nothing for the deny entries **if** a deny entry beats an allow
  entry (question 3).

Until those checks are run, treat the fragment as a draft.

## How it was checked, and what was not

- **Observed, offline:** the fragment is valid JSON; every name is a tool the pinned server
  defines, in the snapshot of its source at commit `69686b06347c89d85c3725cf4a730c979b0148b7`;
  none is on the deny list; every name is read-only by the server's own classification. The
  tests compare the snapshot's commit with the launcher's pin, so moving the pin fails them until
  the snapshot is re-read. See `PinReviewFixtureTests` and `SetOneFragmentTests` in
  `tests/test_l1b_mcp.py`. The snapshot is a recorded copy: the tests prove consistency with the
  pin, not where the copy came from.
- **Not verified:** everything in the list above, and the precedence and merge rules of the
  settings files.
- **Not run:** anything against a live Claude Code session or the lab.

Nothing here names a real host, address, token or home path.
