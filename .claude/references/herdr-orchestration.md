# Herdr Coordination Reference — CoreOS Platform Lab

Read the relevant section when preparing a packet, selecting a procedure or
recovering a mission. The [rule](../rules/herdr-orchestration.md) owns the project
contract; the installed Herdr skill and CLI help own operating syntax. These
examples do not authorize a mission, a topology change, publication or lab access.

## Authority and reading order

1. Establish the active request, lead, allowed actions and any existing approval.
2. Read applicable repository instructions and the [architecture](../../docs/architecture.md).
3. Check the [decision log](../../docs/.prepare/decision-log.md), relevant
   [open questions](../../docs/.prepare/open-questions.md) and assigned sections of
   the [implementation plan](../../docs/.prepare/implementation-plan.md).
4. Add task-specific security/test rules and the accepted inputs. Do not require
   every worker to repeat the whole repository survey or preparation workflow.

| Work | Authority and boundary |
|---|---|
| Preparation or policy work | Explicit assigned paths; no implied platform implementation or lab access. Existing document owners remain authoritative. |
| GitHub planning/publication | [Steward](../agents/github-steward.md) and [bootstrap mission](../../.agents/plans/github-bootstrap-mission.md), with their stage and publication gate. A planning assignment is not permission to publish. |
| Platform/lab work | Implementation gate plus the actual task's permitted operations. Proxmox audit access does not authorize VM creation. |
| Review | Technical findings and evidence checks; no implied fix, owner approval, merge or release. |

Preserve decided D-09/D-10/D-13 and D-46. Read proposal status rather than treating
all preparation material as approved. The historical four-session manifest is
evidence of a specific authorized preparation topology, including its concurrent
prime work; adaptive concurrency does not override it or restart it.

## Parallel implementation

The owner's requested layout groups the same role in one tab with a pane per
worker. For example, an `implementation` tab can contain `impl-host`,
`impl-firewall` and `impl-services` in separate panes. If several reviewers are
needed, they share a `review` tab. These are illustrative names, not fixed IDs or
a requirement to start those workers. Create only role tabs needed by the mission.

Reuse a suitable mission-owned tab, or create one within the authorized mission;
capture its returned tab/root-pane IDs and split further panes in that tab.
Preserve each packet's cwd and the user's focus; choose a readable split layout.
This standing topology preference authorizes role grouping without repeated
confirmation, but does not itself authorize a mission, a new workspace, unrelated
pane moves or extra workers outside the budget. Preserve an existing explicit
mission layout, including historical D-10, unless the owner directs its change.
Tab grouping is visual organization, not file, process or lab isolation.

Within an authorized mission, prefer multiple workers whenever there are useful
independent packages. Worker count follows the ready work, the owner's budget,
tool/host capacity and review capacity; two or three bounded workers are a
starting point when enough independent work exists, not a mandatory minimum or a
fixed maximum. Do not ask for another approval merely to dispatch an
additional worker already covered by that mission. Topology, external actions and
lab access still follow their existing boundaries.

| Ready work | Useful split | Dependency to preserve |
|---|---|---|
| Host and firewall configuration after the spike | One worker owns Butane/host units; another owns firewall files. | Agree unit names and startup ordering first; one owner integrates shared files. |
| Service configuration and acceptance scripts | A service worker owns configuration; a test worker implements scripts against agreed endpoints and source roles. | Script creation is not a lab pass; run against the integrated deployment later. |
| Several independent service configuration files | Give separate files to multiple implementation workers, with review scheduled as outputs arrive. | One designated writer owns shared `compose.yaml` and integrates accepted fragments. |
| Lab operator running a reserved verification window | Other workers prepare independent changes or documentation locally. | Do not deploy those changes or modify captured evidence during the run. |

Reassess after each accepted output or resolved blocker. Dispatch ready packages
before waiting on others; reuse a finished worker for the next suitable package.
The orchestrator coordinates and integrates rather than absorbing all substantive
implementation. A small correction may remain with the lead. Record a short
reason when serial execution is preferable; never manufacture independent tasks
by ignoring their shared inputs, resource effects or acceptance dependencies.

