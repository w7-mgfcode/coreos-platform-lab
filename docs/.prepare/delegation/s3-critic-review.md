# S3 — Critic Review — CoreOS Platform Lab

| Field | Value |
|---|---|
| Document ID | S3 |
| Title | Independent Critic Review of the Plan Review and the Two Drafts |
| Revision | r1 |
| Status | draft |
| Owner | plan-critic |
| Last updated | 2026-11-14 |
| Core-context revision used | r1 (`docs-baseline-r1`) |
| Dependencies | [plan-review.md](../plan-review.md) r1, [s1-platform-delivery.md](s1-platform-delivery.md) r1, [s2-security-verification.md](s2-security-verification.md) r1, the five core documents r1, [methodology-adaptation.md](../methodology-adaptation.md) r1, [docs/architecture.md](../../architecture.md) and `.claude/rules/` (both read 2026-11-14) |
| Change summary | r1: first review |

## 1. Scope and method

**Nothing is built or tested; this review reads documents only.** It covers the 21 findings and 19 recommendations of plan-review r1, its scores and execution order, and the drafts S1 and S2. I wrote none of them.

**Result in brief.**

1. No finding is rejected: 12 are upheld and 9 adjusted. Three severities should change (F-07 down, F-20 and F-21 up). "No finding is Critical" is confirmed.
2. All 19 score sums are arithmetically correct. Twelve single scores are disputed, four of them for counting one benefit twice.
3. R-04, R-02 and R-03 stay in the top five under every change tested. **The top-five set does not hold**: fifth place flips between R-08 and R-14 on a one-point margin.
4. The blocker list is not derived from scores, so no weight or score change can alter it. Its seven members are confirmed, with one scope fix (R-14).
5. The execution order of plan-review § 8 is confirmed except for three corrections (§ 5 rows 3, 5, 6).
6. The two drafts contradict each other in twelve places (§ 9). The four that decide the build are the network form, the firewall unit against Docker, the log route, and how lab values reach the VM.

**Conventions.** Verdicts are *uphold*, *adjust*, *reject*. Unless tagged, a statement is a fact about the cited document and can be checked at the reference given. **[P]** marks my proposal, **[OQ]** a question for the owner, **[opinion]** a challenge that rests on general knowledge of a tool with no source in the register or the repository.

**Limits.**
- SR-20, SR-22, SR-24 and SR-25 are not in the repository. I could not check any upstream quote; "not checkable" below means exactly that.
- SR-13, SR-14 and SR-16 are untracked and were not read. No diagram was viewed and no settings file was opened, so F-16's observations are taken as stated.
- Architecture line numbers were checked against the file as read on 2026-11-14.
- The arithmetic in § 6 and § 11 was done by hand; no command was run.

## 2. Challenges to findings

Strengths S-1 … S-9: all nine line references are exact.

