# S2 — Security and Verification Design

| Field | Value |
|---|---|
| Document ID | S2 |
| Title | Security and Verification Design (draft for integration) |
| Revision | r1 |
| Status | draft |
| Owner | security-writer |
| Last updated | 2026-11-14 |
| Core-context revision used | r1 (`docs-baseline-r1`) |
| Dependencies | [../README.md](../README.md) r1, [../core-context.md](../core-context.md) r1, [../source-register.md](../source-register.md) r1, [../decision-log.md](../decision-log.md) r1, [../open-questions.md](../open-questions.md) r1, [../plan-review.md](../plan-review.md) r1, [../../architecture.md](../../architecture.md) (read 2026-11-14), `.claude/rules/security-patterns.md`, `test-requirements.md`, `product-vision.md` |
| Change summary | r1: first draft |

## 1. Scope and inputs

**Nothing here is built or tested.** This is a design. The lab VM does not exist (core-context § 5), so no statement below reports an observation.

- **Statement classes.** Unless tagged otherwise, every design statement in §§ 2–10 is a **proposal [P]** awaiting the owner. Tags mark the exceptions: **[F]** fact with a reference · **[RD]** reviewer decision · **[OR]** owner requirement or governing rule · **[A]** assumption · **[OQ]** open question · **[C]** conflict · **[U]** unverified, followed by what would verify it.
- **Limit on upstream facts.** SR-24 and SR-25 are cited through the line references in the source register and their paraphrases in plan-review (S-4, F-03, F-18). The upstream files themselves were not opened in this session. Anything about Docker, Caddy, Postfix, Compose, SELinux or Proxmox beyond those paraphrases comes from general knowledge and is tagged [U]. Checkmk statements are all [U] (SR-26 not retrieved, OQ-25).
- **Lab values.** No lab address appears here. Rules and tests read roles from variables; the examples use documentation ranges only. Two further variables: `LAB_CA_CERT`, the root certificate's path on the test client, outside the repository; `LAB_APP_HOST` and `LAB_LOGS_HOST`, defaulting to `app.corelab.test` and `logs.corelab.test` (D-07).

| Role | Variable | Example (documentation range) |
|---|---|---|
| VM address | `LAB_VM_ADDR` | `192.0.2.10` |
| Client network, the allowed source for TCP 443 | `LAB_CLIENT_NET` | `192.0.2.0/28` |
| Forbidden source on the VM's segment, outside the client network | `LAB_FORBIDDEN_NEAR` | `192.0.2.200` |
| Forbidden source on another, routed network | `LAB_FORBIDDEN_FAR` | `203.0.113.50` |
| Admin source | `LAB_ADMIN_SRC` | `198.51.100.10` |
| Checkmk source | `LAB_CHECKMK_SRC` | `198.51.100.20` |

Address variables have no default: a script that finds one unset exits non-zero instead of guessing. The values live in one untracked file with a tracked example (R-04); whether both forbidden roles can exist is OQ-06 and A-07.

**Assigned findings.**

| Finding | Where | Status in this draft |
|---|---|---|
| F-01 Docker CE has no acceptance row | § 10.0, AC-01 | Answered: a required "Docker CE proof" block in the AC-01 evidence, with a negative line for Moby. Rests on D-32 (proposed) |
| F-03 firewall mechanism | § 3 | Answered as a design. Four of its claims wait on the spike (SQ-1 … SQ-4) |
| F-04 no addresses to test from | § 1, § 3.5, § 11 | Left open: only the owner has the plan (OQ-06). The roles the plan must supply are defined |
| F-05 undefined unauthorised client | § 8, AC-05 | Answered |
| F-06 relay, mailbox, Checkmk may not exist | § 8.4, AC-04, AC-08 | Left open (OQ-03, OQ-04). The limit of each fallback is stated |
| F-07 Checkmk on an image-based host | AC-08, § 9.3 | Partly answered: the smallest route and its security constraints. The agent route is S1's and waits on OQ-25 |
| F-08 log route meets SELinux | § 9.2 | Partly answered: candidates ranked by privilege, exceptions named. The choice waits on the spike (SQ-10) and is S1's mechanism |
| F-10 egress by intent only | § 5 | Answered as a proposal; one branch waits on SQ-7 |
| F-12 what a rebuild includes | § 6.4, AC-01 | Answered, resting on D-32 |
| F-13 firewall before anything to test | § 3.6, AC-07 | Answered: a partial run against a stub is recorded as partial, never as AC-07 |
| F-14 requirement rows without an acceptance row | § 10.0 | Answered: EV-WEB, EV-SEC, EV-UPD |
| F-18 screenshot-only evidence | § 10.0, AC-03, AC-06, AC-08 | Answered |
| F-20 secrets channel | § 7 | Answered as a proposal; ownership and label wait on SQ-9 |

**Dependencies on S1, named and not designed here:** VM creation and Ignition delivery; the Docker CE install unit and `daemon.json`; the Compose unit and its ordering; image selection (Postfix image, OQ-11); the WordPress mail integration (OQ-10); the log collection mechanism; the Checkmk agent installation; backup, restore and update procedures.

## 2. Exposure matrix

Ports other than 22, 443 and 587 are the images' usual defaults [A]; the values are confirmed against the pinned images at build. **FX** = `tests/firewall-negative-external.sh`, **FC** = `tests/firewall-negative-container.sh`. Rule IDs (H-n) are in § 3.2. "PROBE" is a throwaway container on its own network; "PEER-PROBE" is the same image attached to the target's network and serves as the positive control.

### 2.1 From outside the VM

| ID | Source | Destination | Verdict | Enforced by | Test |
|---|---|---|---|---|---|
| E1 | client network; Checkmk source | Caddy, TCP 443 | allow | H7 | AC-02; positive control of N-E2 |
| E2 | both forbidden sources; admin source unless it lies in the client network | Caddy, TCP 443 | **block** | H8 | FX · N-E2 |
| E3 | any | VM, TCP 80 | **block** (D-31, proposed) | not published; H8, H5 | FX · N-E3 |
| E4 | any | VM, UDP 443 | **block** [OR: SR-07] | not published; H8, H5 | FX · N-E4 |
| E5 | admin source | VM, TCP 22, key only | allow | H2 | the SSH session the tests run over; control of N-E6 |
| E6 | client network; both forbidden sources | VM, TCP 22 | **block** | H5 | FX · N-E6; password login refused from the admin source · N-E6b |
| E7 | Checkmk source | agent port — exists only if the agent route is chosen (S1, F-07) | allow | H3 | control of N-E8 |
| E8 | everyone else | agent port | **block** | H5 | FX · N-E8 (only when E7 exists) |
| E9 | any, including client, admin and Checkmk | MariaDB, TCP 3306 | **block** | no `ports:`; H8 | FX · N-E9 |
| E10 | any | Postfix, TCP 25, 465, 587 | **block** | no `ports:`; H8 | FX · N-E10 |
| E11 | any | Loki, TCP 3100 | **block** | no `ports:`; H8 | FX · N-E11 |
| E12 | any | Grafana TCP 3000 and Alloy TCP 12345, directly | **block** | no `ports:`; H8 | FX · N-E12 |
| E13 | any | Docker API, TCP 2375, 2376 | **block** | daemon has no TCP listener; H5 | FX · N-E13 |
| E14 | client network; forbidden-near | every other TCP port of the VM | **block** | H5, H8 | FX · N-E14: a full TCP sweep; expected open set is {443} for the client, {} for the forbidden source |

