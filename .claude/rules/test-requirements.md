# Test Requirements

> Vision principle: **"Meet the brief, prove it with evidence."** Every change has valid evidence for the applicable gates, using new runs or explicitly retained results under the change-based validation rule below. Every requirement is closed by an acceptance check that ran on the lab, and every block is shown by a negative test.

## What "tests" mean here

| Layer | Where | What it asserts |
|-------|-------|-----------------|
| **Static** | the whole tree | Configuration parses and is internally valid without a VM: Butane, Compose, Caddyfile, shell scripts. Runs in seconds, locally and in CI. |
| **Acceptance** | `tests/` scripts, run against the lab VM | A requirement works end to end: HTTPS, mail, log search, monitoring, restart, rebuild. |
| **Negative** | `tests/` scripts, run from outside the VM and from an unauthorised container | A connection that must be blocked is refused. |
| **Evidence** | `docs/evidence/` | The captured output, screenshot or log excerpt of an acceptance or negative run, with the date and the versions in use. |

## Gates

Run, in order (fast → slow):

```bash
butane --strict butane/app-01.bu > /dev/null     # Butane parses with no warnings
docker compose -f compose.yaml config --quiet    # Compose file resolves
caddy validate --config Caddyfile --adapter caddyfile
shellcheck scripts/*.sh tests/*.sh
# only with access to the lab VM:
tests/run-acceptance.sh
```

A tool that is not installed locally may run from its official container image, pinned to a version. The scaffold change fixes the exact invocations (for example in one `scripts/validate.sh`); once it exists, that script is the gate and this block is updated to match it.

**Do not commit on red.** The acceptance layer needs the lab and never runs in CI.

## Change-based validation and reuse

Choose checks by affected behavior and inputs, not by the fact that a file or a
whole-tree snapshot hash changed. This section governs rerun selection; it does
not waive a required check, an owner gate, or the evidence rules below.

Before a costly run, record in the existing task record: the changed inputs,
affected checks, reusable results and the concrete reason for any full rerun.
A short entry is enough; do not create another approval process or reporting layer.

| Change | Required validation | Results that may be retained |
|---|---|---|
| Prose, diagrams, review/status records | Relevant links, anchors, tables, revisions, publication hygiene and claim accuracy | Code and runtime tests whose inputs are unchanged |
| Policy, permissions instructions or operational runbook | Targeted consistency and authority review; inspect commands against current code | Unaffected runtime results; this review grants no live execution authority |
| Comments or formatting in code/configuration | Inspect the actual delta. Configuration still passes the static gates ("What doesn't need tests"); run the affected tests as well if directives, generation or behavior could change | Unaffected tests after confirming the delta is non-executable |
| Localized executable change or bug fix | Regression test, affected unit/integration tests and relevant static checks | Checks outside the demonstrated impact boundary |
| Fixture, path, file mode, symlink, package or dependency change | Tests consuming those inputs and affected clean-export/import/entry-point checks | Unaffected checks; a path move is not automatically documentation-only |
| Shared transport, authorization, isolation, runner or cross-component behavior | All affected boundary and negative tests; full relevant suite when impact spans the suite or cannot be bounded | Only evidence with an established unaffected scope |

Classify by how content is used, not by extension: Markdown examples, comments,
fixtures and documentation may be parsed or executed. If the impact is unclear,
inspect the relevant consumers first. If it remains unclear, broaden the checks
and state why. Never shrink a test to create an unaffected scope.

A result is reusable only when it passed and its relevant source, tests, fixtures,
configuration, dependencies, invocation and execution environment remain
applicable. Compare actual content and relevant modes/symlinks; include needed
untracked inputs. A change to the input inventory or to a test's file-discovery
scope may invalidate it. A shared live target can change without a Git diff:
reuse of offline results does not establish current lab state.

The final record distinguishes:
- RUN: check, tested snapshot/inputs, environment, exit status and result;
- RETAINED: earlier passing result and the inspected final delta explaining why
  the check is unaffected;
- NOT RUN, FAILED or INVALIDATED: stated explicitly; never presented as PASS.