## Packet and report

Supply the following in a private English terminal prompt, omitting irrelevant
fields. Actual cwd and runtime targets belong in private packets; public records
use relative paths and sanitized logical identifiers.

```text
Task: <unique ID and bounded outcome>
Report to: <current orchestrator identity>
Mode and authority: <preparation / GitHub / platform-lab; existing approval>
Model and effort: <as the rule's "Models and effort" sets for this role; the invocation used>
Working directory: <exact private cwd>
Baseline: <commit plus local inputs OR revisions and non-secret input snapshot>
Plan: <assigned D-step/section, issue if one exists, affected AC IDs>
Read: <applicable rules and exact source sections>
Procedure: <source file; native alias or explicit file-read mode; named bindings>
Dependencies: <accepted result/version or agreed interface>
Write ownership: <exact paths; integration owner; Git actor if authorized>
Runtime ownership: <target/resource; permitted operations; verification window>
Exclusions and recovery: <forbidden actions; recovery for disruptive work>
Acceptance: <observable result and relevant checks>
Checkpoint: <when to report progress, failure or a dependency change>
Return a terminal report for this task and baseline.
```

```text
Task / worker / cwd / baseline:
Model and effort actually used:
Status: DONE or BLOCKED
Result: exact files/diff/artifact; commit only if authorized and one exists
Procedure used and deviations:
Checks: command, PASS / FAIL / NOT RUN / PARTIAL / NOT APPLICABLE, actual evidence
Lab run if applicable: date/run ID, VM build, configuration/component versions,
  source role, preconditions, actual result and final resource state
Unverified claims, limitations and blockers:
Processes/resources still active and their owner:
Recommended next action:
```

The lead records `accepted` only after reviewing the result. Keep this record in
an existing session/work artifact, with dependencies and ownership. Do not create
one public issue per internal assignment or repurpose the historical preparation
manifest as a live scheduler. Preserve issue/branch/PR conventions for deliverables.

Before a first commit, record document revisions plus an allowlisted non-secret
input inventory and exact snapshots or checksums where useful. Recheck inputs
before acceptance: revision labels alone are mutable. Do not hash or collect
secret-bearing directories. After commits exist, record the SHA and relevant
uncommitted inputs. Untracked files still require direct review.

## Resource ownership

| Resource | Coordination rule | Handoff/recovery check |
|---|---|---|
| Shared checkout | One writer per path, one Git index/branch actor. Shared Compose/Butane/Caddy files need an explicit owner. | Compare assigned and unexpected changes; no branch switch beneath workers. |
| Proxmox provisioning / VM lifecycle | One authorized operator per affected target; no competing create, reboot, rebuild or destroy action. | Verify actual VM state before retry; preserve unrelated VMs and storage. |
| Docker daemon, firewall, Compose stack | Serialize deploy, firewall load and daemon restart. A separate checkout does not isolate them. | Establish installed configuration and service state; record recovery outcome. |
| Acceptance window | Reserve a stable configuration and coordinate allowed/forbidden source roles. Disruption tests are exclusive. | A concurrent change invalidates affected observations; rerun those checks. |
| Persistent DB, uploads, CA, queue, backups | Never disposable fixtures; only named, authorized operations. | Preserve recoverable state; do not replay mail or restore commands blindly. |
| Checkmk and SMTP test resources | Identify check/mailbox/message ownership; do not overlap service-stop tests with unrelated acceptance. | Confirm restored monitoring state and disposition of test messages. |
| Isolated local checks | Distinct temporary directories, project/container names and ports where needed. | Confirm no shared daemon/global rule or volume defeats claimed isolation. |

Ownership is a coordination record, not a technical lock or security boundary.
Free it only after the old writer/command is known to have stopped and the result
is preserved. Keep ownership reserved across a timeout or lost connection.

Illustrative scheduling: an authorized platform writer and a security reviewer
can work on disjoint files. Deployment starts after their accepted interface is
integrated. Then one lab operator runs checks against a fixed revision while the
reviewer examines captured evidence. The steward can prepare public descriptions
independently, but publishes only within its authorization and serializes shared
Git operations. Do not claim full AC-07 from the D4 stub or a failed service.

