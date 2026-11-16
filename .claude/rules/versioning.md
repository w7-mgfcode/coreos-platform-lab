# Versioning

CoreOS Platform Lab ships **one SemVer train** for the whole repo, tagged by hand. There is no release automation.

## Train

| Train | Tag | Source of truth | Changelog |
|-------|-----|-----------------|-----------|
| CoreOS Platform Lab | `vX.Y.Z` | the top section of `CHANGELOG.md` and the matching git tag | `CHANGELOG.md` (root, hand-maintained) |

The repository has no package manifest, so the changelog heading and the tag are the only version markers. They must agree.

Component versions are a separate matter: Fedora CoreOS, Docker CE, the Compose plugin and every container image are pinned in configuration and listed in the documentation. Bumping one of them is an ordinary `chore` or `fix` change, not a release of this repo.

## Cutting a release

1. Confirm the release gate on the lab: every MUST HAVE acceptance check in `test-requirements.md` (AC-01 … AC-09) has passed since the last relevant change, with evidence committed.
2. Add a dated section to `CHANGELOG.md` in one `release(repo): cut X.Y.Z (#N)` commit on `main`.
3. Tag and push: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`.

`v0.1.0` is cut the first time the release gate passes end to end. Ask the owner before pushing any tag.

## SemVer mapping

| Commit | Bump |
|--------|------|
| `feat!:`, `fix!:`, or `BREAKING CHANGE:` in the body | MINOR while in `v0.x`; MAJOR after `v1.0.0` |
| `feat(...)` | MINOR |
| `fix(...)` | PATCH |
| `docs`, `chore`, `refactor`, `test` | No bump; listed under "Other" in the changelog. CI work uses `chore(ci)` under the existing commit grammar. |

A breaking change here is one that an existing VM cannot take without a rebuild or a manual migration, such as a changed data path, a renamed volume or a changed network subnet. While in `v0.x`, MINOR may include breaking changes — call them out under a `### Breaking` heading.