| ID | Verdict | Reference | Challenge and reason |
|---|---|---|---|
| F-01 | uphold | exact (SR-01 L25, L141–150) | High fits the scale only through "would pass for the wrong reason": AC-01 as written passes on the Moby engine. The finding should say so |
| F-02 | uphold | L41–47 exact; SR-22 not checkable | Supported. The risk "a session could assume API access" is hypothetical and already barred by SR-07 "Lab access"; that bears on R-02's B score, not on the severity |
| F-03 | adjust | L101, L94–95 exact; SR-24 not checkable | (1) The correction "runs after Docker and is required by the Compose unit" does not close gap (b), which the finding itself names: both drafts hold that the daemon starts containers with a restart policy before any later unit runs (S1 § 5; S2 § 3.3 "Why two stages"), both unverified. (2) Risk (c) is latent: with a 443-to-443 mapping a plain port match still matches (S2 § 3.2 point 2). (3) "§ 3 lists none" argues from the architecture's silence, not from evidence about FCOS. (4) The host's own ports before the rules load are not covered (K-05). High stands |
| F-04 | uphold | rows are L93–97; L92 is the table separator | High stands. It is OQ-06 restated: a public architecture could never hold the plan. "Allowed and forbidden source" is too coarse (K-07) |
| F-05 | uphold | exact | Nothing wrong. S2 § 10.5 implements the correction |
| F-06 | uphold | exact | Nothing wrong. Overlaps F-07 on Checkmk |
| F-07 | adjust | L111 exact | The severity contradicts the finding's own correction, which says an active HTTPS check alone satisfies the row as written. Then "AC-08 has no defined route" does not hold and the High test (a MUST HAVE check cannot be passed) is not met. With every key fact unverified and confidence "Low to Medium", High is unsupported: **Medium**. If High is kept, R-07 belongs on the blocker list. What is at risk is the requirement row's agent (L31), not AC-08 (S1 C-3). "Does not depend on unverified facts" is also overstated: the smallest route needs the lab root in Checkmk's trust store, unverified (S2 § 6.2 step 6) |
| F-08 | adjust | exact | "Each candidate meets SELinux" assumes two candidates. S2 § 9.2 rank 1 (shared log volumes) needs no host mount. Medium stands |
| F-09 | adjust | L44, L45 and SR-06 exact; SR-20 not checkable | The correction "gate the Compose unit on the install stamp" is insufficient: the stamp is written before the reboot and the new engine appears after it (S1 § 3.4, P-06). Gate on the booted engine |
| F-10 | uphold | the table is L81–87; L77–79 are the figure and its links | Nothing else wrong. The tier of the corrective egress rule is not stated; S2 classes H9 and H10 as EXTRA |
| F-11 | uphold | **wrong line**: "SMTP integration" is L56 (WordPress); L59 is the Alloy row | Substance correct |
| F-12 | uphold | exact | Nothing wrong |
| F-13 | uphold | exact (L134–136) | Nothing wrong. The spike clause in the correction belongs to R-08 |
| F-14 | adjust | L26, L33, L115 exact | The count is inexact: two table rows (L26, L33) carry three proof items, and secrets has **no** proof in § 2 at all (L33 names restore and update only). Missed: the "HTTP backend" proof of L27 (S2 § 10.0 covers it) and the agent of L31 (K-06) |
| F-15 | uphold | L35–37 exact; the rule side checked in SR-03, SR-04, SR-06, SR-08; SR-13 not read | Sound. Its recommendation is too narrow (R-14, § 3) |
| F-16 | adjust | not re-checked | Five unrelated items under one severity. `settings.local.json` is untracked, so it is not a public artifact. The finding omits `docs/.prepare/` itself, which is tracked and will be public (K-09) |
| F-17 | uphold | exact | Low severity and Low confidence agree. Nothing wrong |
| F-18 | adjust | SR-08 table | Title overstated. SR-08 defines AC-03's proof ("Caddy log and the new certificate's validity dates") and AC-08's ("Checkmk state before and after"). Only AC-06 is screenshot-only; none is "not at all". The within-a-day claim depends on the renewal point, unverified (S2 § 6.1) |
| F-19 | uphold | exact | Nothing wrong |
| F-20 | adjust | L47, L115 exact | Low ("polish") understates it. OQ-16 blocks M2; S1 gates the stack unit on the secrets (S1 § 5); S2 § 7.3 leaves ownership and SELinux label unverified, with a possible rule exception (S2 § 9.4 row 1). Same class as F-11: **Medium** |
| F-21 | adjust | L101 exact | The framing misses the real conflict. AC-07 (MUST HAVE, L147) demands failure "from an internal, unauthorised container", so part of the EXTRA separation row sits inside a MUST HAVE check (S2 § 4.3). The drafts split on it (§ 9 row 1) and six re-runs are at stake: **Medium**. "Correction: none" leaves the owner's decision unasked |

## 3. Challenges to scores

**Nothing wrong with:** the arithmetic of all 19 rows; the formula's 0–100 range; the `?` convention, which is applied consistently to rows whose *risk*, not whose remedy, is unverified (R-07, R-13, R-19). The weights are the owner's (methodology-adaptation "Not claimed") and are not challenged.