### 2.2 Between containers and outward

| ID | Source | Destination | Verdict | Enforced by | Test |
|---|---|---|---|---|---|
| C1 | Caddy | WordPress, HTTP, on `web` | allow | membership | AC-02 |
| C2 | WordPress | MariaDB, on `database` | allow | membership | EV-WEB |
| C3 | WordPress at its fixed address | Postfix, SMTP, on `mail` | allow | membership; Postfix trust list | AC-04; positive half of AC-05 |
| C4 | Alloy, Grafana | Loki, on `logs` | allow | membership | AC-06 |
| C5 | Caddy | Grafana, on `grafana-proxy` | allow | membership | AC-02 for the logs name |
| C6 | Postfix | external relay, TCP 587 | allow | egress network; H9 | AC-04 |
| C7 | PROBE | MariaDB 3306, by container address and by the VM address | **block** | bridge isolation; no `ports:` | FC · N-C7 |
| C8 | PROBE | Postfix SMTP, same two ways | **block** | as C7 | FC · N-C8 |
| C8b | a container on `mail` that is not WordPress | Postfix, relay request | **refuse at SMTP level** | Postfix relay restrictions | AC-05 |
| C9 | PROBE | Loki 3100, same two ways | **block** | as C7 | FC · N-C9 |
| C10 | PROBE | Docker API: TCP 2375, 2376 on the bridge gateway and the VM address; no socket in the container | **block** | no listener; no mount | FC · N-C10 |
| C11 | a stack member that is not on the target's network (Caddy → MariaDB, Postfix → MariaDB, WordPress → Loki) | — | **block** | membership | FC · N-C11 — EXTRA |
| C12 | MariaDB, Loki, Alloy, Grafana, WordPress | any address outside the VM | **block** | `internal` networks | FC · N-C12 — EXTRA |
| C13 | Postfix to anything but TCP 587; Caddy outward | outside the VM | **block** | H10 | FC · N-C13 — EXTRA |

C7 … C10 are part of AC-07 as written ("from an unauthorised container") and are therefore MUST HAVE. C11 … C13 prove the EXTRA Docker-network isolation row; see the conflict in § 4.3. Paths may be added to this matrix; none may be removed (SR-08 "Load-bearing tests").

## 3. Host firewall layer (mandatory, D-03)

**3.1 Facts the design rests on.**
- [RD] The host layer is mandatory (D-03). [OR] Rules for published container ports belong in `DOCKER-USER`, not only in `INPUT` (SR-07 "Forbidden"; SR-01 § 6 L101).
- [F] With Docker's iptables backend, user rules for forwarded traffic go in `DOCKER-USER` (SR-24 iptables L48–52, as paraphrased in plan-review S-4). This is conditional on the iptables backend (SR-24 nftables L52–55, same paraphrase).
- [F] Packets reach `DOCKER-USER` after destination translation, so a rule about the published port must match the original destination through connection tracking (SR-24 iptables L83–95, as paraphrased in F-03).
- [A] A-02: Docker on the chosen FCOS release uses the iptables backend. If the spike shows otherwise, this section does not apply as written: the requirement row and SR-07 both name `DOCKER-USER`, so an nftables design would be an owner decision, not a silent substitution. [OQ]

**3.2 Rule intent.**

| ID | Chain | Match (intent) | Verdict | Tier |
|---|---|---|---|---|
| H1 | `INPUT` | loopback; established and related | accept | MUST |
| H2 | `INPUT` | new TCP 22 from the admin source | accept | MUST |
| H3 | `INPUT` | agent port from the Checkmk source, only if the agent route is chosen | accept | MUST when used |
| H4 | `INPUT` | ICMP echo from the admin and Checkmk sources | accept | MUST |
| H5 | `INPUT` | everything else | drop (chain policy) | MUST |
| H6 | `DOCKER-USER` | arriving on the external interface; established and related | return to Docker's chains | MUST |
| H7 | `DOCKER-USER` | arriving on the external interface; new TCP; source in the client network or the Checkmk source; **original** destination the VM address, port 443 | return to Docker's chains | MUST |
| H8 | `DOCKER-USER` | arriving on the external interface; anything else | drop | MUST |
| H9 | `DOCKER-USER` | from the Postfix egress bridge to the external interface; TCP 587, plus DNS if SQ-8 shows it is needed | return | EXTRA |
| H10 | `DOCKER-USER` | from any Docker bridge to the external interface; any other new connection | drop | EXTRA |
| H11 | `ip6tables` `INPUT`, `FORWARD` | loopback and the ICMPv6 the segment requires; everything else | drop (policy) | MUST, § 3.4 |

Three points of intent:
1. **H6 … H8 are scoped to the external interface.** `DOCKER-USER` sees all forwarded traffic. An unscoped final drop could also cut container egress and, depending on bridge settings, traffic between containers [U: spike, SQ-1].
2. **H7 matches the original destination**, never the translated one (§ 3.1). A rule on plain destination port 443 would match the container's port, which happens to be equal today and silently stops protecting if the mapping changes.
3. **H5 is not redundant.** It carries SSH and the agent port, and it is the only barrier for a connection that reaches a published port through Docker's userland proxy instead of the forward path, which is how an IPv6 connection may arrive [U: SQ-5].

```
# illustrative, untested — intent of H6–H8 only
-A DOCKER-USER -i "$EXT_IF" -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
-A DOCKER-USER -i "$EXT_IF" -p tcp -s "$CLIENT_NET" -m conntrack --ctstate NEW --ctorigdst "$VM_ADDR" --ctorigdstport 443 -j RETURN
-A DOCKER-USER -i "$EXT_IF" -j DROP
```

[C] SR-07 "Firewall and network" says the rules "allow TCP 443 from the client network". H7 also admits the Checkmk source, because SR-01 § 6 L95 lets Checkmk reach "checked endpoints" and the active HTTPS check needs it. Either the Checkmk source is defined as part of the client network in the addressing plan, or the rule line is amended. Reported, not resolved.

