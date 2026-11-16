<!--
Title grammar: type(scope): description (#issue)
- type: feat | fix | docs | refactor | test | chore | release
- scope: host | compose | proxy | web | mail | logs | monitoring | firewall | backup | tests | docs | diagrams | ci | repo | release
  (a comma pair such as compose,mail is allowed; only docs and release may omit the scope for a project-wide change)
- description: lowercase, imperative, no trailing period; the issue number is required
The title becomes the squash commit on main. Write no AI attribution line in the title or this body.
Fill every section; write "none" or "not applicable" with the reason instead of deleting it.
-->

## Summary

## Linked issue

Closes #

## Static gates

<!--
RUN: the exit status of scripts/validate.sh on this branch; or NOT RUN with the reason
(no configuration changed, or the gate script does not exist yet). Never PASS without a run.
-->

## Acceptance checks touched

<!--
One line per check: AC-nn — RUN (evidence link) / RETAINED (earlier evidence and why it still holds) / NOT RUN.
"none" if this change touches no acceptance check. Planned or expected results are not evidence.
-->

## Checks to re-run after this change

<!-- Acceptance checks a later release must re-run because of this change (.claude/rules/test-requirements.md). -->

## Vision check

<!-- The scope-lock row this serves (.claude/rules/product-vision.md), or the correctness, security or demonstration problem it fixes. -->

## Security check

- [ ] No secret, token, private key or rendered `*.ign` in the diff
- [ ] No real name, mail address, lab address, host name or absolute home path in the diff, the title or this body
- [ ] No `ports:` on any service but Caddy; every image pinned by version or digest
- [ ] No disabled TLS verification, SELinux or firewall
- [ ] AC-05 and AC-07 are not weakened and their sources are not narrowed