| ID | Initial | Verdict | Criterion challenged and reason | Disputed |
|---|---|---|---|---|
| R-01 | 78 | uphold | Depends on "D-32 confirmed" while its own action defines AC-01 per D-32: it depends on its own approval, and D-32 is outside R-14's pass | — |
| R-02 | 92 | adjust | B=5 rests on a hypothetical ("could assume") that SR-07 already forbids. The feasibility benefit is scored under C=5 | B 5→4 |
| R-03 | 92 | adjust | B=5 "closes a boot-time gap": as written it does not (F-03, challenge 1). Effort basis "one unit, one rule file, two tests" is below S2 § 3.3: two stages, three chains, a variables file | B 5→4 |
| R-04 | 93 | adjust | B=4 "no rule or test is concrete without it" is an unblocking statement. The same benefit is scored again as C=5 and D=5 | B 4→3 |
| R-05 | 83 | adjust | B=4 "prevents a pass for the wrong reason" and D=5 "defines its proof exactly" are one benefit: a valid test | B 4→3 |
| R-06 | 89 | adjust | B=4 "two checks cannot pass otherwise" repeats C=5 "unblocks steps 3 and 4" | B 4→3 |
| R-07 | 54–79 | adjust | A=4 for "monitoring is MUST HAVE"; R-02 and R-06 get A=5 on the same ground. Expected outcome overstated (F-07) | A 4→5 |
| R-08 | 87 | adjust | B=5 is unsupported. A spike reduces uncertainty, not risk, and the risk reduction for F-03, F-07, F-08, F-09 is already claimed by R-03, R-07, R-13, R-09. The counts do not match the row: "A-02 … A-04" is three assumptions, not "four"; the row names four questions, the justification "five", the action six items. Effort "one throwaway VM" predates the drafts' twenty spike questions (§ 9 row 8) | B 5→4 |
| R-09 | 67 | uphold | Score stands. Action: see F-09. The criterion "two builds on the same day give the same package versions" is also met by an unpinned install; the finding concerns different days (S1 § 3.3) | — |
| R-10 | 67 | uphold | Score stands. "Uncertainty: none" is contradicted by S2 § 5 (SQ-7, SQ-8). The dependency on R-04 is weak: Compose subnets are internal values (S1 § 6.2) | — |
| R-11 | 71 | adjust | A=4 for "a requirement row": same inconsistency as R-07. Nothing exists to verify against: no image documentation is in the register (S1 § 1, F-11 row) | A 4→5 |
| R-12 | 77 | uphold | Same self-dependency as R-01 (D-33). "EXTRA after MUST HAVE" restates SR-03 "Order of work" | — |
| R-13 | 50–75 | adjust | A=4: same inconsistency. Its decision must precede R-09's Butane (§ 5 row 7) | A 4→5 |
| R-14 | 86 | uphold | Score stands only if the scope widens. It covers D-20 … D-25 and D-27; OQ-07 asks about D-20 … D-33; R-01 and R-12 depend on D-32 and D-33; S2 E3 rests on D-31. "Minutes of owner time" is a time figure no source gives (manifest § 2 rule 5; OQ-01) | — |
| R-15 | 77 | adjust | C=3 for "the publication gate waits on it" against R-14's C=5 for "approval waits on it". Both gate a phase, and SR-04 requires an issue number on every commit, so all committed work waits on publication | C 3→4 |
| R-16 | 68 | uphold | Overlaps R-01 (§ 4). No dependency is listed, yet OQ-24 decides how much the evidence must carry alone | — |
| R-17 | 63 | adjust | C=3: the spike needs a rendered Ignition file and the workstation has no Butane (core-context § 5; S1 § 7.2, P-15), so R-08 depends on part of it | C 3→4 |
| R-18 | 63 | adjust | C=2 "little depends on it": the first service with a credential and S1's stack unit depend on it. "Uncertainty: none" is contradicted by S2 SQ-9 | C 2→3 |
| R-19 | 24–49 | uphold | No acceptance criterion and no effort basis are given | — |

Effort bases: stated for 17 rows. R-07 ("depends on the instance") and R-19 (none) state no basis.

## 4. Overlaps and double counting

1. **R-08 against R-03, R-07, R-09, R-13.** F-03, F-07, F-08 and F-09 are each mapped to R-08 and to their own remedy, and both rows score the risk reduction. This is the largest double count, and it decides fifth place (§ 6).
2. **R-01 and R-16.** Both produce "every proof has a named place". S2 § 10.0 delivers both in one section. Merge candidate [P].
3. **Inside one row.** R-04 (B, C, D), R-06 (B, C) and R-05 (B, D) each score one benefit under two or three criteria (§ 3).
4. **A recommendation and the decision it adopts.** R-12 is D-33, R-01 is partly D-32, and R-14 asks the owner about such proposals. One owner pass should carry all three.
5. **Owner inputs restated.** R-04 (OQ-06), R-06 (OQ-03, OQ-04), R-14 (OQ-07), R-15 (OQ-17, 21, 22, 23) and the owner's part of R-02 (OQ-02, OQ-05) restate open-questions § 1. They hold three of the top five places and five of the seven blocker slots. This is not wrong, but for these rows the score adds nothing to what the blocker rule already fixes.
6. **Effort counted twice.** R-02's lab trial and R-08's throwaway VM are one event: the spike VM is created by the provisioning procedure (S1 § 7.1, SQ-11).
7. **Criterion E** is benefit over effort, so each row's benefit enters once more at weight 10. Structural, small [opinion].
8. **No two recommendations are duplicates.** R-10 and R-05 share the fixed `mail` address, R-19 and R-07 the agent; these are proper dependencies.

## 5. Sequencing check