**3.3 Loading, persistence and ordering.** One systemd unit shipped in Butane (R-03), running a script and a rule file under `firewall/`. Lab values come from a root-owned variables file on the VM, delivered like the secrets (§ 7), with a tracked example. How lab-specific values reach the VM without being tracked in Butane is S1's.

| Property | Design | Unverified part |
|---|---|---|
| Idempotent | Each run replaces the content of `INPUT` and `DOCKER-USER` in one transaction. A failed run leaves the previous rules in place | the exact restore invocation [U: spike] |
| Before any published port | Stage 1 runs **before** `docker.service`: `INPUT`, `ip6tables`, and a pre-created `DOCKER-USER` holding H6 … H8 | whether Docker keeps a pre-existing, populated `DOCKER-USER` [U: SQ-2] |
| After every Docker start | Stage 2 runs **after** `docker.service`, is bound to it so that a Docker restart re-runs it, asserts that the chain and Docker's jump to it exist, and re-applies | binding directive [U: spike] |
| Stack waits for the firewall | The Compose unit requires stage 2 and is ordered after it (S1 owns that unit; this is the requirement on it) | — |
| Fails closed | Chain missing, external interface missing, or a variable unset: the unit fails, the Compose unit does not start, no port is published | — |
| Persistent by re-application, not by saved state | The design does not depend on Docker preserving `DOCKER-USER` across a restart; the unit re-applies either way. AC-09 is the proof SR-07 asks for ("Rules survive a Docker restart and a host reboot. A test proves it") | Docker's own behaviour [U] |

**Why two stages.** Ordering the Compose unit after the firewall unit is not enough: the Docker daemon itself restarts containers that have a restart policy, before any later unit runs [U: SQ-3]. After an unclean shutdown those containers still exist. Stage 1 closes that window. If SQ-2 shows Docker discards a pre-created chain, the fallback is that no container carries a restart policy that starts it with the daemon, and the Compose unit alone starts the stack. That fallback trades away automatic restart of a crashed container and is S1's and the owner's call. [OQ]

**3.4 IPv6 (OQ-15).** [OR] IPv6 gets equivalent rules or is documented as not in use (SR-01 § 6 L99; SR-07). Proposal: **not in use, and enforced rather than only stated** — Docker networks without IPv6, the published port bound to the IPv4 wildcard, and H11. Evidence: the VM's IPv6 addresses, its listeners, the `ip6tables` rule set, and a negative test from an IPv6 source if the lab has one. If the spike finds IPv6 needed, the alternative is rule parity in `ip6tables` and a second pass over § 2. Decided after SQ-5.

**3.5 What the addressing plan must supply (F-04, OQ-06).** The allowed client network, the admin source, the Checkmk source, and **at least one forbidden source that can reach the VM** — otherwise a failed connection proves a missing route, not a rule. Suggestion for the owner: define the client network as a subset of the VM's segment, so that a forbidden address exists on the same segment (`LAB_FORBIDDEN_NEAR`). This widens the forbidden set; it does not narrow any test source.

**3.6 Proof before the services exist (F-13, D-33).** At the firewall step only a stub is published on 443. FX can then run N-E2, N-E3, N-E4, N-E6 and N-E14. That run is recorded as **partial** in a dated section of the AC-07 evidence file and AC-07 stays "not run". AC-07 is claimed only by a full run with all seven services up.

## 4. EXTRA layers

Built and proven only after every MUST HAVE check has passed (SR-03 "Order of work"; D-27 proposed; F-21).

**4.1 Proxmox firewall.**
- Intent: the same allow list at the VM boundary — inbound TCP 443, TCP 22 and the agent port from their sources, default drop; outbound limited to DNS, time, HTTPS for images and updates, and TCP 587.
- [U] Which levels must be enabled for a VM-level rule to take effect, and whether enabling them can cut the owner's own access to the host: no register entry covers the Proxmox firewall. Verify against its documentation before any change; this is a risk to the host, not only to the VM.
- [OR] Configuring it needs more than the auditor role: SR-07 "Lab access" — "The Proxmox API is used with a privilege-separated token holding the PVEAuditor role unless a task needs more. Any wider role is agreed with the owner first." Proposal: the owner applies it; the repository carries the rule set as an example with placeholder addresses.

**4.2 Proving an outer layer without switching off the inner one.** Once Proxmox drops a packet, the host never sees it, so a passing negative test no longer says which layer blocked — and a broken mandatory layer could hide behind the extra one. No layer is ever disabled for a test (SR-03 "Hard No"). Proposal:
- Attribute each block by counters: the host's drop counters on H8 and H5 before and after the attempt, and the Proxmox firewall's log.
- Keep the Proxmox allow list for TCP 443 one step wider than the host's (the VM's segment, against the client subset). The forbidden-near source then still reaches the host layer and is dropped **there**; the forbidden-far source is dropped at Proxmox. Each layer keeps its own proof.

**4.3 Docker-network isolation, and a tier conflict [C].**
- SR-01 § 2 L32 lists "separate Docker networks" as an extra. SR-03 "Scope Lock" marks Docker-network isolation EXTRA. SR-01 § 10 L147 (AC-07, MUST HAVE) requires blocked connections to fail "from an internal, unauthorised container", and § 6 L81–87 draws five networks as the base design.
- SR-03 "Out of Scope (Hard No)" forbids building "Any EXTRA or OPTIONAL item while a MUST HAVE row is unproven".
- Read strictly, the stack would start on one network and be split later. A later split recreates every network and, under SR-08 ("When a relevant change lands after a check passed, the check is re-run"), forces AC-02, AC-04, AC-05, AC-06, AC-07 and AC-09 to be run again.
- Proposal, for the owner to confirm: the networks of § 5 are created in their final form with the first Compose change, as base design; what waits for the EXTRA stage is the **claim** — N-C11, N-C12, N-C13 and rules H9, H10. Whether that reading respects the quoted line is the owner's decision. Reported, not resolved.

## 5. Docker networks and egress (F-10, R-10)

| Network | Members | Internal | Route out of the VM | Fixed addressing |
|---|---|---|---|---|
| `web` | Caddy, WordPress | yes | none | no |
| `database` | WordPress, MariaDB | yes [OR: SR-01 § 6 L89] | none | no |
| `mail` | WordPress, Postfix | yes | none | **yes**: fixed subnet, fixed WordPress address (§ 8) |
| `logs` | Alloy, Loki, Grafana | yes [OR: L89] | none | no |
| `grafana-proxy` | Caddy, Grafana | yes | none | no |
| `relay-out` (new) | Postfix only | no | TCP 587, and DNS if needed (H9) | stable bridge identifier for H9 |
| `edge` (new, conditional) | Caddy only | no | none (H10) | stable bridge identifier |

