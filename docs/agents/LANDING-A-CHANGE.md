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
