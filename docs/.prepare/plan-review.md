# Plan Review — CoreOS Platform Lab

| Field | Value |
|---|---|
| Document ID | PREP-06 |
| Title | Plan Review and Ranked Recommendations |
| Revision | r4 |
| Status | ready-for-human-review |
| Owner | Orchestrator session (author); independent reviewer: plan-critic; approver: repository owner |
| Last updated | 2026-11-16 |
| Core-context revision used | r1 for §§ 1–8 as first written; r2 (`docs-baseline-r2`) for the corrections and § 9 |
| Dependencies | [core-context.md](core-context.md) r1, [source-register.md](source-register.md) r1, [decision-log.md](decision-log.md) r1, [open-questions.md](open-questions.md) r1, [methodology-adaptation.md](methodology-adaptation.md) r1; for the dated note added in r4: [source-register.md](source-register.md) r4 (SR-28, SR-29) |
| Change summary | r1: findings, recommendations and initial ranking. r2: the critic's review integrated — three severities changed, four line references corrected, six findings added (F-22 … F-27), two recommendations added (R-20, R-21), R-16 merged into R-01, R-03 and R-09 amended, R-14 widened; § 9 records every challenge, the response and the re-ranking. The initial scores in § 7 are kept unchanged as the record of the first pass. r3 (2026-11-16, records reconciliation): one dated note under F-16. No finding, severity, score or rank changed. r4 (2026-11-16, documentation closeout DOC-1): one dated note under the table of § 6, on R-21 and the root `CLAUDE.md`. No finding, severity, score or rank changed. r4, extended on 2026-11-16 after an independent review (DOC-1b): the Dependencies field names the source-register revision of the note |

## 1. Method and limits

The review reads [docs/architecture.md](../architecture.md) (SR-01; line numbers below refer to the migrated file) against three things: the repository as it is, the reviewer's three answers (D-01 … D-03), and the adapted methodology (M-02, M-03, M-09).

Limits that apply to every finding:

- **Nothing is built.** No finding rests on an observation of the lab. A finding about how a tool behaves cites upstream documentation retrieved on 2026-11-14 (SR-20, SR-22, SR-24, SR-25) or is marked unverified.
- **The fixed tables are not criticised as tables.** The requirements table and the acceptance table are taken as given. Findings concern how a row can be proven, or what the architecture leaves unsaid.
- **Severity** is the consequence if the gap is left as it is: *Critical* — the deliverable cannot meet a reviewer decision; *High* — a MUST HAVE acceptance check cannot be passed or would pass for the wrong reason, or a security boundary is unproven; *Medium* — rework, ambiguity or a public inconsistency; *Low* — polish.
- No finding is Critical. That is a result, not an omission: the architecture meets the three reviewer decisions on paper.

## 2. Dimensions

| Dimension | Applicable | Findings |
|---|---|---|
| Requirement coverage | yes | F-01, F-14 |
| Host provisioning and reproducibility from Butane | yes | F-02, F-09, F-12 |
| Docker CE installation and update risk | yes | F-09, F-17; strength S-8 |
| Service design and data persistence | yes | F-11, F-24, F-25; strength S-7 |
| Network isolation and the three firewall layers | yes | F-03, F-04, F-10, F-13, F-21, F-22, F-27 |
| TLS and the internal CA | yes | F-12, F-18; strength S-3 |
| Mail path and relay protection | yes | F-05, F-06, F-11 |
| Log collection | yes | F-08 |
| Monitoring integration | yes | F-06, F-07 |
| Secrets handling | yes | F-20, F-23 |
| Backup and restore | yes, OPTIONAL tier | no separate finding: the section is sound in outline (S-7) and its open values are OQ-19 |
| Testability of AC-01 … AC-10 and their evidence | yes | § 5; F-01, F-04, F-05, F-12, F-18 |
| Dependencies and sequencing | yes | F-13, F-26 |
| Unresolved external dependencies | yes | F-02, F-06 |
| Public-repository hygiene | yes | F-15, F-16 |
| Unnecessary complexity | yes | none in r2: F-21 was reframed as a tier conflict; the plan carries nothing the brief does not need |

No dimension is marked not applicable.

## 3. Strengths worth preserving

| ID | Strength | Evidence |
|---|---|---|
| S-1 | The document never claims to be proven: its status line and its last sentence both say so | SR-01 L3, L152 |
| S-2 | The single points of failure are stated without softening | SR-01 § 9 L129 |
| S-3 | It forbids proving HTTPS with verification switched off | SR-01 § 5 L73; § 10 L142 |
| S-4 | It places rules for published container ports in `DOCKER-USER`, not `INPUT`, and makes that conditional on the iptables backend. Both points agree with the upstream documentation | SR-01 § 6 L101; SR-24 iptables L48–52, nftables L52–55 |
| S-5 | A read-only Docker socket mount is not treated as read-only API access | SR-01 § 6 L103 |
| S-6 | Log labels are kept low-cardinality, with queue and request identifiers left in the log line | SR-01 § 7 L109 |
| S-7 | The backup section names the traps: a live volume copy is not a consistent database backup, a restored mail queue can send twice, a copy on the same host is not a backup | SR-01 § 8 L117–119 |
| S-8 | The Fedora major-upgrade risk of the package override is stated and matches the upstream note | SR-01 § 2 L37; SR-20 L62–73 |
| S-9 | Negative tests are part of acceptance, from outside and from an unauthorised container | SR-01 § 10 L145, L147 |

## 4. Findings

Each finding: severity · evidence · what is missing or risky · consequence · recommended correction · confidence · linked recommendations.

**F-01 — The Docker CE decision has no acceptance row** · High
- Evidence: SR-01 § 2 L25 gives the proof (`docker version`, `rpm -q docker-ce`, `rpm-ostree status`); the acceptance table § 10 L141–150 has no row for it. D-02 is one of three reviewer decisions.
- Missing: a place where that proof is run and recorded.
- Consequence: AC-01 as written would pass on the Moby engine; the release gate (AC-01 … AC-09) could pass without evidence for a reviewer decision.
- Correction: make the Docker CE proof a required part of the AC-01 evidence; do not add a row.
- Confidence: High. · R-01