- `relay-out` is the finding's own correction (F-10): with `mail` internal, Postfix has no other way to the relay; with `mail` not internal, WordPress would share the exit.
- `edge` is needed only if a container attached solely to internal networks cannot publish a port [U: SQ-7]. If it can, `edge` is dropped.
- Both additions change the five-network table of SR-01 § 6. That table is not one of the fixed tables, but the change is an architecture edit and is proposed in § 11, not assumed.
- Consequence: WordPress, MariaDB, Loki, Alloy and Grafana have no route out. WordPress cannot fetch updates or plugins at run time; SR-01 § 4 L56 already wants plugins "from a reproducible source". How they get there is S1's. [OQ] whether the owner accepts a WordPress without outward access.
- Postfix: whether a container resolves an external name on its non-internal network without an extra rule is [U: SQ-8]. H9 limits by port (R-10); limiting by address as well is possible only if the relay's addresses are stable [OQ, with OQ-04].
- The host's own outward traffic (DNS, time, image pulls, OS updates, the Docker repository) is not restricted in the host layer; SR-01 § 6 L89 asks for these to be listed "in separate rules", which is proposed for the Proxmox layer (§ 4.1).
- Isolation between two Docker bridges is Docker's own behaviour [U against the register; N-C7 … N-C9 are its test].

## 6. TLS and the internal CA

**6.1 Facts and rules.**
- [OR] Caddy issues and renews with `tls internal`; its data directory is persistent; clients and Checkmk trust the root's public certificate; the CA private key never leaves the VM except in an encrypted backup (SR-07 "TLS and the internal CA"; SR-01 § 5 L71).
- [OR] Verification is never switched off (SR-01 § 5 L73, § 10 L142; SR-03 principle 7).
- [F] Internal leaf certificates default to a 12-hour lifetime (SR-25 tls.md L458, as cited in F-18). The renewal point inside that lifetime and the intermediate's and root's lifetimes are [U: SQ-12, or SR-25 tls.md L452–458].
- [OR] Grafana requires its own login behind HTTPS (SR-01 § 5 L73). Anonymous access stays off; the admin password is a secret (§ 7). An unauthenticated API request must be refused; AC-06 records it.

**6.2 Trust distribution.**
1. On the VM, copy **only** the root's public certificate out of Caddy's data directory. Its path inside the directory is [U: SQ-12; SR-25 automatic-https.md L150–156].
2. Transfer it over the existing SSH channel to the admin workstation, outside the repository.
3. Compare its SHA-256 fingerprint on both ends. A fingerprint is public and may appear in evidence.
4. Test client: scripts pass the file explicitly (`--cacert "$LAB_CA_CERT"`), so no system trust store changes for testing. Name resolution uses a hosts entry or the client's resolve option; that pins an address and leaves name verification on.
5. Demonstration browser: the owner adds the root to one client's trust store, as a documented manual step.
6. Checkmk: the root goes into the trust store its active checks use [U: OQ-25; A-06]. If the owner cannot change that store, the certificate check cannot be run verified, and this route is **blocked**, not worked around.

Honest limit: the root can sign any name. A client that trusts it trusts whoever holds the VM's CA key, for every site. Install it only on lab clients.

**6.3 Renewal trial (AC-03, F-18).** No configuration change: at the default lifetime a renewal falls within a day (F-18). The trial records the leaf at the start, polls until the serial changes, and stops at 12 hours plus a margin. An intermediate renewal cannot be observed in that window and is stated as not verified.

**6.4 Rebuild and restart (F-12).**
- Restart: the same root file must validate the site after a Docker restart and a reboot. This is the proof that the data directory persists, and AC-09 carries it.
- Fresh build (D-32, proposed): a new VM creates a new CA; steps 1 … 6 are repeated. The previous root must then **fail** against the new VM — the control that shows the build is fresh and that the check discriminates.
- Restore (AC-10): the previous root must still validate.

## 7. Secrets (F-20, R-18, OQ-16)

**7.1 Rules that bind.** [OR] SR-07 "Secrets handling" and "Forbidden": no secret in git, in Butane or Ignition, in `compose.yaml`, in `environment:` values, in image layers or in issue text; services read secrets as Compose secret files, one grant per service; sources outside the repository or git-ignored; one tracked example with names and placeholders; a new secret enters the example and the restore procedure in the same change; no encryption at rest on the host, said plainly; names and booleans only in logs.

**7.2 Inventory** (names only; fixed at the scaffold): `db_root_password` (MariaDB) · `db_wordpress_password` (MariaDB and WordPress, two grants) · `wordpress_salts` (WordPress, if the image accepts them from a file [U: S1]) · `wordpress_admin_password` (the provisioning step only, for the demonstration login) · `relay_credentials` (Postfix; format depends on the image, OQ-11) · `grafana_admin_password` (Grafana) · a Checkmk agent secret (only if the agent route is chosen [U]) · a backup passphrase (OPTIONAL tier, OQ-19). Not secret but lab-private, kept in the untracked variables file: the relay's host name and port, and the addresses of § 1.

An environment variable that holds the **path** `/run/secrets/<name>` is allowed; one that holds a value is not. Whether each image reads its secret from a file is [U] and belongs to image selection (S1).

**7.3 Channel, location, ownership and mode.**
- **Channel:** after the first boot and the Docker CE installation, the owner copies the source files over SSH from the admin workstation (R-18). Never through Ignition. This is a manual step of AC-01 and is listed among its documented sources.
- **Source side:** outside the repository, in a mode-600 location on the admin workstation, like the API token (SR-07 "Lab access"). Not in a git-ignored directory of the working tree: one forced `git add` would publish it.
- **VM side:** one directory under `/var/lib/corelab`, root-owned, mode 0700; one file per secret, mode 0400.
- **Owner of each file:** root where the image reads the secret as root before dropping privileges, otherwise the UID its process runs as. Compose's per-secret ownership and mode options may not apply to file-backed secrets [U: SQ-9; SR-27 not retrieved], so the host file's own ownership decides.
- **SELinux label:** a file-backed secret is a bind mount, and the secrets syntax has no relabel option [U]. The directory needs a label a confined container may read, applied by the unit that prepares it. Which label, and how to set it on a host without the usual policy tools, is [U: SQ-9].
- **Example file:** one tracked file listing name, consumer, format and a placeholder; its path is fixed at the scaffold.
- **Stated limits:** no encryption at rest; anyone with root on the VM or with Docker API access reads every secret. Rotation is not designed.

**7.4 Evidence item EV-SEC (F-14).** `tests/secrets-hygiene.sh` → `docs/evidence/req-secrets.md`. It prints names and booleans only: each inventory file exists with the designed owner and mode; no container has an environment variable that carries a value where a file path is designed; no rendered Ignition file and no secret source is tracked. The git-side half applies whatever the tier: keeping secrets out of git is not optional (SR-03 "Scope Lock").