| # | Point in plan-review § 8 | Verdict | Evidence |
|---|---|---|---|
| 1 | Order 1: R-14, R-15 | correct | Neither needs the lab. R-14's scope: § 3 |
| 2 | Order 2: R-04, R-06, owner's part of R-02 | correct | — |
| 3 | Order 3: R-01 and R-12 | **error** | Both depend on D-32 or D-33 "confirmed"; no recommendation obtains that. Fix: widen R-14 [P] |
| 4 | Order 3: R-05 with R-10, R-11 | acceptable | R-05 lists both as dependencies; state the inner order |
| 5 | Order 4 R-08 before order 5 R-17 | **error** | The spike needs Ignition rendered by a pinned Butane (core-context § 5; S1 § 7.2, P-15). That part of R-17 precedes R-08 |
| 6 | Order 5 R-03, R-09; order 6 R-07 | **error of kind** | "Specify" and "confirm" are merged. S2 § 3, S1 § 3 and S2 § 10.8 already specify with spike-conditional branches. Specify at order 3; confirm after the spike. R-07's floor needs R-06 only |
| 7 | Order 5: R-13 and R-09 unordered | gap | The log driver is daemon configuration that Ignition writes once (S1 § 6.1, P-16). The same holds for S2's daemon settings (SQ-5, SQ-6). All precede the host step |
| 8 | R-08's dependencies | incomplete | Omits OQ-06 (the spike VM needs an address; S2 SQ-7 needs a client-role source) and the Butane invocation |
| 9 | D-33 and R-12: where AC-03 runs | gap | S1 lets the trial start at D5, but D7 changes the `Caddyfile` and S2 § 10.3 needs Caddy uninterrupted. SR-08: a check is re-run when a relevant change lands after it passed. Place AC-03 after the last proxy change and before AC-09 [P] |
| 10 | D-33: "restart and rebuild, then the release gate" | open | Which VM carries the release evidence (K-04) |
| 11 | Order 7: R-19; EXTRA after MUST HAVE | correct | SR-03 "Order of work" |

## 6. Sensitivity test

**Method.** One change at a time. A weight change of ±5 moves each row by ± its score on that criterion. The weights are not renormalised; renormalising multiplies every row by the same factor and leaves the order unchanged. The table shows the seven highest rows. No row below R-05 comes closer than six points to fifth place in any weight case, R-07's upper bound included.

**Weights.**

| Change | R-04 | R-02 | R-03 | R-06 | R-08 | R-14 | R-05 | Top-five set |
|---|---|---|---|---|---|---|---|---|
| initial | 93 | 92 | 92 | 89 | 87 | 86 | 83 | R-04, R-02, R-03, R-06, R-08 |
| A +5 | 98 | 97 | 97 | 94 | 91 | 91 | 88 | fifth place tied: R-08 = R-14 |
| A −5 | 88 | 87 | 87 | 84 | 83 | 81 | 78 | unchanged |
| B +5 | 97 | 97 | 97 | 93 | 92 | 89 | 87 | unchanged |
| B −5 | 89 | 87 | 87 | 85 | 82 | 83 | 79 | **changed**: R-14 replaces R-08 |
| C +5 | 98 | 97 | 96 | 94 | 92 | 91 | 85 | unchanged |
| C −5 | 88 | 87 | 88 | 84 | 82 | 81 | 81 | unchanged |
| D +5 | 98 | 96 | 97 | 93 | 91 | 90 | 88 | unchanged |
| D −5 | 88 | 88 | 87 | 85 | 83 | 82 | 78 | unchanged |
| E +5 | 97 | 95 | 95 | 93 | 90 | 91 | 88 | **changed**: R-14 replaces R-08 |
| E −5 | 89 | 89 | 89 | 85 | 84 | 81 | 78 | unchanged |

**Disputed scores** (the twelve of § 3; a score of 5 cannot rise).

| Score | −1 | +1 | Top-five set |
|---|---|---|---|
| R-02 B=5 | 87, ties R-08 | — | unchanged |
| R-03 B=5 | 87, ties R-08 | — | unchanged |
| R-04 B=4 | 88, fourth | 98 | unchanged |
| R-05 B=4 | 78 | 88 | **changed at +1**: R-05 replaces R-08 |
| R-06 B=4 | 84, sixth | 94 | **changed at −1**: R-14 replaces R-06 |
| R-08 B=5 | 82, seventh | — | **changed at −1**: R-14 replaces R-08 |
| R-07 A=4 | 49–74 | 59–84 | unchanged |
| R-11 A=4 | 66 | 76 | unchanged |
| R-13 A=4 | 45–70 | 55–80 | unchanged |
| R-15 C=3 | 73 | 81 | unchanged |
| R-17 C=3 | 59 | 67 | unchanged |
| R-18 C=2 | 59 | 67 | unchanged |

