# Implementation Plan — CoreOS Platform Lab

| Field | Value |
|---|---|
| Document ID | PREP-07 |
| Title | Implementation Plan (conditional) |
| Revision | r3 |
| Status | ready-for-human-review |
| Owner | Orchestrator session (integrator); drafts by platform-writer (S1) and security-writer (S2); reviewed by plan-critic (S3); approver: repository owner |
| Last updated | 2026-11-16 |
| Core-context revision used | r2 (`docs-baseline-r2`) |
| Dependencies | [plan-review.md](plan-review.md) r2, [delegation/s1-platform-delivery.md](delegation/s1-platform-delivery.md) r1, [delegation/s2-security-verification.md](delegation/s2-security-verification.md) r1, [delegation/s3-critic-review.md](delegation/s3-critic-review.md) r1, [decision-log.md](decision-log.md) r2, [open-questions.md](open-questions.md) r2; for rule 5 of § 3, added in r2: [decision-log.md](decision-log.md) r6 (D-48); for the dated note added in r3: [source-register.md](source-register.md) r4 (SR-28, SR-29) |
| Change summary | r1: integration of the two drafts after the critic's review. r2 (2026-11-16): rule 5 added under the table of § 3 for the owner's scheduling decision D-48. The table, the exits, the "May claim" column and every other section are unchanged. r3 (2026-11-16, documentation closeout DOC-1): one dated note under the table of § 3 on the root `CLAUDE.md` of step D2. The table, its exits and every rule are unchanged. r3, extended on 2026-11-16 after an independent review (DOC-1b): the note assigns R-21's measure to the pair of briefs, and the Dependencies field names the source-register revision of the note |

## 1. What kind of plan this is

**A conditional plan, not a build order to start on.** The requirements and the acceptance conditions are stable: they are fixed by the reviewer's answers and the two tables of the architecture. What is not stable is how several of them will be met on this lab, because that depends on answers only the owner has and on facts only a first VM can show.

So the plan fixes what can be fixed now — the order of work, the exit of each step, how each acceptance check is run and what evidence it leaves — and marks every part that waits on a blocker. **Nothing in it is built or tested.** It is a proposal until the owner approves it (D-09).

The plan summarises and reconciles. The detail stays in the two drafts and is linked, not repeated:

- host, Docker CE, services, boot order, delivery steps: [S1](delegation/s1-platform-delivery.md)
- exposure matrix, firewall, networks, TLS, secrets, relay protection, test design: [S2](delegation/s2-security-verification.md)

## 2. Blockers

Nothing below can be worked around by an agent. The step column says where work stops without the answer.

| Blocker | What is needed | Who | Stops |
|---|---|---|---|
| The implementation gate | a dated approval line in [decision-log.md](decision-log.md) § 5 | owner | every step from D1 |
| OQ-07 | yes, no or change on the proposals in decision-log § 3 | owner | approval |
| OQ-02 | host capacity and version; VM size; room for a second VM | owner (auditor token, then a read-only query) | D1, D3, D9 |
| OQ-05 | who creates the VM and with which privileges | owner | D1, D3 |
| OQ-06 | addressing plan: VM address, a source for each test role (client, admin, Checkmk, **a forbidden source that can reach the VM**), the machine the client-role tests run from, name resolution | owner | D1 (the spike VM needs an address), D4, AC-02, AC-07 |
| OQ-04 | an authenticated relay on TCP 587 and a test mailbox | owner | D6, AC-04 |
| OQ-03 | a Checkmk instance whose checks and trust store the owner controls | owner | D8, AC-08 |
| The spike | the answers in § 4 | first lab session after the gate | D3 onward in detail |

Not blockers, but needed on the way: OQ-12 (update window, at D3), OQ-11 (Postfix image, at D6), OQ-20 (log retention, at D7), OQ-19 (OPTIONAL tier, at D11).

## 3. Execution order