## 8. Mail relay protection (F-05, R-05)

**8.1 Who may relay.** [OR] Postfix relays only for the designated application client, only to the designated external relay, with STARTTLS and authentication on TCP 587; a refused attempt from an unauthorised client is a required test (SR-07 "Mail"; SR-01 § 7 L107).
- **Exactly one client:** the WordPress container at one fixed address on `mail`. Postfix's trusted list holds that single address and loopback — narrower than the widest value SR-07 "Forbidden" tolerates ("the fixed Compose subnet of the allowed client"), so no exception is needed.
- **No published port** [OR]. Reachability from outside is a separate matter and is tested under AC-07 (N-E10), as F-05 asks.
- **Postfix is a final destination for nothing:** every accepted message goes to the relay.
- **Upstream side:** STARTTLS mandatory, and the relay's certificate verified against the image's CA bundle (SR-03 principle 7); credentials from the secret file.

**8.2 How the refusal is produced.** At the recipient stage of the SMTP dialogue: a client in the trusted list is permitted; for anyone else a recipient outside Postfix's own domains is rejected with a permanent 5xx reply, and nothing is queued. Parameter names and the exact reply are standard Postfix behaviour from general knowledge [U: `upstream-claim-verify` against the Postfix configuration reference, and the chosen image's documentation]. The test matches the reply class and the enhanced status code, not the text.

```
# illustrative, untested — intent only
mynetworks = 127.0.0.0/8 <WordPress address on mail>/32
smtpd_relay_restrictions = permit_mynetworks, reject_unauth_destination
```

**8.3 Limits, stated.**
- Trust is by source address. Whoever can create a container with that address is trusted; that requires the Docker API, which is why C10 and E13 matter to mail as well.
- A compromised WordPress can send anything through the authenticated relay account. Rate limiting is not designed.
- Authentication between WordPress and Postfix would remove the address dependency. It is not proposed (core-context § 13 principle 6).

**8.4 If no real relay exists (F-06, OQ-04).** A test receiver proves delivery inside the lab only [F: SR-01 § 7 L107]. The evidence must say so on its first line. Whether an in-lab delivery counts as AC-04 passed is the owner's decision, not this draft's [OQ]. A receiver inside the VM would be an eighth service with no scope-lock row. AC-05 does not depend on the relay: the refusal happens before any relaying.

## 9. SELinux and container privileges

**9.1 Baseline.**
- [OR] SELinux stays enforcing; `label=disable`, `privileged`, host namespaces, broad capabilities and a Docker socket mount each need a justification recorded next to them; bind mounts carry `:Z` (private) or `:z` (shared) (SR-07 "Forbidden", "Host").
- **Enforcing on the host is not the same as confined containers.** Whether Docker CE from Docker's repository confines containers by SELinux without an explicit daemon setting is [U: SQ-6]. If it does not, the host can report "Enforcing" while containers run unconfined. The setting, if needed, ships in Butane (S1). AC-01 records both the host mode and the daemon's security options.
- Base design: no `privileged`, no host network or PID namespace, no socket mount, no `ports:` except on Caddy, and no label exception. Every deviation is listed in § 9.4.
- Optional hardening, applied only where an image starts cleanly with it and never delaying a MUST HAVE row: drop all capabilities and add back the minimum (Caddy binds a low port), and no-new-privileges.

**9.2 The log collector's mounts (F-08, OQ-09).** The mechanism is S1's. This is the security ranking it should choose from. Every row's SELinux behaviour is [U: SQ-10].

| Rank | Route | Host mounts into Alloy | Exception needed |
|---|---|---|---|
| 1 | **Shared log volumes.** Caddy writes its access log, and Postfix its log, into named volumes that Alloy mounts read-only | none | none expected. Needs a Postfix image that can log to a file (SR-01 § 4 L65 says this must not be assumed; OQ-11) and rotation inside the volumes |
| 2 | **Host journal.** Docker's `journald` driver; Alloy reads the journal read-only | journal directories, machine ID | a confined container cannot read host logs by default. Either a dedicated log-reader SELinux type for Alloy alone, or `label=disable`. Both are deviations recorded next to the service. The journal must never be relabelled for a container |
| 3 | **Docker's JSON files** | `/var/lib/docker/containers`, read-only | as rank 2, and it exposes every container's output |
| 4 | **Docker socket** | the socket | full API access (SR-01 § 6 L103); a label exception as well. Not proposed |

Rank 1 covers what the requirement asks — web and SMTP logs (SR-01 § 2 L30, § 4 L59) — with no host mount. The other services' output then stays in Docker's own rotated logs and is not searchable in Grafana; that is a stated limit. If rank 1 fails in the spike, rank 2 with the narrow type is the fallback, with its justification written beside the service (R-13).

**9.3 The monitoring agent.** Installation is S1's (F-07). Constraints: the agent port is reachable from the Checkmk source only (E7, E8); an agent on the host reads Docker state as root with no container mount; a containerised agent would need the socket and host namespaces, each a recorded deviation. The smallest AC-08 route (R-07) needs no agent.

**9.4 Rule lines that may need an exception.**

| Rule line (exact) | When | Position |
|---|---|---|
| SR-07 "Forbidden": "`setenforce 0`, `SELINUX=disabled`, or `security_opt: label=disable` without a justification recorded next to it" | log routes 2 … 4; possibly the secrets mount if SQ-9 finds no usable label | Avoid by route 1. Otherwise prefer a narrow type over `label=disable` and record why |
| SR-07 "Forbidden": "A Docker socket mount (`/var/run/docker.sock`) without a recorded justification. A read-only mount is not read-only API access" | log route 4; a containerised agent | Not proposed |
| SR-07 "Firewall and network": "`DOCKER-USER` rules allow TCP 443 from the client network and drop the rest of the forwarded traffic to published ports" | the Checkmk source on 443 (§ 3.2) | Amend the line or the addressing plan |
| SR-07 "Lab access": "…holding the PVEAuditor role unless a task needs more. Any wider role is agreed with the owner first" | the Proxmox firewall (§ 4.1) | The owner applies it |
| SR-08 "Conventions": "Tests are read-only against the lab unless their name says otherwise (`restore`, `restart`)" | probes start throwaway containers; AC-04 sends a message; AC-08 stops a service | Script headers and names say so (§ 10); the wording could name these cases (§ 11) |
| SR-03 "Hard No": "Any EXTRA or OPTIONAL item while a MUST HAVE row is unproven" | final-form networks from the first change (§ 4.3) | Owner decision |

## 10. Verification design

### 10.0 Common elements