**Plain statement.**
- **Top five: the set changes.** It changes in 2 of 10 weight cases, ties in a third, and changes in 3 of the 21 score cases. Every change is at the fourth or fifth place, among R-06, R-08, R-14 and R-05, which lie within six points.
- **R-04, R-02 and R-03: always in the top five.** They are the first three in every weight case. A one-point cut to its own B score drops any one of them to fourth, never lower.
- **Blocker list: no change, by construction.** Plan-review § 8 classes blockers by kind (security, feasibility, owner-only decision), not by score. Only a classification challenge can alter it (§ 11).
- **Consequence for the plan: none.** The rows that swap are either blockers already (R-14, R-06, R-05) or fixed in the order by a dependency (R-08). The execution order does not depend on the fifth place.

## 7. Review of S1

**Against the packet: met.** Required structure present; all ten assigned findings have a status; RQ-1 … RQ-10 appear in § 7.3 and § 7.5; twelve spike questions each carry a command and a decision; 362 lines; no time estimate; no claim that anything works. **No invented fact found.** Three statements of tool behaviour lack the unverified mark (the `core` user in § 2.3; the route C claim and "host units become searchable" in § 6.1); minor.

**Sound and worth keeping:** P-06 (corrects F-09), P-14, P-15 (corrects § 5 row 5), P-16, and the conflicts C-1 … C-3, none of which the review had.

| # | Kind | Point | Evidence |
|---|---|---|---|
| a | rule | Option M1 allows the agent "over SSH with a restricted key". SR-07 "Host": SSH is "reachable from the admin network only". Not flagged | S1 § 6.3 table |
| b | rule | On the first boot the firewall unit is skipped (P-06) while the network is online. The host then has no `INPUT` rule. Not flagged (K-05) | S1 § 5 table row 1 |
| c | rule | The secrets evidence item is placed at D11 (OPTIONAL), though C-1 says the mechanism is needed from D5 and SR-03 says keeping secrets out of git is not optional | S1 § 7.5 RQ-10 |
| d | weak | SQ-09 lists a directory. Listing is not reading, the command mounts one of the two paths route A needs, and `getenforce` is not a sufficient precondition (§ 9 row 7). It can pass falsely | S1 § 7.1; S1 § 6.1 |
| e | weak | SQ-03 needs an install that names only `docker-ce`; P-04 installs both packages in one transaction. The spike needs two install variants | S1 § 7.1; § 3.2 |
| f | order | The table runs D1 before D2 while P-15 moves the Butane invocation ahead of D1. D1's needs omit it and OQ-06 | S1 § 7.3 |
| g | gap | The stack unit waits for a `.ready` marker. Nobody creates it or starts the unit afterwards, and at D4 the stub has no secrets yet must start | S1 § 5 |
| h | gap | Postfix preference (ii) builds an image on the VM. It has no registry digest (SR-07 "pinned by version or digest") and adds a package mirror that § 7.4's list of documented sources omits | S1 § 4 note 4; § 7.4 |
| i | gap | D6 feeds AC-05, but its exit condition has no refusal in it | S1 § 7.3 |

## 8. Review of S2

**Against the packet: met.** Required structure present; all thirteen assigned findings have a status; every blocked path names a test; each of the ten checks has preconditions, run, positive, negative, right-reason check, evidence file, script and "not verifiable yet"; 449 lines. The six rule lines quoted in § 9.4 are exact. **No invented fact found**; port numbers are classed as assumptions. Two untagged tool statements (the queue ID in the received headers, § 10.4; "Caddy binds a low port", § 9.1); minor. AC-05 and AC-07 are not narrowed: confirmed.

**Sound and worth keeping:** § 4.2 (attributing a block to its layer), § 4.3 (the tier conflict), § 9.1 (K-02), the right-reason checks of § 10.5 and § 10.7.

