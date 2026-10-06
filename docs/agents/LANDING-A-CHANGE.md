# Landing a change: the mechanics

`AGENTS.md` states the rule: every change lands through a pull request, with
the `verify` check green and squash as its merge method. This file holds what
sits behind that rule and bites only when it is not known.

## Every commit is signed

Local commits inherit `commit.gpgsign`; an unsigned commit is rejected at
merge, not at push. A rebase re-creates the commits it moves and signs them
again under the same setting, so a signing failure leaves the rebase stopped
part-way rather than producing an unsigned commit.

## Actions are pinned to a commit SHA

Repository policy requires every action in `.github/workflows/` to be pinned to
a full commit SHA. A tag reference does not fail review, it fails the run.
Dependabot owns action versions and bumps them in one grouped PR monthly;
bumping a SHA by hand only creates a conflict with the next one.

## A workflow registers when a push modifies it

A workflow file registers with GitHub only when a push modifies it. A workflow
added in a repository's first push stays invisible, absent from the Actions
list, until some later commit touches the file.

## Releasing

`CHANGELOG.md` follows Keep a Changelog. These are its conventions as they
stand, described rather than enforced: changes collect under
`## [Unreleased]` on `beta`, migration steps go under
`### Migrating from <previous minor>` as the first heading of the section,
and repository-only changes go under `#### Internal` inside `### Changed`.

A release takes these steps, in order:

1. The last branch into `beta` before the release carries one commit that
   renames `## [Unreleased]` to `## [X.Y.Z] - <YYYY-MM-DD>` and bumps both
   manifests to `X.Y.Z`. Nothing is edited on `master` after the merge, so
   this commit is the release's content.
2. Merge `beta` into `master` by PR.
3. Run `release.yml`'s `workflow_dispatch` dry run on `master`. It checks
   that the manifests agree and extracts the version's changelog section,
   with no write access. When `release.yml` is missing from the Actions list
   after the merge, a commit that touches it registers it, as the section
   above says.
4. Tag `vX.Y.Z` on `master` and push the tag. `release.yml` checks that the
   tagged commit is on `master`, that the tag is `vX.Y.Z` with no
   pre-release suffix and matches both manifests, and publishes the GitHub
   release with that version's section as its body.