The order refines the five steps of [architecture § 10](../architecture.md#10-megvalósítás-és-átvételi-ellenőrzés) without changing them (D-33, proposed). No durations are given: no time budget exists (OQ-01).

"Exit" is what must be observed and recorded before the next step starts. "May claim" lists the acceptance checks a step is allowed to mark as passed; everything else it produces is a partial result and is recorded as partial.

| Step | Architecture step | Work | Exit | May claim |
|---|---|---|---|---|
| D0 Owner inputs | 1 | The owner answers the blockers of § 2. No lab contact | each blocker answered or explicitly deferred with its consequence | — |
| D1 Spike | 2 | First the one part of the scaffold the spike needs: a pinned Butane invocation, because the workstation has none. Then a throwaway VM built by the provisioning procedure with a minimal Butane file; the questions of § 4 are answered; the VM is destroyed. The provisioning trial and the spike are one event | every spike question has a recorded answer | nothing. Spike notes are working notes, not evidence |
| D2 Platform scaffold | 2 | The file layout (D-05), `scripts/validate.sh` running each static gate from a pinned container, the example variables file, the evidence index, a root `CLAUDE.md` (R-21) | the script passes on the scaffold and fails on a deliberately broken copy of each input | — |
| D3 Host | 2 | Decided first, from the spike: the log driver and any SELinux daemon setting, because Ignition writes the daemon configuration once. Then Butane, the provisioning script, the Docker CE first-boot unit, the host-rule stage of the firewall (so SSH is limited from the first boot), the version list, the install documentation | the owner builds the VM from the repository; the Docker CE proof is captured; a second reboot leaves the install unit skipped and Docker running | — (the Docker CE proof is reused in AC-01) |
| D4 Host firewall | 2 | The firewall unit and rules; Caddy alone as the stub service on TCP 443 | from the client role 443 answers, from the forbidden role it does not, and both hold after a Docker restart and a reboot | **AC-07 in part only**, recorded as partial |
| D5 Web | 3 | The secrets channel and file-based secrets (OQ-26); MariaDB, WordPress, the proxy route, scripted initialisation | login, a post and an upload over verified HTTPS; the upload survives a stop and start of the stack | EV-WEB; EV-SEC; AC-02 **for the application name only**, recorded as partial |
| D6 Mail | 3 | Postfix, the WordPress mail hand-over, fixed addressing on the mail network | a message from WordPress is queued, traced by its queue ID, and arrives; a relay attempt from the probe on the mail network is refused at SMTP level | AC-04, AC-05 |
| D7 Logs | 4 | Alloy, Loki, Grafana, the logs name on the proxy — the last change to the proxy configuration | one HTTP error and one SMTP event found by a query, Grafana behind its own login | AC-06; AC-02 in full (both names); the AC-03 trial starts here |
| D8 Monitoring | 4 | The active HTTPS check; the agent route and local checks if the spike allows | stopping a service changes the check state; restoring it clears it | AC-08 |
| D9 Restart, rebuild, release gate | — | In this order: AC-07 in full; then the restart checks; then a fresh VM built from the repository. Which VM carries the release evidence is OQ-29; recommended: the final run happens on the rebuilt VM | AC-07 passes in full; AC-02 and AC-07 pass again after a Docker restart and after a reboot; the fresh build passes | AC-07, AC-09, AC-01; then the gate: AC-01 … AC-09 |
| D10 EXTRA layers | 2 | Proxmox firewall; the isolation claims for the Docker networks | each layer's own negative tests, attributed to that layer | additions to AC-07 |
| D11 OPTIONAL tier | 5 | Backup, restore, update procedure | a restore trial with measured times; an update trial | AC-10; EV-UPD |

*Note of 2026-11-16 (DOC-1).* Step D2 lists "a root `CLAUDE.md` (R-21)" as something the scaffold creates. A root `CLAUDE.md` and a root `AGENTS.md` already exist; they were added on 2026-11-16 outside this package ([source-register.md](source-register.md) SR-28, SR-29). The row is kept as written. At D2 the work on these files is to bring them up to date with what the scaffold fixes: `AGENTS.md` says its "Build & Test Commands" section is updated in the same change in which `scripts/validate.sh` lands. R-21's measure (it exists, is about a page, lists the gate commands) then applies to the pair: `AGENTS.md` carries the gate commands, and `CLAUDE.md`, which imports it, stays within its stated limit of 150 lines. Nothing here changes the exit of D2.

Rules that hold across the table:

1. **MUST HAVE before EXTRA before OPTIONAL** (SR-03). D10 and D11 start only when D9's gate has passed, or when the owner explicitly decides otherwise.
2. **No check is passed against nothing.** AC-07 is claimed only at D9, with all seven services running (F-13). The run at D4 is recorded as partial.
3. **A change after a pass means a re-run** (SR-08). Every step that touches a component names the checks to repeat.
4. **Each step is one or more sub-issues, each one branch and one PR.** The mapping to issues is in [github-project-plan.md](github-project-plan.md).
5. **One exception to the exit rule, decided by the owner (D-48, 2026-11-16).** The logs sub-issue of D7 (S3.1) may be integrated and accepted once the first half of D6 is done (S2.2: Postfix for the single client and the refusal, AC-05), provided its own prerequisites and acceptance conditions are met. It does not wait for the second half of D6 (S2.3: the relay hand-over and the WordPress mail path, AC-04). Nothing else in the table changes: D6's exit and what D6 and D7 may claim are as written, AC-04 is still required for the gate at D9, and no other step starts before the exit of the one before it. The order of work as a whole (D-33) is still a proposal. Four conditions go with the exception:
   - Shared files have one designated writer at a time; rebasing a branch does not replace that.
   - The only way described so far to apply a change on the running VM restarts every service, Caddy included ([S1 § 2.3](delegation/s1-platform-delivery.md)). While that holds, S2.3 is deployed outside the observation window of the AC-03 trial.
   - A check that a later change actually affects is re-run (rule 3). If AC-06 passed before S2.3 lands and S2.3 changes Postfix's image, log output or the log route, AC-06 is re-run.
   - The release evidence for the log search also shows the search for a Postfix queue ID, which the requirements table names for the searchable-logs row ([architecture § 2](../architecture.md#2-követelmények-és-döntések)). An AC-06 pass taken earlier from the refusal event does not replace it.

The files each step creates and their commit scopes are listed in [S1 § 7.3](delegation/s1-platform-delivery.md#73-steps).

## 4. The spike

One throwaway VM, after the implementation gate. It turns the assumptions A-02 … A-04 and several open questions into facts. Each question has exactly one command set and one decision that depends on it; the commands are in the drafts.

The two drafts numbered their questions separately. The merged list below is the one to use; the last column points to the command.

| ID | Question | Decision that depends on it | Closes | Command in |
|---|---|---|---|---|
| SP-01 | Are the four base packages of the upstream procedure present on this FCOS release? | the package list of the install transaction | A-03 | S1 SQ-01 |
| SP-02 | Does the override leave the host on Docker CE after the reboot? | D-24 adopted as written or amended | D-02 feasibility | S1 SQ-02 |
| SP-03 | Does `docker-ce` alone bring in the Compose and buildx plugins? Needs its own install variant that names only `docker-ce` | explicit plugin install needed, or kept as a guard | OQ-13 | S1 SQ-03 |
| SP-04 | Is a version-qualified package request accepted? | pinned engine version, or record-only with a stated limit | OQ-14 | S1 SQ-04 |
| SP-05 | Does the install succeed with the repository file and key shipped by Butane? | ship the key, or reference Docker's key location and record it | D-24 | S1 SQ-05 |
| SP-06 | Which firewall backend does Docker use, and does `DOCKER-USER` exist? | the host firewall design as written, or an owner decision | A-02 | S2 SQ-1; S1 SQ-06 |
| SP-07 | Does Docker keep a pre-created, populated `DOCKER-USER` chain? | two-stage firewall unit, or the restart-policy fallback (§ 7, row 2) | — | S2 SQ-2 |
| SP-08 | Do containers start before a unit ordered after Docker, and after an unclean reboot? | whether a boot window exists; the restart policy | F-03 | S2 SQ-3; S1 SQ-10 |
| SP-09 | External interface name | the interface variable of the rules | — | S2 SQ-4 |
| SP-10 | Is IPv6 active on the VM and in Docker? | "not in use, enforced", or rule parity | OQ-15 | S2 SQ-5; S1 SQ-07 |
| SP-11 | Are containers SELinux-confined under Docker CE without a daemon setting? Runs before SP-14 and SP-15: an enforcing host does not show that containers are confined | a daemon setting in Butane | A-09, F-24 | S2 SQ-6 |
| SP-12 | Can a container on internal networks only publish a port? | whether the extra `edge` network is needed | — | S2 SQ-7 |
| SP-13 | Does external name resolution work from internal and non-internal networks? | the Postfix egress rule and resolver | — | S2 SQ-8 |
| SP-14 | Can a non-root, confined container read a file-backed Compose secret? | ownership, mode and label of the secrets directory | OQ-16 | S2 SQ-9 |
| SP-15 | What can a confined log collector **read** (not merely list) under enforcing SELinux: a shared volume; the journal directories and machine identifier, with and without a log-reader type? | the log route (§ 7, row 1) | OQ-09 | S2 SQ-10 (S1 SQ-09 lists one directory only and can pass falsely) |
| SP-16 | Can a probe container join a Compose network at a chosen address? | the probe method of AC-05 and AC-07 | — | S2 SQ-11 |
| SP-17 | Where is the root certificate in Caddy's data, and what are the lifetimes in practice? | the export step; the bound of the AC-03 trial | — | S2 SQ-12 |
| SP-18 | Is Python present on the host? | Docker plugin possible, or local checks only | A-04, OQ-08 | S1 SQ-08 |
| SP-19 | Did Ignition arrive through the cloud-init vendor snippet? | the provisioning procedure as designed, or another delivery path | F-02 | S1 SQ-11 |
| SP-20 | Where does a held or failed host update show? (OPTIONAL) | what an update-state check would read | F-17 | S1 SQ-12 |

Facts already established from upstream documentation, so that the spike does not spend time on them (retrieved 2026-11-14; see the source register for line ranges):

- The upstream Docker CE unit is ordered after `network-online.target` and before `zincati.service`, runs only while its stamp file is absent, and writes the stamp before it reboots (SR-20 L28–31, L37–39). S1's reasoning for gating the stack on the installed package rather than on the stamp (P-06) rests on exactly this order.
- The Proxmox procedure sets a static address on the Proxmox side with `--ipconfig0` and delivers Ignition with `--cicustom vendor=…`; it creates a snippet-capable storage first (SR-22 L22–31, L119–120, L132–143).
- Caddy's internal root certificate is valid for 3600 days and the intermediate for 7 days by default; leaf certificates for 12 hours; installing the root into a trust store from inside a container can fail, so the root is copied out (SR-25 tls.md L454–458).

These are facts about the tools' documentation. How they behave on the lab is still for the spike.

## 5. How each acceptance check is run and what it leaves

The full design — preconditions, positive case, negative case, the right-reason check, what cannot be verified yet — is in [S2 § 10](delegation/s2-security-verification.md#10-verification-design). This table is the index. Script and evidence names are proposals until the scaffold fixes them.

| Check | First full run | Script | Evidence file | The control that makes a pass mean something | Waits on |
|---|---|---|---|---|---|
| AC-01 Rebuild | D9 | `tests/host-rebuild-verify.sh` after the owner's documented build | `docs/evidence/ac-01-rebuild.md` | the log shows a machine provisioned after the run started; the Moby package is absent; a previous root certificate fails against the new VM | OQ-02, OQ-05, D-32 |
| AC-02 HTTPS | D7 (application name alone at D5, partial) | `tests/proxy-https.sh` | `docs/evidence/ac-02-https.md` | the same request without the lab root fails on verification, in the same session | OQ-06 |
| AC-03 Certificate lifecycle | starts at D7, after the last proxy change, and must end before AC-09; expected within a day (the renewal point is unverified, SP-17) | `tests/proxy-cert-renewal.sh` | `docs/evidence/ac-03-cert-renewal.md` | new serial under the same root, the proxy's container start time unchanged, no manual step between the readings | AC-02 |
| AC-04 Mail | D6 | `tests/mail-send-trace.sh` | `docs/evidence/ac-04-mail.md` | a token that is new on every run; the queue ID in the received message equals the one in the log | OQ-04, OQ-11 |
| AC-05 Relay protection | D6 | `tests/mail-relay-refusal.sh` | `docs/evidence/ac-05-relay-refusal.md` | the probe got Postfix's banner in the same session and the allowed client succeeded in the same run; a timeout is a FAIL | OQ-11 |
| AC-06 Log search | D7 | `tests/logs-search.sh` | `docs/evidence/ac-06-log-search.md` and a screenshot | a query for a token never sent returns nothing; an unauthenticated query is refused | the log route |
| AC-07 Firewall | D9 (partial at D4) | `tests/firewall-negative-external.sh`, `tests/firewall-negative-container.sh` | `docs/evidence/ac-07-firewall.md` | per blocked path, the allowed counterpart succeeds first in the same run; a negative with a failed control is a FAIL | OQ-06; all services running |
| AC-08 Monitoring | D8 | `tests/monitoring-service-restart.sh` | `docs/evidence/ac-08-monitoring.md` and screenshots | the state was OK just before the stop, so the alert is not a certificate error | OQ-03 |
| AC-09 Restart | D9 | `tests/host-restart.sh docker`, then `vm` | `docs/evidence/ac-09-restart.md` | the client role sees an outage and a recovery while the forbidden role never gets through | AC-02, AC-07 |
| AC-10 Restore | D11 | `tests/backup-restore.sh` | `docs/evidence/ac-10-restore.md` | data written after the backup is absent after the restore | OQ-19 |

Every evidence file records the date, the VM build, the versions in use, the role each request came from, the command and its output, and a PASS or FAIL line; a check that did not run says "not run" (SR-08). Scripts print variable names instead of lab values and never read a secret into output.

AC-05 and AC-07 are load-bearing (SR-08). Neither draft narrows them: the unauthorised relay client is placed on Postfix's own network, where it is strongest, and every blocked path is tried from every forbidden role the lab has.

## 6. Traceability: every requirement row has a proof

The requirements table is not changed. This names where each row's proof lands (R-01; F-01, F-14).

| Requirement row ([architecture § 2](../architecture.md#2-követelmények-és-döntések)) | Built in | Proven by |
|---|---|---|
| Fedora CoreOS on Proxmox | D1, D3, D9 | AC-01 |
| Docker CE | D1, D3, D9 | the required "Docker CE proof" block of the AC-01 evidence: `rpm -q docker-ce`, `rpm-ostree status`, `docker version`, and the Moby package absent (D-32) |
| Web service | D5 | **EV-WEB** `docs/evidence/req-web-function.md`: login, a post, an upload, read back over verified HTTPS, and again after AC-09 |
| HTTPS reverse proxy | D4, D5 | AC-02 |
| Internal CA and automation | D4, D5 | AC-02, AC-03 |
| SMTP container | D6 | AC-04, AC-05 |
| Searchable logs | D7 | AC-06 |
| External monitoring | D8 | AC-08. The row names an agent as well as active checks; see § 7, row 6 |
| Firewall and isolation | D4, D9; extras at D10 | AC-07, AC-09 |
| Optional operations | D11; secrets from D5 | restore: AC-10 · update trial: **EV-UPD** `docs/evidence/req-update-trial.md` · secrets: **EV-SEC** `docs/evidence/req-secrets.md` |

## 7. Where the drafts disagreed, and how it is settled

The writers worked in parallel and could not read each other. The critic listed the contradictions; this table records each with the evidence and the outcome. "Settled" means settled as a proposal within this plan; the owner can overrule any of it.

| # | Point | S1 | S2 | Evidence | Outcome |
|---|---|---|---|---|---|
| 1 | Log collection route | Docker's journal log driver, Alloy reads the host journal (P-09) | Shared log volumes first: no host mount, no SELinux exception expected; the journal second, with a narrow log-reader type (§ 9.2) | SR-07 forbids a label exception without a recorded justification. Whether either route works under enforcing SELinux is unverified (SP-15). The requirement asks for web and SMTP logs (SR-01 § 2 L30) | **Not settled; decided by SP-15.** Order of preference: the route that needs no exception. If both need none, the journal route, because it also covers the host units. The log driver is fixed before D3 either way (S1 P-16) |
| 2 | Loading the firewall rules against Docker's own container start | Firewall unit after Docker; systemd as the only starter; a restart policy that keeps the daemon from starting containers (P-07) | Two stages: one before Docker with a pre-created chain, one after; S1's approach as the fallback (§ 3.3) | Neither behaviour is verified (SP-07, SP-08). S1 states that its constraint relaxes if rules load before Docker | **Settled:** S2's two-stage unit is the design; S1's restart-policy rule is the fallback if SP-07 shows Docker discards the chain. Both drafts agree the stack unit requires the firewall unit |
| 3 | How lab addresses reach the firewall unit | Lab-private values are parameters of the build: in the rendered, untracked Ignition (P-02) | A variables file copied to the VM like the secrets (§ 3.3) | Addresses are lab-private but not secret (SR-07). A firewall that waits for a manual copy is closed but not working after a fresh build | **Settled:** addresses ride in the rendered Ignition, which is never tracked; secrets never do. The firewall is then complete on first boot |
| 4 | When the Docker networks take their final form | Created as base design at D4–D7; internal flags and isolation tests at D10 | Final form from the first Compose change; only the isolation *claims* wait for D10, because a later split forces six checks to be re-run (§ 4.3) | SR-03 forbids building an EXTRA item while a MUST HAVE row is unproven; SR-08 requires re-runs after a relevant change; AC-07 itself tests from an unauthorised container | **Escalated to the owner** (OQ-27). Recommended: S2's reading. The plan table above assumes it |
| 5 | Networks beyond the architecture's five | not addressed | adds `relay-out` for Postfix only, and `edge` for Caddy if SP-12 requires it (§ 5) | F-10: with five networks Postfix has no route to the relay unless WordPress shares one | **Proposed as an architecture edit** (D-36); the architecture is not changed by this package |
| 6 | What closes the monitoring row | Agent script without a package, with local checks, as the route for the row; active checks as the floor (P-13) | The smallest route for AC-08 is the active check alone (§ 10.8) | The requirement row names "agent and active checks" (SR-01 § 2 L31); AC-08 asks only for an alert on a stopped service (L148) | **Settled:** AC-08 can pass on the active check. The requirement row is closed only with agent evidence as well, recorded in the AC-08 evidence file. If the spike rules the agent out, that is reported as a gap against the row, not hidden behind AC-08 |
| 7 | Spike question numbering | SQ-01 … SQ-12 | SQ-1 … SQ-12, different questions | — | **Settled:** the merged list SP-01 … SP-20 in § 4 |

### Corrections taken from the critic's review of the drafts

The drafts are kept as written; these points override them where they differ. Critic's reference in brackets.

| Draft | Point | Disposition |
|---|---|---|
| S1 | The agent option "over SSH with a restricted key" conflicts with SSH being reachable from the admin network only [§ 7 a] | Dropped unless the Checkmk source lies in the admin network; the socket variant remains |
| S1 | On the first boot the firewall unit is skipped while the network is up [§ 7 b] | The host-rule stage does not wait for the Docker CE engine (D-37, F-22) |
| S1 | Secrets evidence placed in the OPTIONAL step [§ 7 c] | EV-SEC is produced from D5 (§ 3) |
| S1 | The stack unit waits for a secrets-ready marker nobody creates; the stub at D4 has no secrets [§ 7 g; § 8 e] | Open design point for the host step: the marker is created by the last step of the secrets procedure, and the condition applies from D5, not to the stub. Recorded, not designed here |
| S1 | A Postfix image built on the VM has no registry digest and adds a package source [§ 7 h] | Open with OQ-11: the base image is pinned by digest and the package by version, and the package source joins the documented sources of AC-01; whether that satisfies "pinned by version or digest" is for the owner |
| S1 | The mail step's exit had no refusal in it [§ 7 i] | Added (§ 3, D6) |
| S2 | Rule H4, ICMP echo, has no source in the architecture [§ 8 a] | Not part of the mandatory set; kept only if the owner wants it (D-42) |
| S2 | "Fails closed" covered published ports only [§ 8 b] | Lab addresses in the rendered Ignition make the host rules complete on first boot (§ 7 row 3) |
| S2 | EV-WEB writes to the lab but was not named among the tests that do [§ 8 c] | Its script header and name say so; listed with the proposed wording change to the test rule in the readiness report |
| S2 | No test topology: where the runner sits and how it reaches each role [§ 8 d] | Asked in OQ-06; the acceptance runner cannot be designed before the answer |
| S2 | AC-01's "provisioned after the run started" names no time source [§ 8 f] | Open design point for the AC-01 script |
| S2 | Rotation inside shared log volumes has no owner [§ 8 g] | Belongs to the log step if that route is chosen (D-38); the rotation and retention settings are part of the AC-06 evidence (F-25) |
| S2 | AC-07 in full runs four times [§ 8 h] | Three if the final run is on the rebuilt VM (OQ-29). The two runs after restarts are required by the test rule; the boot-window probe is kept as an addition to AC-09, not a condition of it |
| both | Nobody owned the trigger that makes WordPress send the AC-04 message [§ 9] | The platform side provides the trigger (the CLI run of S1 § 6.2); the test script calls it |

Three conflicts between sources, found by the writers, are not disagreements between drafts and go to the owner: the Compose secrets mechanism is OPTIONAL in the scope lock but required by the security rule (OQ-26); the Checkmk source on TCP 443 against the firewall rule line (OQ-28); and network isolation as EXTRA against AC-07 (OQ-27, row 4 above).

## 8. What stays unverified

Stated here so that the plan is not read as stronger than it is.

- **Every upstream behaviour not listed in § 4 as an established fact.** The writers did not open the upstream sources; they worked from the register and marked the rest unverified. Each such statement in the drafts names the spike question or the document that would verify it.
- **Everything about Checkmk** (SR-26 not retrieved, OQ-25).
- **Postfix configuration details**, which come from general knowledge and depend on the image (OQ-11).
- **Image behaviour**: file-based credentials, health endpoints, data paths. Verified per image when it is pinned, with `upstream-claim-verify`.
- **The static gate commands**, which have never been run (OQ-18).
- **The provisioning procedure**, which has not been tried on the lab.

## 9. Not in this plan

- No configuration, script or test file. Those are written after the implementation gate, under issues.
- No dates and no effort in hours or days (OQ-01).
- No change to the architecture, the rules or the fixed tables. Proposed changes are listed in [readiness-report.md](readiness-report.md).
- Nothing for the rejected Swarm alternative.