| # | Kind | Point | Evidence |
|---|---|---|---|
| a | architecture | H4 (ICMP echo, tier MUST) has no source. SR-01 L93–97 lists no ICMP, and L95 limits Checkmk to "only the ports the chosen integration needs". Not flagged | S2 § 3.2 |
| b | gap | "Fails closed" holds for published ports only. If the unit fails before applying, `INPUT` is unset too. The lab values arrive "like the secrets", after first boot, so until then the host has no `INPUT` rule; a default drop without the admin source would close the channel that delivers them | S2 § 3.3 |
| c | rule | EV-WEB writes a post and an upload to the lab. It is missing from the § 9.4 row on SR-08 "Tests are read-only" | S2 § 10.0; § 9.4 |
| d | gap | "How it is run" has no topology. `run-acceptance.sh` chains AC-02 (client role), AC-07 (up to four roles, and on the VM) and AC-05 (on the VM). E2 forbids the admin source on 443, so the admin workstation cannot run AC-02. Where the runner sits and how it reaches each role is not designed (K-07) | S2 § 10.0; § 2.1 E2 |
| e | gap | The secrets-complete marker that S1 delegates is not defined | S2 § 7.3; S1 § 5 |
| f | gap | AC-01's right-reason check, "provisioning time later than the run's start", does not say where that time is read | S2 § 10.1 |
| g | gap | Rank 1 of the log routes needs "rotation inside the volumes"; no one owns it (SR-07 "Logs") | S2 § 9.2 |
| h | proportion | AC-07 in full runs at least four times: once, after each of two restarts, and on the rebuilt VM. SR-08 requires the two restart runs. The rebuilt-VM run and the boot-window probe are S2's additions; weigh them against core-context § 13 principle 6 [P] | S2 § 10.1, § 10.7, § 10.9 |

## 9. Cross-draft contradictions

| # | Topic | S1 | S2 | Note |
|---|---|---|---|---|
| 1 | Network form and timing | Networks appear at D4–D7; `internal` flags and isolation tests come at D10 (§ 7.3, bullet after P-14) | Final form, with `internal` flags and `relay-out`, from the first Compose change; only N-C11 … N-C13 and H9, H10 wait (§ 4.3, § 5) | S1 defers to S2 here. Under S1, D10 lands after the gate checks: six re-runs (S2 § 4.3) and a breaking change (SR-06). Owner decision |
| 2 | Firewall unit against Docker | One unit after `docker.service` (§ 5, P-07) | Stage 1 before `docker.service`, stage 2 after (§ 3.3) | Decide after the spike |
| 3 | Closing the boot window | Restart policy so that the daemon starts nothing; systemd is the only starter (§ 5) | Pre-created chain first; the restart policy is a fallback that "trades away automatic restart of a crashed container" (§ 3.3) | Both unverified: S1 SQ-10, S2 SQ-2, SQ-3. Keep all three |
| 4 | First boot | Firewall unit skipped until the Docker CE engine is booted (§ 5 table) | Stage 1 always runs before Docker (§ 3.3) | K-05 |
| 5 | Lab values to the VM | Script parameters or an untracked include, rendered into Ignition (P-02) | A root-owned variables file "delivered like the secrets", over SSH after first boot (§ 3.3) | S1's route avoids § 8 row b. SR-07 bars secrets from Ignition, not addresses [P] |
| 6 | Log route | `journald` driver and Alloy's journal source; images log to standard output (§ 6.1, P-09; § 4 c3) | Rank 1: Caddy and Postfix write files into shared volumes; the journal is rank 2 and needs a narrow type or `label=disable` (§ 9.2) | S1's list has no shared-volume route. S2's rank 1 leaves five services and the host units unsearchable. P-16 applies only under S1's route |
| 7 | SELinux precondition | `getenforce` reporting Enforcing is enough for SQ-09 | An enforcing host does not mean confined containers (§ 9.1, SQ-6) | S2's SQ-6 must run before S1's SQ-09 |
| 8 | Spike identifiers | SQ-01 … SQ-12 | SQ-1 … SQ-12, other questions under the same numbers | S1 SQ-09 is the journal, S2 SQ-9 the secrets; S1 SQ-10 the restart policy, S2 SQ-10 the log mounts. Four pairs overlap (S1 06, 07, 09, 10 with S2 1, 5, 10, 3); the union is about twenty questions. Renumber on merge |
| 9 | Agent transport | Systemd socket, or SSH with a restricted key (§ 6.3) | An agent port from the Checkmk source only (H3, E7); TCP 22 from the admin source only (H2, E6) | The SSH variant also meets § 7 row a |
| 10 | When AC-02 closes | D4 and D5 (§ 7.5 RQ-4) | Both names (§ 10.2); the logs name exists from D7 | AC-02 cannot pass in full before D7 |
| 11 | Order inside D9 | Restart re-runs listed before "AC-07 in full" (§ 7.3) | AC-09 presupposes AC-07 passed in full (§ 10.9) | Take S2's order |
| 12 | Secrets evidence | At D11, OPTIONAL (§ 7.5 RQ-10) | The git-side half applies "whatever the tier" (§ 7.4) | Depends on K-01 |