The final publication snapshot need not equal an earlier test snapshot byte for
byte. It needs complete coverage: retained results for unchanged inputs plus
appropriate checks/review of every later delta. Do not claim that a full suite
ran on the final tree when its result was retained from an earlier one.

Run full suites for a concrete integration, packaging, environment or coverage
reason, not merely to refresh a timestamp or whole-tree hash. A clean export is
required when validating that a publication does not depend on local-only files;
repeating it after prose-only edits requires an identified affected check.
Where supporting tooling has both an offline gate and a network-less suite, the
two provide distinct evidence even when they run the same unit tests. Assess reuse for each separately; neither substitutes for the other's
unique checks.

Before a release, rerun acceptance checks invalidated by relevant changes, as
required below. Preserve AC-05/AC-07 sources and positive controls. A required
check that is blocked by missing authorization stays blocked, not waived.

## Required coverage — the acceptance checks

The acceptance table in `docs/architecture.md` § 10 is the specification. The IDs below are assigned in that table's order; if the table changes, update the IDs here in the same change.

| Check | Acceptance condition | Proof |
|-------|----------------------|-------|
| AC-01 Rebuild | The environment can be created on a new VM from the documented sources | Run log of a fresh build |
| AC-02 HTTPS | Correct name and trusted chain, with no `-k` and no browser exception | `curl` with the lab root CA, certificate details |
| AC-03 Certificate lifecycle | A controlled lab trial shows automatic renewal | Caddy log and the new certificate's validity dates |
| AC-04 Mail | A mail sent from WordPress arrives and can be traced by queue ID | Postfix log line and the received message |
| AC-05 Relay protection | A relay attempt from an unauthorised client is refused | SMTP transcript with the rejection |
| AC-06 Log search | An HTTP error and an SMTP event are found in Grafana | Query and result screenshot |
| AC-07 Firewall | Forbidden connections fail from outside and from an unauthorised container | Negative test output per blocked path |
| AC-08 Monitoring | Stopping a service raises an alert; restoring it clears the alert | Checkmk state before and after |
| AC-09 Restart | After a VM and a Docker restart, services and protection rules work | Re-run of AC-02 and AC-07 after each restart |
| AC-10 Restore | Test data is restored and CA trust is kept; time and data loss are recorded | Restore log with measured times |

AC-01 … AC-09 gate the first release. AC-10 belongs to the OPTIONAL backup tier and is required only when that tier is delivered.

### Load-bearing tests

AC-05 and AC-07 are the spec for the security boundary. Never weaken them, narrow their source addresses, or remove a blocked path from them to make a change pass.

A negative test must fail for the right reason: the service is running and reachable from an allowed source, and the same request from the forbidden source is refused or times out. A test that "passes" because the service is down proves nothing.

## Evidence rules

- An acceptance check is marked passed only with its evidence file committed and linked from the issue.
- Evidence records the date, the VM build, and the versions of FCOS, Docker CE, Compose and the images involved.
- Evidence never contains secrets, tokens or third-party personal data. Redact before committing.
- A check that was not run is recorded as not run. Plans and expected results are not evidence.
- When a relevant change lands after a check passed, the check is re-run before a release.

## When new tests are required

- **New service or published port** → one positive check, plus a negative check for every path that must stay closed
- **New firewall rule** → a negative test from the source it blocks, and a re-run of AC-09
- **Bug fix** → a check that would have caught the bug
- **New first-boot or systemd unit** → a check that it ran once and that a reboot leaves the host in the expected state
- **Change to a pinned version** → re-run the acceptance checks that touch that component

## Conventions

- Files: `tests/<area>-<what>.sh`, executable, `set -euo pipefail`, exit non-zero on failure
- Each script prints what it checks, the command it ran and a final PASS or FAIL line
- Targets (VM address, hostnames, CA path) come from variables with documented defaults, never hardcoded secrets
- Tests are read-only against the lab unless their name says otherwise (`restore`, `restart`)

## What doesn't need tests

- Documentation and diagrams
- `.claude/` policy files (the rule IS the test; `audit-rules-drift` catches drift)
- Comment-only or formatting-only changes to configuration that still pass the static gates