## Repository command routing

Static inspection: 2026-11-16. These are candidate procedures, not a mandatory
pipeline or proof of native alias availability. Paths below are relative to
`.claude/commands/`. Read each selected procedure and bind its scope first.

| Task | Procedure | Required adaptation |
|---|---|---|
| Understand assigned area | [core_piv_loop/prime.md](../commands/core_piv_loop/prime.md) | Handle absent HEAD and application files; include relevant untracked files. Do not install `tree` just for this template. |
| Implement authorized work | [core_piv_loop/execute.md](../commands/core_piv_loop/execute.md) | Bind specific plan sections and files; reading D0–D11 does not authorize executing them all. Use infrastructure checks, not invented type gates. `/commit` is not permission or proof of an available command. |
| Review a diff/PR | [do/review.md](../commands/do/review.md) | Include untracked inputs where relevant; use actual static/AC requirements. Its `Approved` heading is technical review only. No automatic posting. |
| Review with a durable artifact | [validation/code-review.md](../commands/validation/code-review.md) | Authorize its exact output path; adapt generic paths and tests. A read-only review cannot silently run disruptive lab checks. |
| Record execution | [validation/execution-report.md](../commands/validation/execution-report.md) | Only if a durable report is requested. Replace generic unit/type rows with applicable static, lab and evidence results; explicitly mark unrun checks. |
| Plan unresolved work | [core_piv_loop/plan-feature.md](../commands/core_piv_loop/plan-feature.md) | Do not replan approved work, introduce an 80% coverage gate or follow its subagent advice beyond the mission budget. |

Before native invocation, verify the alias resolves to that exact source in the
worker client, including dynamic shell snippets. Otherwise use explicit file-read
mode with named bindings; do not assume argument numbering, `$ARGUMENTS`, shell
injection or aliases transfer between clients.

Known local route problems at inspection:

- `end-to-end-feature.md` refers to missing `core_commands/*` procedures.
- `do/implementation.md` depends on a repository `github-pm` skill that is absent
  and requests issue closure after local work. Use the steward's closure rules.
- `validation/code-review-fix.md` refers to missing `commands/validate.md`.
- PRP creators reference absent `PRPs/templates/prp_base.md` and some request
  extra subagents. Neither dependency authorizes creating a new framework.

Report the broken route; select a bounded procedure or keep only that route
blocked. Toolkit repair is a separate scope. The static gates in
[test-requirements.md](../rules/test-requirements.md) are the intended checks;
confirm the files/tools exist before invoking them. Do not create missing
platform files merely to make an orchestration check pass.

## Observation and recovery

Use the installed skill for commands; these are decisions, not a script.

| Observation | Next action |
|---|---|
| Submission acknowledged, no work observed | Inspect identity, state and output before resubmitting; start remains unconfirmed. |
| Settled state or completion notification | Match report task ID and baseline; it may describe an earlier turn. |
| Unexpected idle/unknown/blocked | Read output; use `agent explain` only if supported. An unfamiliar approval UI can be missed by detection. Do not answer it without consent. |
| Output wait matches immediately | Check a unique task/run marker and actual command result; old screen text can match. |
| Timeout or connection lost | Inspect artifacts, running commands and target state; do not assume failure meant no side effect. |
| Writer unreachable | Keep its file/lab ownership reserved until stopped; continue independent work. |
| Incomplete report | Try the skill's larger/history read; if unavailable, ask for a sanitized temporary Markdown report and read it on the same machine. |
| Baseline/configuration changed | Identify affected results, notify dependents and revalidate those results. |
| Restored screen/conversation | Rediscover identity/cwd/jobs and inspect lab state; replay is historical output, not resumed execution. |
| Cleanup requested | Separate pane closure, checkout removal and service/data cleanup; preserve results and act only on owned authorized resources. |