- **Scripts.** Under `tests/`, named `<area>-<what>.sh`, `set -euo pipefail`, printing what is checked, the command and a final PASS or FAIL (SR-08 "Conventions"). `tests/run-acceptance.sh` runs AC-02, AC-07, AC-05, AC-04, AC-06 in that order. AC-01, AC-03, AC-08, AC-09 and AC-10 are separate runs: they take a build, a day, an outside system, a restart or a restore.
- **Evidence** (R-16, F-18). One file per check, `docs/evidence/ac-NN-<slug>.md`; a screenshot beside it under the same stem; every screenshot accompanied by the same result as text. Each run adds a dated section with: date; VM build (repository revision, FCOS version); Docker CE, Compose and image versions with digests; the script and its revision; the **role** each request came from; command; output; PASS or FAIL. A check that did not run says "not run" (SR-08).
- **Redaction by construction.** Scripts print variable names, not their values, and replace every configured lab value in captured output with its variable name before writing. Mail addresses and the relay's name are masked the same way. No secret is ever read into output.
- **A static control on the tests themselves.** A gate that fails if any file under `tests/` or `scripts/` contains an option that disables certificate verification (SR-07 "Forbidden"). Proposed for `scripts/validate.sh` (R-17).

**Requirement rows and their proof (F-14).** The fixed tables are not changed; this only names where each proof lands.

| Requirement row (SR-01 § 2) | Proof |
|---|---|
| Fedora CoreOS on Proxmox | AC-01 |
| Docker CE | AC-01, required block "Docker CE proof" (F-01, D-32) |
| Web service: login, content, upload | **EV-WEB** — `tests/web-content-upload.sh` → `docs/evidence/req-web-function.md`: log in, create a post with a unique token, upload a file, read both back over verified HTTPS. Re-read after AC-09, which shows the data is durable |
| HTTPS reverse proxy: HTTPS access, HTTP backend | AC-02; the backend half by C1 and N-E12 |
| Internal CA and automation | AC-02, AC-03 |
| SMTP container | AC-04, AC-05 |
| Searchable logs | AC-06 |
| External monitoring | AC-08 |
| Firewall and separation | AC-07, AC-09 |
| Optional operations | restore: AC-10 · secrets: **EV-SEC** (§ 7.4) · update trial: **EV-UPD** — `docs/evidence/req-update-trial.md`, written by S1's update procedure |

**Nothing below narrows AC-05 or AC-07.** The unauthorised relay client is placed where it is strongest, on Postfix's own network. Every blocked path of § 2 is tested from every forbidden role that exists in the lab.

### 10.1 AC-01 Rebuild
- **Preconditions:** capacity for a second VM, or consent to destroy the first (OQ-02); the provisioning procedure and its privileges (S1, OQ-05); D-32 confirmed; secrets and variables files at hand.
- **Run:** the owner follows the documented procedure from a clean checkout at a recorded revision, on a new VM. Then `tests/host-rebuild-verify.sh` (read-only) over SSH.
- **Positive:** the Docker CE proof — `rpm -q docker-ce`, `rpm-ostree status`, `docker version` (SR-01 § 2 L25); host SELinux enforcing and the daemon's security options; the first-boot unit ran once and a reboot leaves the same state (SR-08 "When new tests are required"); firewall unit active; seven services running; then AC-02 and AC-07 against the new VM.
- **Negative:** the Moby engine package is absent. Where a previous VM existed, its root certificate fails against the new one (§ 6.4).
- **Right-reason check:** the log shows a newly provisioned machine — provisioning time later than the run's start — so an existing VM cannot satisfy the check. Every input from outside the repository is listed: OS image and checksum, package repository, image digests, the names of the secret and variables files.
- **Evidence:** `docs/evidence/ac-01-rebuild.md` · **Script:** `tests/host-rebuild-verify.sh`
- **Not verifiable yet:** all of it. Also open: whether two builds on different days yield the same engine version (F-09, OQ-14; S1).

### 10.2 AC-02 HTTPS
- **Preconditions:** root certificate exported, fingerprint compared (§ 6.2); name resolution (OQ-06); run from the client role.
- **Run:** `tests/proxy-https.sh`, for both names.
- **Positive:** a request with the lab root as the only trust anchor succeeds with verification on; the certificate's subject names, issuer, serial and validity are recorded.
- **Negative:** (a) the same request without the lab root fails with a verification error; (b) with the lab root but a name the site has no certificate for, it fails.
- **Right-reason check:** (a) and (b) fail on verification, not on connection, and they run in the same session as the positive case, so the pass cannot come from a client that verifies nothing.
- **Evidence:** `docs/evidence/ac-02-https.md` · **Script:** `tests/proxy-https.sh`
- **Not verifiable yet:** all of it; waits on OQ-06 and the root's path (SQ-12).

### 10.3 AC-03 Certificate lifecycle
- **Preconditions:** AC-02 passes; Caddy runs without interruption for the trial; the VM's clock is synchronised.
- **Run:** `tests/proxy-cert-renewal.sh record` at the start, `… compare` when the serial has changed or at the bound of § 6.3.
- **Positive:** a new leaf for the same name with a different serial and a later expiry; it verifies against the **same** root; Caddy's log lines for the renewal lie between the two readings.
- **Negative:** none in the acceptance row. The controls below take its place.
- **Right-reason check:** it is a renewal, not a re-issue: Caddy's container start time is unchanged, the root fingerprint is unchanged, the old leaf was still valid when the new one began, and no manual step lies between the readings.
- **Evidence:** `docs/evidence/ac-03-cert-renewal.md` · **Script:** `tests/proxy-cert-renewal.sh`
- **Not verifiable yet:** all of it. Beyond that: the renewal point within the lifetime [U], and any intermediate renewal, which this trial does not reach.

### 10.4 AC-04 Mail
- **Preconditions:** a relay with authentication and a test mailbox (OQ-04); Postfix image and WordPress integration chosen (OQ-10, OQ-11; S1); relay credentials in place.
- **Run:** `tests/mail-send-trace.sh`. It makes **WordPress** send a message with a unique token in the subject — through WordPress's own mail path, not from a separate SMTP client; the trigger is S1's.
- **Positive:** Postfix's log shows the message accepted, a queue ID, and the relay's acceptance; the owner confirms arrival in the mailbox; the same queue ID is found by a Grafana query, which joins this check to AC-06.
- **Negative:** none in the acceptance row.
- **Right-reason check:** the token is new on every run, so an older message cannot satisfy it; the queue ID in the received message's headers equals the one in the log.
- **Evidence:** `docs/evidence/ac-04-mail.md`, with a redacted view of the received message · **Script:** `tests/mail-send-trace.sh`
- **Not verifiable yet:** all of it. With a test receiver only, the limit of § 8.4 applies.