**Unowned, not contradictory:** the AC-04 trigger. S1 § 6.2 hands its use to S2; S2 § 10.4 hands the trigger to S1.

**Additive, not contradictory:** the AC-01 content. S1 § 3.5 adds `docker compose version`; S2 § 10.1 adds the absent Moby package, the SELinux mode and the daemon's security options. Take the union.

**Agreements reached independently:** the boot window exists (both, unverified); one fixed WordPress address on `mail`; the partial firewall run is never claimed as AC-07; a fresh build makes a new CA (D-32); an active check is the floor for AC-08; secrets travel over SSH after first boot; no Docker socket mount.

## 10. Missed findings

Not scored. Each is a proposal for the orchestrator to class and rank.

| ID | Finding | Evidence |
|---|---|---|
| K-01 | The secrets mechanism is OPTIONAL in the scope lock and a required pattern in the security rule; the sequence needs it from the first credential | SR-03 "Scope Lock"; SR-07 "Forbidden", "Secrets handling"; S1 C-1 |
| K-02 | "SELinux stays enforcing" can hold on the host while containers run unconfined. Whether Docker CE confines them without a daemon setting is unverified, and D-02 replaces the engine FCOS ships. A security boundary with no finding and no acceptance line until S2 added one | S2 § 9.1, SQ-6 |
| K-03 | The disk-fill control has no proof and collides with the monitoring floor. SR-07 "Logs" requires rotation, retention and a disk alert together; a disk alert needs a host agent; R-07's floor has none. No acceptance row, no evidence item | SR-07 "Logs"; SR-01 L109; S1 § 6.1 last bullet; OQ-20 |
| K-04 | Which VM carries the release evidence is undecided. The rebuild makes a new VM and a new CA, evidence records the VM build, and the drafts put some checks on the first VM and AC-01, AC-02, AC-07 on the second. Option [P]: make the rebuilt VM the one on which the final acceptance run happens | SR-08 "Evidence rules"; S1 § 7.3 D9; S2 § 10.1 |
| K-05 | The host's own ports before the rules load. F-03 covers published ports only. On the first boot, and until the lab values arrive, nothing limits TCP 22 to the admin source | SR-07 "Host"; § 7 row b; § 8 row b |
| K-06 | Requirement row 8 plans "agent and active checks", and SR-01 L111 lists five check groups. AC-08 proves one alert. The rest has no owner in the test plan | SR-01 L31, L111; S1 C-3 |
| K-07 | The tests need five source roles; A-07 assumes two. The admin workstation is forbidden on 443 unless it lies in the client network. OQ-06 and R-04's criterion should ask for each role | S2 § 1 table; § 2.1 E2; core-context § 11 |
| K-08 | Layout and scope gaps: D-05 has no place for per-service configuration (S1-Q1), and SR-04 has no scope for `scripts/**` outside backup, so `scripts/validate.sh` has none | decision-log D-05; SR-04 scope table; S1 § 7.2 |
| K-09 | `docs/.prepare/` is tracked and will be public, and R-15 does not cover it. SR-19 names two other repositories of the owner; whether they are public is unknown to me. Include the directory in the pre-publication scan [OQ] | source-register SR-19; core-context § 6 row 4 |
| K-10 | Upstream evidence is second-hand throughout. Neither writer opened SR-20, SR-22, SR-24 or SR-25, and the register has no entry for Postfix, the container SELinux policy, systemd, Zincati, the Proxmox firewall, Compose or WordPress. The review's paraphrases are a single point of trust | S1 § 10; S2 § 1; S1 § 9; S2 § 11 |
| K-11 | Methodology M-06 names a "recommendation in plan-review.md" for a root `CLAUDE.md` at the scaffold. Plan-review has none | methodology-adaptation M-06 |
| K-12 | The static gates cover Butane, Compose, the Caddyfile and shell scripts. The mandatory layer's rule file has no static check [opinion: whether one is worth adding] | SR-08 "Gates" |

## 11. Proposed re-ranking

A proposal; the orchestrator re-ranks. It applies the twelve disputed scores of § 3 and nothing else. The K findings are not scored.