**F-02 — How the VM is created on Proxmox is not described, and the documented way needs root on the host** · High
- Evidence: SR-01 § 3 L41–47 says Butane and Ignition, not how Ignition reaches the VM. SR-22 L7: "All of the commands will be run as the `root` user on the Proxmox VE host"; L22–31 snippet storage; L94–124 image import and `--cicustom vendor=…` delivery. SR-07 "Lab access" limits agent access to a read-only auditor token unless the owner agrees to more.
- Missing: the provisioning procedure, who runs it, and with which privileges.
- Consequence: AC-01 and the whole of step 2 have no defined starting point; a session could assume API access it must not have.
- Correction: decide and document the procedure as the owner's root procedure with a parameterised script; keep the API token read-only.
- Confidence: High for the upstream facts; the procedure is untried on the lab. · R-02, OQ-05

**F-03 — The host firewall has no mechanism: how rules are loaded, in what order against Docker, and how they match** · High
- Evidence: SR-01 § 6 L101 states that rules "survive a Docker and host restart" but not how. SR-24 iptables L83–95: packets reach `DOCKER-USER` after destination translation, so rules on the published port must use the `conntrack` original-destination match. The architecture names no firewall service or rule loader anywhere (§ 3, § 6); this is an observation about the document, not about what FCOS ships.
- Risky: (a) no persistence mechanism is named; (b) nothing orders rule loading before the stack starts, so a window with a published port and no rule is possible after boot; (c) a rule written against port 443 without the original-destination match matches the container's port, which is correct only while the mapping is 443 to 443 — a latent fault; (d) host-level rules for TCP 22 and the monitoring port (§ 6 L94–95) belong in `INPUT`, a second place.
- Consequence: AC-07 and AC-09 can fail, or pass while the boundary is open during boot.
- Correction (amended in r2): specify one mechanism before any rule is written, shipped by Butane and idempotent, in two stages — host rules and a pre-created chain **before** Docker starts, re-application after every Docker start — required by the Compose unit, with an explicit check that the chain exists. A unit that only runs after Docker does not close gap (b), because the daemon can start containers before any later unit runs (unverified; SP-07, SP-08).
- Confidence: High for (a)–(c) from the sources; behaviour on FCOS is unverified (A-02). · R-03, R-08

**F-04 — The firewall tests have no addresses to test from** · High
- Evidence: SR-01 § 6 L93–97 names an "internal user network", an "administration network", "Checkmk" and an "unauthorised client" as sources; § 3 L41 says "stable IP and name resolution"; § 10 L133 lists DNS as something to clarify. No addressing plan exists in any source.
- Missing: the VM address, name resolution, and a source for each test role — client, admin, Checkmk, a forbidden source that can still reach the VM, and if possible a second, routed one (F-27).
- Consequence: no rule can be written concretely and no negative test can be shown to fail for the right reason (SR-08 "Load-bearing tests").
- Correction: obtain the plan from the owner; keep real addresses out of tracked files and feed tests from variables.
- Confidence: High. · R-04, OQ-06

**F-05 — "Unauthorised client" in the relay check is undefined, so the test can pass for the wrong reason** · High
- Evidence: SR-01 § 7 L107 and § 10 L145; SR-08 asks for an "SMTP transcript with the rejection"; SR-07 "Forbidden" allows a trusted network as wide as "the fixed Compose subnet of the allowed client".
- Risky: if the test client cannot reach Postfix at all, the result is a timeout, which proves network isolation, not relay protection. If the trusted network is the whole mail subnet, any container on that network may relay.
- Consequence: AC-05, a load-bearing check, would not prove what it names.
- Correction: define the allowed client as one fixed address, the test client as a second container that can reach Postfix on the same network, and the expected result as an SMTP refusal; test reachability from outside separately under AC-07.
- Confidence: Medium: the design space is clear; Postfix behaviour is from general knowledge, not a retrieved source. · R-05

**F-06 — Two MUST HAVE checks depend on systems that may not exist** · High
- Evidence: SR-01 § 7 L107 (a test receiver proves only in-lab delivery), L111 (Checkmk "preferably" elsewhere); § 10 L133; OQ-03, OQ-04 carried since 2026-11-13 (SR-14).
- Missing: a relay with a mailbox for AC-04, a Checkmk instance for AC-08.
- Consequence: AC-04 and AC-08 cannot be passed; the release gate cannot be met.
- Correction: get the owner's answers before the mail and monitoring steps are planned in detail, and state in advance what each fallback can and cannot prove.
- Confidence: High. · R-06

**F-07 — The Checkmk agent on an image-based host is an unsolved integration** · Medium (High in r1)
- Evidence: SR-01 § 7 L111 calls it an "early implementation trial"; OQ-08. **The Checkmk documentation was not retrieved (SR-26); the plugin's Python requirement and FCOS shipping without Python are unverified (A-04).**
- Risky: the usual installation is a package; layering one more package onto the host adds update risk (compare SR-20 L62–73). A Docker plugin that needs an interpreter the host lacks cannot run there.
- Consequence: AC-08 itself has a floor route — an active check — so it is not unpassable; what has no route is the agent the requirement row names (SR-01 § 2 L31) and the check groups of § 7 L111. Even the floor needs the lab root in Checkmk's trust store, which is unverified.
- Correction: define the smallest route that satisfies the acceptance row as written — an alert on a stopped service can come from an active HTTPS check alone — and treat agent and Docker checks as an addition decided after the spike.
- Confidence: Low to Medium, because the key facts are unverified. Severity lowered in r2: the High test (a MUST HAVE check cannot be passed) is not met. · R-07, R-08, OQ-25, OQ-30

