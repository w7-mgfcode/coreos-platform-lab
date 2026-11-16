---
name: Sub-issue
about: One branch and one pull request under an epic. Carries its epic's milestone.
title: "type(scope): description"
labels: "type:sub-issue"
---

<!--
Title: the commit grammar without the issue suffix, lowercase, imperative, no trailing period.
After filing: link this issue as a native sub-issue of its epic, set the epic's milestone, and add
its area:, tier: and priority: labels, and a gate: label only if this issue proves an acceptance check. Cite file:line or "architecture § x" for every claim.
No secret, lab address, host name, real name, mail address or absolute home path anywhere in this issue.
-->

Sub-issue of #

## Purpose

## Scope

<!-- The files in scope. -->

## Out of scope

## Dependencies

<!-- By issue number. -->

## Risks / blockers

## Acceptance criteria

<!--
Each one verifiable by a command, a test script or an evidence file. Name the acceptance checks
(AC-nn) this issue proves. Tick only with proof: *(proof: PR #n / commit abc1234 / docs/evidence/<file>)*
A check that was not run on the lab is not passed.
-->

- [ ]

## Why it matters now