### 10.5 AC-05 Relay protection (load-bearing)
- **Preconditions:** Postfix running; `mail` with its fixed subnet and WordPress at its fixed address; a pinned probe image; a free address on `mail` for the probe [U: SQ-11].
- **Run:** `tests/mail-relay-refusal.sh`, on the VM. It starts and removes one probe container, and says so in its header.
- **Positive (same run):** from the WordPress container, a message for an outside recipient is accepted and queued.
- **Negative:** from the probe **on `mail`**, at another address: greeting, sender, then an outside recipient → permanent refusal. Repeated with the WordPress sender address as envelope sender → still refused. Nothing is queued for the probe.
- **Right-reason check:** the probe received Postfix's banner and a positive reply to its greeting in the same session, so the service was up and reachable from that very client; the allowed client succeeded in the same run. A timeout, a refused connection or a temporary 4xx reply is a **FAIL**: those would prove isolation or an outage, not relay protection.
- **Evidence:** `docs/evidence/ac-05-relay-refusal.md`, holding both transcripts · **Script:** `tests/mail-relay-refusal.sh`
- **Not verifiable yet:** all of it. The exact reply [U] and the image (OQ-11).

### 10.6 AC-06 Log search
- **Preconditions:** the log route decided (§ 9.2, R-13); Grafana reachable with its own login; AC-02 passes.
- **Run:** `tests/logs-search.sh`. It requests a non-existent path carrying a unique token, takes an SMTP event from the same session (the AC-04 queue ID or the AC-05 refusal), and queries through Grafana over verified HTTPS, authenticated. The API route is [U]; the owner's screenshot of the same query in Grafana accompanies the text result.
- **Positive:** the HTTP error line with the token and the SMTP line are both returned; the query text is recorded; the label set is service, host and environment only (SR-07 "Logs").
- **Negative:** an unauthenticated query is refused (§ 6.1).
- **Right-reason check:** a query for a token that was never sent returns nothing, so the query does not match everything; the token is new per run, so an old line cannot satisfy it.
- **Evidence:** `docs/evidence/ac-06-log-search.md` and `ac-06-log-search.png` · **Script:** `tests/logs-search.sh`
- **Not verifiable yet:** all of it; the route itself is undecided.

### 10.7 AC-07 Firewall (load-bearing)
- **Preconditions:** the addressing plan (OQ-06, A-07); firewall unit active; **all seven services running**; the external script runnable from each role; a pinned probe image.
- **Run:** `tests/firewall-negative-external.sh` once from each of the client, forbidden-near and forbidden-far roles, and from the admin role for the non-SSH paths. `tests/firewall-negative-container.sh` on the VM, which starts and removes probe containers. One result line per path ID of § 2.
- **Positive:** every "allow" row acting as a control: E1 from the client role; E5 as the session itself; for each internal service a PEER-PROBE on its network connects.
- **Negative:** N-E2 … N-E14 and N-C7 … N-C10. From a container, each target is tried **by container address and by the VM address**, not by name only: a name that does not resolve across networks is not a blocked connection.
- **Right-reason check:** per path, the control precedes the negative attempt in the same run. Published port: the client role succeeds, the forbidden role fails, and the host's drop counter rises by the attempt (§ 4.2). Unpublished service: the PEER-PROBE connects, the outside attempt fails. Docker API: it answers on its local socket on the host and on no TCP port. A negative result with a failed control is a FAIL.
- **Evidence:** `docs/evidence/ac-07-firewall.md` · **Scripts:** the two above
- **Not verifiable yet:** all of it. Weak by nature: N-E4 — a silent UDP port cannot be told from a dropped one, so the evidence adds the VM's listener list. IPv6 waits on SQ-5. A lab without a forbidden-far source records that role as not run.

### 10.8 AC-08 Monitoring
- **Preconditions:** a Checkmk instance the owner controls (OQ-03, A-06); the root certificate in its trust store (§ 6.2); an active HTTPS check on the application name with verification on — the smallest route (R-07). Agent checks are an addition (S1).
- **Run:** `tests/monitoring-service-restart.sh`: record the check's state; stop WordPress; wait for the check interval; record; start it; record. The states come from Checkmk as text where an interface allows [U: OQ-25], otherwise from the owner's screenshots with the status text typed beside them.
- **Positive:** OK before; critical after the stop; OK after the restore; three timestamps.
- **Negative:** none in the acceptance row.
- **Right-reason check:** the state was OK immediately before the stop, which shows that trust was in place and the alert is not a certificate error; the critical output names an HTTP failure; the change follows the stop time and the recovery follows the start time.
- **Evidence:** `docs/evidence/ac-08-monitoring.md` and screenshots · **Script:** `tests/monitoring-service-restart.sh`
- **Not verifiable yet:** all of it. [OQ] whether "alert" means the critical state or a delivered notification; proposed: the state and its entry in Checkmk's event history.

### 10.9 AC-09 Restart
- **Preconditions:** AC-02 and AC-07 passed in full on the current build; EV-WEB's token post exists.
- **Run:** `tests/host-restart.sh docker`, then `tests/host-restart.sh vm`. Each records the rule set, restarts, waits for the services, and re-runs AC-02 and AC-07 in full.
- **Positive:** all services return; the firewall unit ran and is active; the normalised `INPUT`, `DOCKER-USER` and `ip6tables` rule sets equal those from before; the same root file validates; the token post is still there.
- **Negative:** AC-07's negatives, after each restart. In addition a **boot-window probe**: the forbidden-near role attempts TCP 443 once a second across the restart and never succeeds.
- **Right-reason check:** the client role polls alongside and sees an outage followed by recovery, so "never succeeded" is not explained by a service that stayed down.
- **Evidence:** `docs/evidence/ac-09-restart.md` · **Script:** `tests/host-restart.sh`
- **Not verifiable yet:** all of it. Proposed addition, not required by the row: the same check after a hard stop from Proxmox, performed by the owner, because the window of § 3.3 differs after an unclean shutdown.

### 10.10 AC-10 Restore (OPTIONAL tier)
- **Preconditions:** the tier is delivered (OQ-19; D-22 proposed); S1's backup and restore procedures; an external, encrypted target.
- **Run:** `tests/backup-restore.sh`: write token A; back up; record the root fingerprint; write token B; restore onto a **fresh** VM in the order of SR-01 § 8 L121; measure.
- **Positive:** token A and its upload are present; AC-02 passes with the **previous** root file untouched on the client; time from start to that pass is recorded.
- **Negative:** token B is **absent**. No test message is sent a second time from a restored queue (SR-01 § 8 L117).
- **Right-reason check:** B's absence shows the data came from the backup and not from a surviving volume, and its age is the measured loss; the target was provisioned after the backup.
- **Evidence:** `docs/evidence/ac-10-restore.md` · **Script:** `tests/backup-restore.sh`
- **Not verifiable yet:** all of it; no target and no RPO or RTO values (OQ-19).

## 11. Proposed changes to the core documents

Proposals to the orchestrator. No core document was edited.

