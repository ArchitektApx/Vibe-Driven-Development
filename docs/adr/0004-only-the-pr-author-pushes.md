# Only the PR-Author pushes, and only after Sign-off

A push or a PR publishes the work beyond the user's machine, so exactly one
Role does it: the PR-Author, after Sign-off. The Coder and the Code-Reviewer
never push. Whether a PR is opened is asked at Workflow start or, with
`ask at sign-off`, the default, deferred to Sign-off, and nothing is pushed
before the user confirms its title and body.

## Considered options

**A carve-out letting the Coder or the Code-Reviewer push under some
condition.** Rejected: their "never" rules mark where each Role's boundary
sits, and an exception would turn "never" into "usually" on every other line
of their files.