On supporting servers, `completion_seq` and `state_change_seq` help distinguish
fresh transitions. They may be absent on older servers and do not identify the
accepted task. Do not build a hard dependency on them or update Herdr to get them.
Use finite waits; interleave meaningful user updates and independent work.
An idle coding agent may have background jobs, so inspect reported resources too.

For remote work, keep the same explicit machine/session context throughout.
Machine-profile discovery is not a pane inventory. A UI machine switch does not
retarget the calling shell; neither an unavailable remote nor version mismatch
authorizes local fallback, profile edits, server installation or restart.

## Verification scenarios

Review these cases when changing the rule. They are policy checks, not lab passes.

1. A closed implementation gate permits assigned document work but no lab probe.
2. Two workers request `compose.yaml`: only the named writer receives ownership.
3. No HEAD exists: onboarding reviews untracked inputs without creating a commit.
4. A restart overlaps AC-07: defer one run; do not combine unstable observations.
5. A previous `DONE` appears: require the new task's report before acceptance.
6. A prompt times out: inspect before retry; preserve old writer ownership.
7. A template requests commit/issue closure: the packet and steward bounds win.
8. A restored pane shows a pass: require the matching recorded run and target state.
9. A report is clipped: recover it without publishing private terminal history.
10. Required Herdr capability is unavailable: report it and continue independent
    work without switching orchestration tools or changing the installation.
11. The model the rule selects for a role is unavailable in the installed client:
    report it and continue independent work; no other model is substituted
    without an explained proposal to the owner.
12. A fix lands after a review: the changed and affected portions are rechecked;
    the whole review is not restarted without cause, and no further complete
    review layer is added merely for consolidation.

A live smoke test, if separately authorized, can use one read-only worker task,
report collection and acceptance. It needs no GitHub writes or lab contact.

## Sources and limits

Reviewed on 2026-11-16 using three research/review subagents. The source rule was
adapted from another repository; this version binds only CoreOS Platform Lab
documents. Adaptive worker scheduling, lab reservations and acceptance records are
project policy, not Herdr guarantees. No Herdr process was controlled for this
documentation change, and no native alias, client/server pair or lab run was
validated. Recheck live capabilities when a real mission begins. The model and
effort defaults of the rule's "Models and effort" section are the owner's policy
of 2026-11-16; whether the installed client offers a named model or effort is
checked from its help when a session is started.

Primary references, accessed through the [official documentation index](https://herdr.dev/tui/docs/):

| Source | What it supports |
|---|---|
| [Agent skill](https://herdr.dev/tui/docs/agent-skill/) | Operating skill versus human guide, environment boundary and release-matched skill. |
| [Agent automation](https://herdr.dev/tui/docs/agent-automation/) | Agent/pane/layout separation, returned identities and report-history recovery. |
| [CLI reference](https://herdr.dev/tui/docs/cli-reference/) | Prompt/wait semantics, version-dependent counters, output matching and cleanup operations. |
| [Agents](https://herdr.dev/tui/docs/agents/) | Detection limitations, ambiguous idle/blocked states and background jobs. |
| [Integrations](https://herdr.dev/tui/docs/integrations/) | Resume identity and lifecycle reporting differ by integration; do not assume hooks guarantee status. |
| [Session state](https://herdr.dev/tui/docs/session-state/) | Detach, restart, screen replay and native conversation restore preserve different things. |
| [Connecting machines](https://herdr.dev/tui/docs/connecting-machines/) | Independent remote servers and explicit remote targeting. |

The requested [Deep Dive](https://acchapm1.github.io/tutorials/Herdr/herdr-deep-dive)
and [Beginner Guide](https://acchapm1.github.io/tutorials/Herdr/herdr-beginner-guide)
are secondary learning resources. Their useful themes are bounded specialist
work, deliberate layouts, isolated files and preserving work across detach.
Do not carry over their list-position targeting, unverified `agent status`/wait
syntax, raw prefix-key orchestration or general claims about hook-based status.
Both include broad socket-removal troubleshooting: it is not acceptable recovery
for this mission. Prefer installed skill/help and the official references above.
Tutorial setup, global tuning, raw socket automation and experimental handoff do
not become authorized just because orchestration is requested.