| Rank | ID | Initial | Proposed | Change |
|---|---|---|---|---|
| 1 | R-04 | 93 | 88 | B 4→3 |
| 2 | R-02 | 92 | 87 | B 5→4 |
| 2 | R-03 | 92 | 87 | B 5→4, back to 5 once the action closes the boot window |
| 4 | R-14 | 86 | 86 | none; scope widened to D-20 … D-33 |
| 5 | R-06 | 89 | 84 | B 4→3 |
| 6 | R-08 | 87 | 82 | B 5→4 |
| 7 | R-15 | 77 | 81 | C 3→4 |
| 8 | R-01 | 78 | 78 | none; merge with R-16 |
| 8 | R-05 | 83 | 78 | B 4→3 |
| 10 | R-12 | 77 | 77 | none |
| 11 | R-11 | 71 | 76 | A 4→5 |
| 12 | R-16 | 68 | 68 | none |
| 13 | R-09, R-10 | 67 | 67 | none; R-09's action and criterion amended |
| 13 | R-17 | 63 | 67 | C 3→4 |
| 13 | R-18 | 63 | 67 | C 2→3 |
| provisional | R-07 | 54–79 | 59–84 | A 4→5 |
| provisional | R-13 | 50–75 | 55–80 | A 4→5 |
| optional | R-19 | 24–49 | 24–49 | none |

**Does the review confirm the initial order?**
- **Priority ranking: partly.** The first three places are confirmed. Below them R-14 rises past R-06 and R-08, and R-08 leaves the top five. From fourth to eleventh place, neighbours differ by three points or fewer, which is less than one step on any of the criteria A to D; I would not defend the order between neighbours there.
- **Blocker list: confirmed.** The same seven. Three things for the orchestrator to settle: widen R-14; note that the list is not closed under its own dependency column (blocker R-03 depends on R-08, blocker R-05 on R-10 and R-11); and resolve F-07 against R-07 (§ 2).
- **Execution order: confirmed with three corrections.** The Butane part of R-17 before R-08; the specifications of R-03, R-07 and R-09 at order 3 with confirmation after the spike; D-32 and D-33 inside the owner's first pass.

**Questions for the owner** (escalated, not answered):
1. Where does the MUST HAVE part of Docker-network separation end and the EXTRA part begin (F-21, S2 § 4.3, § 9 row 1)?
2. Is the Compose secrets mechanism OPTIONAL or required from the first credential (K-01)?
3. Does the release need the agent of requirement row 8, or is AC-08's active check enough (K-06)?
4. On which VM is the release evidence taken (K-04)?
5. Can the lab supply the five source roles, and from which machine do the client-role tests run (K-07)?
6. Is `docs/.prepare/` published as it stands, including the names of other repositories (K-09)?

## 12. Completion report

| Item | Content |
|---|---|
| Session | S3, `plan-critic` |
| Baseline | `docs-baseline-r1`; plan-review r1; S1 r1; S2 r1 |
| Files created or changed | Created `docs/.prepare/delegation/s3-critic-review.md`. No other file created or changed |
| Evidence consulted | The delegation manifest; README, core-context, source-register, decision-log, open-questions (all r1); methodology-adaptation r1; `docs/architecture.md` in full; the rules `product-vision`, `security-patterns`, `test-requirements`, `versioning`, `commit-format`, `branch-naming`, `output-formatting`; plan-review r1; both drafts in full. Not consulted: the upstream sources SR-20, SR-22, SR-24, SR-25 (not in the repository); SR-13, SR-14, SR-16; the diagrams; any settings file |
| Decisions proposed | None for the decision log. Proposals to the orchestrator: nine finding adjustments including three severity changes (§ 2); twelve score changes (§ 3, § 11); a merge of R-01 with R-16; a wider R-14; three corrections to the execution order (§ 5); twelve missed findings K-01 … K-12 (§ 10) |
| Assumptions introduced | (1) "Each weight by ±5" means one weight at a time, by five points, without renormalising. (2) "Disputed scores" are the twelve disputed in § 3. (3) Line numbers are those of the files as read on 2026-11-14 |
| Open questions | Six for the owner (§ 11). For the orchestrator: whether F-07 stays High, and whether prerequisites of blockers are themselves blockers |
| Validation performed | By reading and by hand. All 19 score sums recomputed; ten weight cases and twenty-one single-score cases computed for the seven highest rows; every finding (21) and every recommendation (19) has a verdict; architecture line references checked for F-01 … F-21 and S-1 … S-9; the six rule quotations in S2 § 9.4 compared with the rules; the line counts of S1 (362) and S2 (449) confirmed; this file's length read back after writing (290 lines, under the packet's limit of roughly 350). No shell command, no git or GitHub action, no contact with the lab |
| Limitations | No upstream quotation could be checked, so every verdict on a tool-behaviour claim is a verdict on consistency, not on truth. F-16 was not re-observed. Combined changes (a weight and a score together) were not tested exhaustively. The proposed scores in § 11 are one reviewer's reading and carry the same resolution limit as the originals |
| Status | **Complete** against the packet. No blocker for this session |