**F-08 — The log collection route is undecided and the host-mount candidates meet SELinux** · Medium
- Evidence: SR-01 § 4 L65 (Caddy writes an access log; the Postfix image's log target "must not be assumed"); § 6 L103; OQ-09. SR-07 forbids `label=disable` and a socket mount without a recorded justification.
- Risky: reading the host journal or the Docker socket from a container needs a host mount under enforcing SELinux. Whether that works without a label exception is **unverified**. A third route — services write into shared volumes the collector mounts — needs no host mount (S2 § 9.2) but depends on the Postfix image.
- Consequence: AC-06 may need an exception that the rules require to be justified in writing, or a different route.
- Correction: answer it in the spike, then decide and record the justification if one is needed.
- Confidence: Low for the SELinux behaviour (unverified); High that the route is undecided. · R-08, R-13

**F-09 — The first boot is not reproducible in time and its ordering against the stack is unstated** · Medium
- Evidence: SR-01 § 3 L44 says the verified versions "enter the installation documentation"; SR-06 says components are "pinned in configuration". The upstream unit installs whatever `docker-ce` the repository offers that day (SR-20 L37) and reboots (L39). SR-01 § 3 L45 starts the Compose project "after the network and Docker".
- Missing: the FCOS stream and version, a Docker CE version policy, where the repository's signing key comes from, and a condition that keeps the Compose unit from starting before the post-install reboot.
- Consequence: two rebuilds can produce different engines; AC-01 "from documented sources" becomes ambiguous; the first boot can start the stack on the wrong engine or fail noisily.
- Correction (amended in r2): pin and record, ship the repository file and key with Butane, and gate the Compose unit on the **booted engine being Docker CE**. The install stamp is not enough: upstream writes it before the reboot (SR-20 L38–39), and the new engine exists only after it.
- Confidence: Medium. · R-09, OQ-14

**F-10 — Egress is described by intent, not by network** · Medium
- Evidence: SR-01 § 6 L81–87 lists five networks; L89 says the database and log networks get no direct internet exit, Postfix needs "a separately permitted exit", and an `internal` network's limits "must be tested".
- Missing: which networks are internal, and which network gives Postfix its route to the relay. Postfix is a member of `mail` only (L85).
- Consequence: either `mail` is not internal, and WordPress and Postfix share an exit, or Postfix cannot reach the relay.
- Correction: complete the network table with an internal flag and an egress path per network; give Postfix its own egress network; restrict that egress to the relay port in the host layer.
- Confidence: Medium. · R-10

**F-11 — The Postfix image and the WordPress mail integration are not chosen** · Medium
- Evidence: SR-01 § 4 L65 ("the chosen Postfix image"), § 4 L56 ("SMTP integration"); OQ-10, OQ-11.
- Missing: an image with a pin, and the way WordPress hands mail to Postfix.
- Consequence: AC-04, AC-05 and the mail half of AC-06 cannot be designed in detail.
- Correction: choose by stated criteria and verify the claims against the image's documentation.
- Confidence: High that it is open. · R-11

**F-12 — AC-01 does not say what a rebuild includes** · Medium
- Evidence: SR-01 § 10 L141; § 5 L71 (the CA lives in Caddy's persistent data); § 10 L150 (restore keeps CA trust).
- Missing: whether a rebuild restores data and the CA. A fresh build creates a new CA, so every client must trust a new root. A rebuild also needs room for a second VM or the destruction of the first (OQ-02).
- Consequence: the check can be argued either way after the fact.
- Correction: define AC-01 as a fresh build without restore, with trust distribution as a documented step (D-32).
- Confidence: High. · R-01, R-12

**F-13 — Step 2 builds the firewall before there is anything to test it against** · Medium
- Evidence: SR-01 § 10 L134–136; SR-08 "A negative test must fail for the right reason: the service is running and reachable from an allowed source".
- Risky: at step 2 no service exists. The paths to the database, SMTP and Loki can only be tested meaningfully once those services run.
- Consequence: AC-07 marked passed at step 2 would be a test against nothing.
- Correction: prove the host rule at step 2 against a stub service; run AC-07 in full when all services exist; run the spike before the scaffold depends on its answers (D-33).
- Confidence: High. · R-12

**F-14 — Proofs named in § 2 that have no row in § 10** · Medium
- Evidence: SR-01 § 2 L26 (login, content and upload), L27 (the HTTP backend), L31 (the agent), L33 (restore *and update* trial). Secrets (§ 8 L115) have no proof named even in § 2. The acceptance table covers restore (L150) but none of the others.
- Consequence: these proofs have no owner in the test plan.
- Correction: a traceability table that maps every requirement row to an acceptance check or a named evidence item.
- Confidence: High. · R-01

**F-15 — Rules state as policy what the owner has not confirmed** · Medium
- Evidence: SR-13 "Decisions Made" marks the scope list, the AC numbering, the release gate, the Docker CE additions and the Zincati policy as unconfirmed; they appear as rules in SR-04, SR-08, SR-06 and SR-03 principles 3 and 9, and in SR-01 § 2 L35–37.
- Consequence: an owner who approves "the rules" approves these without having been asked; a later change touches several files and, after publication, public labels.
- Correction: one explicit pass by the owner over D-20 … D-25 and D-27 before the publication gate.
- Confidence: High. · R-14

**F-16 — Public artifacts carry stale or unreviewed content** · Medium
- Evidence (not re-observed by the critic): diagrams 01–04 footers say the Docker CE question is "to be clarified" and cite the old file names; diagram 01 says "recommended submission"; diagram 03's subtitle speaks of two firewall layers; diagram 01 is linked from SR-01 § 1 (viewed 2026-11-14). The toolkit under `.claude/skills/` includes third-party skills, one with a licence file, one with a licence line, others without a stated origin (OQ-17). The repository has no licence (OQ-22). The commit author address becomes public on push (OQ-21). `docs/.prepare/` itself is tracked and will be public; it names two other repositories of the owner, both public (checked 2026-11-14) and both already named in the tracked steward definition.
- Consequence: a public contradiction of D-02; possible licence problems; an address published without a decision.
- Not a public artifact, noted for the owner: `.claude/settings.local.json` is ignored by git but pre-approves `gh issue` and `gh pr` commands for agent sessions on this machine.
- Correction: settle these at the publication gate.
- Confidence: High. · R-15
- *Note of 2026-11-16, not part of the review:* the finding is kept as observed on 2026-11-14. Two parts of its evidence have since been settled by owner decisions: the diagram text by D-44 (diagrams 01–04 regenerated; OQ-23 closed as CQ-07) and the toolkit by D-45 (excluded from git; OQ-17 closed as CQ-08). The licence (OQ-22) and the commit address (OQ-21) are still open.

**F-17 — A blocked host update would go unnoticed** · Low
- Evidence: SR-01 § 2 L37 and § 9 L125; SR-20 L62–66. How Zincati reports a failed deployment is **unverified**.
- Consequence: the host could stay on an old release silently.
- Correction: a check on update state, in the OPTIONAL tier.
- Confidence: Low. · R-19

**F-18 — Evidence for AC-06 is a screenshot only; AC-03 and AC-08 lack a form** · Low
- Evidence: SR-08 table: AC-06 "query and result screenshot"; AC-08 "Checkmk state before and after" and AC-03 "Caddy log and the new certificate's validity dates" name the content but not a re-runnable form. SR-25 tls.md L458: internal leaf certificates default to a 12-hour lifetime, so a renewal should be observable within a day without changing configuration; the renewal point inside that lifetime is unverified (SP-17).
- Consequence: screenshots alone are hard to re-run and to compare.
- Correction: add command output next to each screenshot, and define the AC-03 trial from the default lifetime.
- Confidence: High for the lifetime (upstream); Medium for the rest. · R-16

**F-19 — The static gates cannot run on the workstation as written** · Low
- Evidence: SR-08 "Gates"; SR-21 (`butane`, `caddy`, `shellcheck` not installed; `docker` is); OQ-18.
- Correction: run each from a pinned container in `scripts/validate.sh`, as SR-08 already allows.
- Confidence: High. · R-17

**F-20 — "Protected transfer" of secrets names no channel** · Medium (Low in r1)
- Evidence: SR-01 § 3 L47, § 8 L115; OQ-16. The first service with a credential and the stack unit both wait on it (S1 § 5); ownership and SELinux label of the secret files are unverified (S2 § 7.3, SP-14).
- Correction: document one channel, the target directory, ownership and mode, and the example file.
- Confidence: High that it is open. · R-18

**F-21 — The line between the mandatory layer and the EXTRA network isolation runs through a MUST HAVE check** · Medium (Low in r1, reframed)
- Evidence: SR-01 § 6 L101: the two extra layers "are also implemented and tested"; SR-03 scope lock marks Docker-network isolation EXTRA and forbids building an EXTRA item while a MUST HAVE row is unproven; AC-07 (MUST HAVE, § 10 L147) requires blocked connections to fail "from an internal, unauthorised container"; § 6 L81–87 draws five networks as the base design.
- Consequence: part of the EXTRA row sits inside a MUST HAVE check. If the networks are split only at the EXTRA stage, six checks must be re-run (S2 § 4.3). The two drafts read it differently.
- Correction: an owner decision on where the line runs (OQ-27). Recommended reading: the networks take their final form with the first Compose change as base design; only the isolation *claims* and the egress rules wait for the EXTRA stage. Apart from this, the plan carries nothing the brief does not need: the service count and the networks follow from the requirements.
- Confidence: High. · R-12, R-14

### Findings added in r2

Found by the plan-critic (its K-numbers in brackets) or by the writers, and classed here by the orchestrator.

**F-22 — The host's own ports are unprotected until the rules load** · Medium [K-05]
- Evidence: F-03 covers published container ports only. S1 § 5 skips the firewall unit on the first boot; S2 § 3.3 delivers the lab values after first boot. SR-07 "Host": SSH is "reachable from the admin network only".
- Consequence: on a fresh VM, TCP 22 is limited by nothing until the rules are complete. SSH is key-only, which bounds the exposure but does not meet the rule line.
- Correction: the host-rule stage must not wait for the Docker CE engine or for a manual copy: lab addresses ride in the rendered, untracked Ignition. · R-03

**F-23 — The secrets mechanism is OPTIONAL in the scope lock and required by the security rule** · Medium [K-01; S1 C-1]
- Evidence: SR-03 "Scope Lock" row "Compose secrets mechanism: OPTIONAL … keeping secrets out of git is not optional"; SR-07 "Secrets handling" requires Compose secret files and forbids inline secrets.
- Consequence: the sequence needs the mechanism from the first service with a credential, which an OPTIONAL tier may not precede.
- Correction: an owner decision (OQ-26). Recommended: file-based secrets are base design from the web step; "optional" describes the brief, not the build. · R-14, R-18

**F-24 — "SELinux stays enforcing" may not mean that containers are confined** · High, provisional [K-02]
- Evidence: SR-07 "Host" and SR-01 § 6 L103 require SELinux enforcing and correct mount labels. D-02 replaces the engine FCOS ships with Docker's own packages. Whether that engine confines containers without an explicit daemon setting is **unverified** (S2 § 9.1, SP-11).
- Consequence: the host could report enforcing while containers run unconfined; mount labels would then mean nothing.
- Correction: answer SP-11 in the spike; if a setting is needed it ships in Butane; AC-01 records the daemon's security options next to the host mode.
- Confidence: Low — the risk is plausible and unverified, so the severity is provisional. · R-20

**F-25 — The disk-fill control has no proof** · Medium [K-03]
- Evidence: SR-07 "Logs" and SR-01 § 7 L109 require rotation, retention and a disk alert together. No acceptance row and no evidence item covers them; a disk alert needs a host agent, which the AC-08 floor does not have.
- Correction: name the proof — the retention and rotation settings in the AC-06 evidence, the disk check in the agent part of the AC-08 evidence. · R-01, R-07

**F-26 — Which VM carries the release evidence is undecided** · Medium [K-04]
- Evidence: SR-08 "Evidence rules" (evidence records the VM build); AC-01 builds a second VM with a new CA; the drafts place some checks on the first VM and others on the second.
- Correction: an owner decision (OQ-29). Recommended: the rebuilt VM is the one on which the final acceptance run happens, so that AC-01 and the release evidence describe the same build. · R-12

**F-27 — The tests need more source roles than the plan assumes** · Medium [K-07]
- Evidence: S2 § 1 defines client, admin, Checkmk and two forbidden roles; A-07 assumed two. S2 § 2.1 E2 forbids the admin source on TCP 443, so the admin workstation cannot run the client-role tests unless it lies in the client network. Where the test runner sits is not designed.
- Correction: OQ-06 asks for each role and for the machine the client-role tests run from. · R-04

**Smaller points recorded without a finding number:** the repository layout (D-05) has no place for per-service configuration files, and the commit scope table has no scope for `scripts/validate.sh` [K-08] — both are proposed rule and layout changes in [readiness-report.md](readiness-report.md). The mandatory layer's rule file has no static check [K-12]; whether one is worth adding is left open at the scaffold. The methodology named a recommendation for a root `CLAUDE.md` that did not exist [K-11]; it is now R-21. That the writers worked from paraphrases of the upstream sources [K-10] is addressed by the line-by-line table added to the source register in r2 and remains a limit for every source listed there as not retrieved.

## 5. Acceptance checks: testable as written?

| Check | Testable as written? | What evidence would prove it | Gap |
|---|---|---|---|
| AC-01 Rebuild | Partly: "the environment" is not delimited | Run log of a fresh build with versions, plus the Docker CE proof | F-01, F-02, F-09, F-12 |
| AC-02 HTTPS | Yes | `curl` with the lab root CA and name resolution by option or hosts entry; certificate subject, issuer and dates | needs OQ-06 |
| AC-03 Certificate lifecycle | Yes, within a day at the default lifetime | Two certificates for the same name with different serials and validity, and the proxy's log lines between them | F-18 |
| AC-04 Mail | Only with a real relay and mailbox | Postfix log line with queue ID, the received message with identifying data redacted | F-06, F-11 |
| AC-05 Relay protection | Not until the unauthorised client is defined | SMTP transcript ending in a refusal, plus the same client's allowed counterpart succeeding | F-05 |
| AC-06 Log search | Yes, once the route is chosen | The query text and its result as text, plus a screenshot | F-08, F-18 |
| AC-07 Firewall | Not until addresses exist; fully only when all services run | Per blocked path: the forbidden attempt failing and the allowed one succeeding | F-03, F-04, F-13 |
| AC-08 Monitoring | Only with a Checkmk instance | Check state before the stop, after it, and after the restore | F-06, F-07 |
| AC-09 Restart | Yes | AC-02 and AC-07 re-run after a Docker restart and after a reboot | depends on F-03 |
| AC-10 Restore | Yes in outline; OPTIONAL | Restore log with measured times, AC-02 with the old root still trusted | OQ-19 |

## 6. Recommendations

Effort is a relative size, because no time budget exists (OQ-01): **S** — one document section or one small file; **M** — several files or one lab session; **L** — several lab sessions. The basis is stated per row.

| ID | Findings | Action | Expected outcome | Dependencies | Effort and basis | Acceptance criteria | Uncertainty |
|---|---|---|---|---|---|---|---|
| R-01 | F-01, F-12, F-14 | Add a traceability table to the implementation plan: every requirement row → acceptance check or named evidence item. Put the Docker CE proof into the AC-01 evidence. Define AC-01 as a fresh build (D-32) | Every reviewer decision has recorded proof | D-32 confirmed | S — one table | Ten requirement rows mapped; AC-01 evidence lists three Docker CE commands | none |
| R-02 | F-02 | Document VM creation as the owner's root procedure on the Proxmox host, after SR-22, with a parameterised script; the API token stays read-only | A defined start for step 2 and AC-01 | OQ-02, OQ-05 | M — one script, one doc section, one lab trial | The procedure names every privileged step and who runs it | untried on the lab |
| R-03 | F-03, F-22 | Specify the firewall mechanism before any rule (amended in r2): shipped by Butane, idempotent, two stages — host rules and a pre-created chain before Docker, re-application after every Docker start — required by the Compose unit; original-destination matching; assert the chain exists; lab addresses in the rendered Ignition so the host rules are complete on first boot | No open window at boot; AC-09 has a mechanism | SP-06 … SP-08 | M to L — two stages, three chains, a variables source, two tests (S2 § 3.3) | The design names load order, persistence and failure behaviour | behaviour on FCOS unverified |
| R-04 | F-04 | Get the lab addressing plan from the owner; keep it in an untracked variables file with a tracked example | Rules and tests become concrete | OQ-06 | S — owner input and one example file | Allowed and forbidden sources named; no real address tracked | none |
| R-05 | F-05 | Define AC-05: one fixed allowed address; a second container on the mail network as the unauthorised client; expect an SMTP refusal; the allowed path shown working in the same run | AC-05 proves relay protection | R-10, R-11 | S — one test design | The test fails if Postfix is down | Postfix specifics unverified |
| R-06 | F-06 | Get the owner's answers on the relay, the mailbox and Checkmk; write down what each fallback proves | AC-04 and AC-08 become plannable | OQ-03, OQ-04 | S — owner input | Each fallback states its limit | none |
| R-07 | F-07 | Define the smallest AC-08 route: an active HTTPS check that alerts on a stopped proxy; agent and container checks as an addition after the spike | AC-08 has a route that does not depend on unverified facts | R-06, R-08, OQ-25 | M — depends on the instance | The route is written before the monitoring step starts | key facts unverified |
| R-08 | F-03, F-07, F-08, F-09 | Run an early spike VM and record the answers: installed packages before and after the override, firewall backend and chain, Python, IPv6, the log collector's mount under SELinux, whether the Compose plugin comes as a dependency | Assumptions A-02 … A-04 and OQ-08, 09, 13, 15 become facts | R-02; the implementation gate | M — one throwaway VM | Each question has a command and a recorded answer; spike notes are not acceptance evidence | — |
| R-09 | F-09 | Pin the FCOS stream and version and state the Docker CE version policy; ship the repository file and signing key with Butane; gate the Compose unit on the booted engine being Docker CE (amended in r2) | Repeatable first boot | R-08 | S to M — Butane only | Two builds on different days give the same package versions, or the documentation states that they may differ and the evidence records what was installed | the pin syntax for a layered package is unverified |
| R-10 | F-10 | Complete the network table: internal flag and egress per network; an egress network for Postfix only; egress limited to the relay port | Isolation that can be tested | R-04 | S — design | Every network has a stated exit or none | none |
| R-11 | F-11 | Choose the Postfix image and the WordPress mail integration by stated criteria; verify with `upstream-claim-verify` | Mail path can be designed | — | S — a comparison and a decision | The choice cites the image's own documentation | none |
| R-12 | F-12, F-13, F-21 | Adopt the refined order (D-33): spike, scaffold, host and firewall against a stub, web, mail, logs, monitoring, restart and rebuild, release gate; EXTRA layers after every MUST HAVE row | No check is marked passed against nothing | D-33 confirmed | S — plan text | Each step names its exit and the checks it may claim | none |
| R-13 | F-08 | After the spike, decide the log route and record any SELinux exception with its reason next to the configuration | AC-06 has a route inside the rules | R-08 | M — one decision and a trial | The decision cites the spike output | depends on unverified behaviour |
| R-14 | F-15, F-21, F-23 | One owner pass over every proposal in decision-log § 3 (widened in r2 from D-20 … D-25 and D-27): confirm, amend or reject each | Rules and decisions agree before anything is public; R-01 and R-12 stop depending on their own approval | — | S — owner decisions only | Each line has a recorded status | none |
| R-15 | F-16 | Before publication: decide on diagrams 01–04 (regenerate footers, annotate, or hold back), the toolkit's third-party skills, the licence and the commit address; note the pre-approved `gh` commands in local settings | Nothing stale or undecided is published | — | S to M — owner decisions; a diagram regeneration if chosen | The steward's scan and gate list show each item settled | none |
| R-16 (merged into R-01 in r2) | F-18 | One evidence template per check: date, VM build, versions, command, output; text next to every screenshot; AC-03 trial defined from the default lifetime | Evidence that can be re-run and compared | — | S — one template | Every AC names its evidence file | none |
| R-17 | F-19 | `scripts/validate.sh` runs each static gate from a pinned container; update the gate block in the test rule in the same change | One command, same result locally and in CI | scaffold step | S — one script | The script exits non-zero on a broken input | none |
| R-18 | F-20 | Document the secrets channel: copy over SSH after first boot into a root-owned directory with restrictive modes; tracked example file with key names only | Secrets handling that can be followed and restored | — | S — one doc section | The example file lists every secret name | none |
| R-19 | F-17 | A check on host update state, in the OPTIONAL tier | A stuck update becomes visible | R-07 | S — one local check, if the state is observable | the check reports a held update in a trial | behaviour unverified |
| R-20 (added in r2) | F-24 | Answer in the spike whether containers are SELinux-confined under Docker CE; ship the daemon setting in Butane if needed; record the daemon's security options in the AC-01 evidence | The SELinux boundary is a fact, not an assumption | R-08 | S — one spike question, one setting, one evidence line | AC-01 evidence shows host mode and daemon security options | the risk itself is unverified |
| R-21 (added in r2) | methodology M-06 | Create a root `CLAUDE.md` with the scaffold: the gate commands with a healthy output, the conventions, the things agents get wrong | Sessions share one short context file | scaffold step | S — one page | it exists, is about a page, lists the gate commands | none |

*Note of 2026-11-16 (DOC-1).* A root `CLAUDE.md` and a root `AGENTS.md` exist since 2026-11-16, added outside this package ([source-register.md](source-register.md) SR-28, SR-29). R-21 stays as recommended for what the scaffold adds, the gate commands and their healthy output. No finding, severity, score or rank changed.

## 7. Scoring

Criteria and weights: **A** alignment with confirmed intent and requirements (25) · **B** reduction of evidenced risk or architectural failure (25) · **C** ability to unblock dependent work (20) · **D** contribution to verifiable implementation readiness (20) · **E** proportionality of benefit to estimated effort (10). Each is scored 0–5. Priority = Σ(weight × score) ÷ 5, range 0–100.

The score is a decision aid, not a prediction. Where a criterion rests on an unverified fact it is marked **?**, is not scored zero, and the row shows an interval over the possible values of that criterion; the weights are not renormalised and such a row's place in the order is provisional.

| ID | A | B | C | D | E | Score | Confidence | One-line justifications (A · B · C · D · E) |
|---|---|---|---|---|---|---|---|---|
| R-04 | 5 | 4 | 5 | 5 | 4 | **93** | High | host firewall is a reviewer decision · no rule or test is concrete without it · unblocks rules, tests, TLS names · makes AC-02 and AC-07 runnable · owner input only |
| R-02 | 5 | 5 | 5 | 4 | 3 | **92** | High | "FCOS VM on Proxmox" is requirement row 1 · removes an access assumption that breaks a rule · every later step needs a VM · defines the AC-01 start · needs a lab trial |
| R-03 | 5 | 5 | 4 | 5 | 3 | **92** | Medium | mandatory layer · closes a boot-time gap and a wrong-match risk shown in upstream docs · AC-07 and AC-09 depend on it · gives both a mechanism · a unit, rules and tests |
| R-06 | 5 | 4 | 5 | 4 | 4 | **89** | High | mail and monitoring are MUST HAVE · two checks cannot pass otherwise · unblocks steps 3 and 4 · decides what can be claimed · owner input only |
| R-08 | 4 | 5 | 5 | 4 | 3 | **87** | High | serves reproducibility, not a row directly · turns four assumptions into facts · five questions wait on it · later designs cite real output · one throwaway VM |
| R-14 | 5 | 3 | 5 | 4 | 5 | **86** | High | approval discipline is an owner requirement · avoids public rework · approval waits on it · settles the IDs tests use · minutes of owner time |
| R-05 | 5 | 4 | 2 | 5 | 5 | **83** | Medium | AC-05 is load-bearing · prevents a pass for the wrong reason · unblocks one check · defines its proof exactly · one design note |
| R-01 | 5 | 3 | 2 | 5 | 5 | **78** | High | anchors a reviewer decision · closes a coverage gap · little depends on it · every row gets proof · one table |
| R-12 | 4 | 3 | 4 | 4 | 5 | **77** | High | keeps MUST before EXTRA · prevents empty passes · orders all later work · exits become checkable · plan text only |
| R-15 | 5 | 4 | 3 | 3 | 4 | **77** | High | public hygiene is an owner requirement · removes a public contradiction and licence risk · the publication gate waits on it · little for build readiness · mostly decisions |
| R-11 | 4 | 3 | 4 | 3 | 4 | **71** | Medium | SMTP container is a requirement row · removes an unknown, not a fault · mail design and tests wait on it · moderate · a comparison |
| R-16 | 4 | 2 | 2 | 5 | 5 | **68** | High | "prove it with evidence" · low risk today · little depends on it · directly raises verifiability · one template |
| R-09 | 4 | 3 | 2 | 4 | 4 | **67** | Medium | reproducibility is a principle · rebuild drift is plausible, not yet seen · little depends on it · sharpens AC-01 · Butane only |
| R-10 | 4 | 3 | 3 | 3 | 4 | **67** | Medium | isolation is EXTRA, the table is base design · resolves an inconsistency · relay test design uses it · moderate · design text |
| R-17 | 3 | 2 | 3 | 4 | 5 | **63** | High | process, not a requirement · low risk · CI and every later change use it · one-command gate · one script |
| R-18 | 4 | 3 | 2 | 3 | 4 | **63** | High | secrets out of git is not optional · removes an ambiguity · little depends on it · moderate · one section |
| R-07 | 4 | ? | 3 | 4 | 3 | **54–79** | Low | monitoring is MUST HAVE · risk size rests on unverified Checkmk facts · the monitoring step waits on it · gives AC-08 a route · depends on the instance |
| R-13 | 4 | ? | 3 | 3 | 3 | **50–75** | Low | searchable logs is MUST HAVE · rests on unverified SELinux behaviour · log step waits on it · moderate · a decision and a trial |
| R-19 | 2 | ? | 0 | 2 | 3 | **24–49** | Low | OPTIONAL tier · rests on unverified updater behaviour · nothing depends on it · small · small |

## 8. Classification and order

### Mandatory blockers

An evidenced security or feasibility blocker, or a decision only the owner can make. None is deprioritised for its benefit-to-effort score.

| Blocker | Why it is mandatory | Blocks |
|---|---|---|
| R-14 owner pass over the proposals | approval cannot be given on unconfirmed rules | the implementation gate |
| R-15 publication hygiene | a public contradiction and undecided publication questions | the publication gate |
| R-02 VM provisioning path | feasibility: no VM without it; touches the lab-access rule | step 2, AC-01 |
| R-04 addressing plan | security: the mandatory layer cannot be written or tested | AC-02, AC-07 |
| R-06 relay and Checkmk answers | feasibility: two MUST HAVE checks | AC-04, AC-08 |
| R-03 firewall mechanism | security: boot-time gap and wrong-match risk | AC-07, AC-09 |
| R-05 relay test definition | security: a load-bearing test that could pass wrongly | AC-05 |

### Ranked improvements

By initial score: R-08 (87), R-01 (78), R-12 (77), R-11 (71), R-16 (68), R-09 (67), R-10 (67), R-17 (63), R-18 (63), then the provisional rows R-07 (54–79) and R-13 (50–75).

### Optional enhancements

R-19 (24–49).

### Priority rank is not execution order

Priority says what matters most; execution order says what can be done first. They differ here because the highest-priority items wait on the owner while several lower ones can be written now.

| Order | Recommendation | Why here |
|---|---|---|
| 1 | R-14, R-15 | owner decisions; they gate approval and publication and need no lab |
| 2 | R-04, R-06, and the owner's part of R-02 | owner input; everything concrete waits on it |
| 3 | R-01, R-12, R-16, R-05, R-10, R-11, R-18 | documents and designs that can be written before any VM exists |
| 4 | R-02 (trial), R-08 | the first contact with the lab, after the implementation gate |
| 5 | R-03, R-09, R-13, R-17 | depend on the spike or belong to the scaffold |
| 6 | R-07 | depends on the Checkmk answer and the spike |
| 7 | R-19 | OPTIONAL tier |

## 9. Independent review and re-ranking

The plan-critic session reviewed r1 of this document together with both drafts: [delegation/s3-critic-review.md](delegation/s3-critic-review.md). It wrote none of them. Its limits are its own: it could not open the upstream sources and did not re-observe F-16. The orchestrator reviewed the critic's output in turn; no session was the sole reviewer of its own work.

### 9.1 Response to the challenges

| Challenge (critic's section) | Response | Effect |
|---|---|---|
| "No finding is Critical" confirmed; 12 findings upheld (§ 2) | — | none |
| F-03: a unit after Docker does not close the boot window; risk (c) is latent; the FCOS remark argues from silence; host ports are not covered | **Accepted** in full | correction and R-03 amended; wording fixed; F-22 added |
| F-07: High is unsupported, because the finding's own correction gives AC-08 a route | **Accepted** | severity Medium; R-07 stays off the blocker list |
| F-08: a third route exists | **Accepted** | wording |
| F-09: gating on the stamp is insufficient | **Accepted**; confirmed against SR-20 L38–39 | correction and R-09 amended |
| F-04, F-10, F-11: line references | **Accepted** | L93–97, L81–87, L56 |
| F-14: inexact count; two proofs missed | **Accepted** | finding rewritten |
| F-16: local settings are not a public artifact; `docs/.prepare/` omitted | **Accepted**; both named repositories checked and found public | finding rewritten |
| F-18: title overstated; the within-a-day claim rests on an unverified renewal point | **Accepted** | title and text |
| F-20: Low understates it | **Accepted** | severity Medium |
| F-21: the real conflict is the tier line through AC-07 | **Accepted** | reframed, severity Medium, OQ-27 |
| Twelve disputed scores (§ 3) | **All twelve accepted.** Four removed a benefit counted under two criteria; three aligned the A score with rows scored on the same ground; R-08's B was a spike's uncertainty reduction counted as risk reduction | § 9.2 |
| R-03's B could return to 5 once the action closes the window | **Not taken**: the amended action rests on unverified behaviour (SP-07) | B stays 4 |
| R-01 and R-16 overlap | **Accepted** | R-16 merged into R-01 |
| R-14 is too narrow; R-01 and R-12 depend on their own approval | **Accepted** | R-14 covers all of decision-log § 3 |
| "Minutes of owner time" is a figure no source gives | **Accepted** | removed |
| Execution order: the Butane invocation precedes the spike; specify before the spike and confirm after; D-32 and D-33 in the owner's first pass | **Accepted** | § 9.3 |
| AC-03 must run after the last proxy change; AC-07 in full precedes AC-09; AC-02 in full needs the logs name | **Accepted** | [implementation-plan.md](implementation-plan.md) § 3 |
| The blocker list is not closed under its own dependencies (R-03 on R-08; R-05 on R-10, R-11) | **Accepted as a note**, not as new blockers: a prerequisite is not an owner decision or an evidenced failure. It takes its blocker's place in the execution order | § 9.3 |
| Missed findings K-01 … K-12 | Classed: six became F-22 … F-27; K-06 is folded into F-07 and OQ-30; K-08, K-10, K-11, K-12 are recorded after F-27; K-09 into F-16 | § 4 |
| Review points on S1 (nine) and S2 (eight) and the twelve cross-draft contradictions | Taken into the integration | [implementation-plan.md](implementation-plan.md) § 7, § 8 |

### 9.2 Re-ranking

Final scores apply the twelve accepted changes. R-20 and R-21 are new and were not seen by the critic; their scores are the orchestrator's alone and are marked so.

| Final rank | ID | Initial rank | Initial | Final | Reason for the change |
|---|---|---|---|---|---|
| 1 | R-04 | 1 | 93 | **88** | B 4→3: "nothing is concrete without it" was already scored under C and D |
| 2 | R-02 | 2 | 92 | **87** | B 5→4: the access risk is hypothetical and already barred by a rule |
| 2 | R-03 | 2 | 92 | **87** | B 5→4: as first written the action did not close the boot window; amended, but unverified |
| 4 | R-14 | 6 | 86 | **86** | score unchanged; scope widened; rises because others fell |
| 5 | R-06 | 4 | 89 | **84** | B 4→3: repeated the unblocking benefit scored under C |
| 6 | R-08 | 5 | 87 | **82** | B 5→4: a spike reduces uncertainty; the risk reductions belong to R-03, R-07, R-09, R-13 |
| 7 | R-15 | 9 | 77 | **81** | C 3→4: it gates a phase, like R-14 |
| 8 | R-01 | 8 | 78 | **78** | unchanged; absorbs R-16 |
| 8 | R-05 | 7 | 83 | **78** | B 4→3: one benefit, a valid test, was scored under B and D |
| 10 | R-12 | 9 | 77 | **77** | unchanged |
| 11 | R-11 | 11 | 71 | **76** | A 4→5: a requirement row, like R-02 and R-06 |
| 12 | R-09 | 13 | 67 | **67** | unchanged; action amended |
| 12 | R-10 | 13 | 67 | **67** | unchanged |
| 12 | R-17 | 15 | 63 | **67** | C 3→4: the spike needs its Butane invocation |
| 12 | R-18 | 15 | 63 | **67** | C 2→3: the first credential and the stack unit wait on it |
| provisional | R-20 | — | — | **59–84** | new; A 5 · B ? · C 2 · D 4 · E 5; orchestrator's score only |
| provisional | R-07 | provisional | 54–79 | **59–84** | A 4→5 |
| provisional | R-13 | provisional | 50–75 | **55–80** | A 4→5 |
| 19 | R-21 | — | — | **50** | new; A 3 · B 1 · C 2 · D 3 · E 5; orchestrator's score only |
| optional | R-19 | optional | 24–49 | **24–49** | unchanged |
| — | R-16 | 12 | 68 | merged | into R-01 |

**Did the review confirm the initial order?** Partly, and it says so itself.

- The **first three places are confirmed** and held under every weight and score change the critic tested.
- **Below them the order changed**: R-14 rose to fourth, R-08 left the top five. The critic's sensitivity test showed fifth place flipping between R-08 and R-14 on a one-point margin in three of ten weight cases. From fourth to eleventh place neighbours differ by three points or fewer, which is less than one step on a criterion. **The order between neighbours in that band is not meaningful and should not be read as a decision.**
- The **blocker list is confirmed unchanged**: R-14, R-15, R-02, R-04, R-06, R-03, R-05. It is classed by kind, not by score, so no score change could alter it.
- The **execution order is confirmed with three corrections** (§ 9.3). The critic's own conclusion holds: the swaps in the ranking change nothing in what is done first, because the rows that swap are either blockers already or fixed in the order by a dependency.

### 9.3 Execution order after the review

This replaces the order table of § 8.

| Order | Recommendation | Why here |
|---|---|---|
| 1 | R-14 (all of decision-log § 3), R-15 | owner decisions; they gate approval and publication and need no lab |
| 2 | R-04, R-06, the owner's part of R-02 | owner input; everything concrete waits on it |
| 3 | R-01 (with R-16), R-12, R-10, R-11, then R-05; R-18; and the **specifications** of R-03, R-07, R-09 with their spike-conditional branches | documents and designs that need no VM. The two drafts already contain most of them |
| 4 | the Butane invocation of R-17, then R-02 (trial) together with R-08 and R-20 | the first contact with the lab, after the implementation gate; the spike VM is created by the provisioning procedure, so these are one event |
| 5 | R-13 and the daemon settings, **before** R-09's Butane; then the confirmation of R-03, R-09; the rest of R-17; R-21 | the log driver and the SELinux setting are daemon configuration that Ignition writes once |
| 6 | R-07 confirmation | the floor needs only the Checkmk answer; the agent route needs the spike |
| 7 | R-19 | OPTIONAL tier |