**Spike questions from this draft** — for the spike list S1 keeps. One command set and one dependent decision each; none has been run.

| ID | Question | Command | Decision that depends on it |
|---|---|---|---|
| SQ-1 | Firewall backend; does the chain exist | `docker info`; `iptables --version`; `iptables -S DOCKER-USER` | § 3 as written, or an owner decision (A-02) |
| SQ-2 | Does Docker keep a pre-created, populated `DOCKER-USER` | create the chain with a marker rule, start and restart Docker, `iptables -S DOCKER-USER` | two-stage unit, or the restart-policy fallback (§ 3.3) |
| SQ-3 | Do containers start before a unit ordered after Docker | `journalctl -b -o short-monotonic -u docker` against the unit's start time, after a hard stop | whether the boot window exists |
| SQ-4 | External interface name | `ip -br link` | the interface variable |
| SQ-5 | IPv6 on the VM and in Docker; an IPv6 listener on 443 | `ip -6 addr`; `ss -ltn`; `docker network inspect`; `ip6tables -S` | § 3.4 (OQ-15) |
| SQ-6 | Are containers confined by SELinux under Docker CE | `getenforce`; `docker info --format '{{json .SecurityOptions}}'`; `ps -eZ` for a container process | a daemon setting in Butane (§ 9.1) |
| SQ-7 | Can a container on internal networks only publish a port | such a container with a published port, tried from the client role | the `edge` network (§ 5) |
| SQ-8 | External name resolution from internal and non-internal networks | a lookup from a probe on each | H9 and Postfix's resolver |
| SQ-9 | Can a non-root, confined container read a file-backed Compose secret | a probe service with a root-owned 0400 secret; `ls -Z`; `ausearch -m avc -ts recent` | ownership, mode and label (§ 7.3) |
| SQ-10 | Log mounts under SELinux | a reader on a shared named volume; a journal mount with and without a log-reader type; `ausearch -m avc` | the log route (§ 9.2, OQ-09) |
| SQ-11 | Can a probe join a Compose network at a chosen address | `docker run --rm --network <project>_mail --ip <free address>` | the AC-05 and AC-07 probe method |
| SQ-12 | Root certificate path; default lifetimes | `find` in Caddy's data; `openssl x509 -noout -dates` on leaf, intermediate, root | § 6.2 step 1; the AC-03 bound |

- **core-context § 11, new assumptions:** containers are SELinux-confined only if the daemon is set so (SQ-6) · Docker keeps a pre-created `DOCKER-USER` (SQ-2) · a container on internal networks only cannot publish (SQ-7) · file-backed Compose secrets take the host file's ownership and need a container-readable label (SQ-9) · a probe can join a Compose network at a chosen address (SQ-11).
- **open-questions, additions:** (1) the tier conflict of § 4.3 — owner; (2) the Checkmk source on TCP 443 against the SR-07 line (§ 3.2) — owner; (3) whether an in-lab delivery passes AC-04 (§ 8.4) — owner; (4) what "alert" means in AC-08 — owner; (5) a WordPress without outward access (§ 5) — owner, with S1; (6) restart policy against the boot window (§ 3.3) — S1 and owner, after SQ-2 and SQ-3; (7) whether the relay's addresses are stable — with OQ-04. **OQ-06** should also ask for a forbidden source that can reach the VM, and whether a second, routed one exists (§ 3.5).
- **decision-log § 3, proposals to record:** the two-stage firewall unit and rule intent H1 … H11 · IPv6 not in use and enforced · a single trusted relay client address · networks `relay-out` and conditional `edge` (an edit to SR-01 § 6) · the secrets channel, location and modes of § 7.3 · evidence naming `docs/evidence/ac-NN-<slug>.md` and the items EV-WEB, EV-SEC, EV-UPD · the script names of § 10 · layer attribution by counters, with the Proxmox allow list one step wider (§ 4.2).
- **source-register:** retrieve and register what this draft could only tag [U] — the Postfix configuration reference, the Proxmox firewall documentation, the Compose secrets guide (SR-27), the container SELinux policy's types — and SR-26. Add to SR-24 and SR-25 what each cited line range says, so that a later session need not rely on a paraphrase.
- **rules (for the readiness report; not edited):** SR-08 "Conventions" could name probe containers and a sent test message beside `restore` and `restart`; SR-08 "Gates" could gain the no-insecure-option control (§ 10.0); SR-07 "Firewall and network" needs the Checkmk source settled.

## 12. Completion report

| Item | Content |
|---|---|
| Session | S2 — `security-writer` |
| Baseline | `docs-baseline-r1`; core documents r1; plan-review r1 |
| Files created or changed | Created `docs/.prepare/delegation/s2-security-verification.md`. Nothing else was created or changed |
| Evidence consulted | delegation-manifest (§ 2, packet S2); README, core-context, source-register, decision-log, open-questions (all r1); `docs/architecture.md` § 2, 5, 6, 7, 8, 10; plan-review r1, the thirteen assigned findings and their recommendations; `.claude/rules/security-patterns.md`, `test-requirements.md`, `product-vision.md`. SR-24 and SR-25 only through the register's line references and plan-review's paraphrases — the upstream files were not opened |
| Decisions proposed | The eight groups listed for decision-log § 3 in § 11. None is settled |
| Assumptions introduced | Five, listed for core-context § 11 in § 11, each tied to a spike question. Default service ports in § 2 are an assumption until the images are pinned |
| Open questions | Seven new ones and an extension of OQ-06 (§ 11). Two conflicts reported and not resolved: the tier of Docker-network isolation against AC-07 (§ 4.3), and the Checkmk source against the SR-07 rule line (§ 3.2). Six rule lines that may need an exception are quoted in § 9.4 |
| Validation performed | By reading only. Checked: every blocked path in § 2 names a test; each of the ten checks has preconditions, run, positive, negative, right-reason check, evidence file, script and "not verifiable yet"; all thirteen assigned findings have a status in § 1; no acceptance or requirement row is reworded; no address outside the documentation ranges, no real name and no host name appears; the two code fragments are labelled illustrative and untested; the file's length was read back after writing. No shell command was run, no git or GitHub action taken, no lab system contacted |
| Limitations | Nothing is built or tested, so nothing here is verified against a system. Docker, Caddy, Postfix, Compose, SELinux, Proxmox and Checkmk behaviour beyond the register's paraphrases is from general knowledge and tagged [U]. S1's draft was not read; overlaps with it (log mechanism, unit ordering, spike list, image-dependent details) are named as dependencies and may disagree with it. Script and evidence names are proposals until the scaffold fixes them |
| Status | **Complete** against the packet; no blocker for the session. The design itself stays blocked on the owner for OQ-03, OQ-04, OQ-06 and on the spike for SQ-1 … SQ-12 |
