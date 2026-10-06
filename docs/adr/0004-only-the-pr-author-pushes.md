# Only the PR-Author pushes, and only after Sign-off

A push or a PR publishes the work beyond the user's machine, so exactly one
Role does it: the PR-Author, after Sign-off. The Coder and the
Code-Reviewer never push, without exception. Whether a PR is opened is
answered once at Workflow start and recorded in the `PR:` line of `LOOP.md`;
a missing or unrecognised line is read as asking at Sign-off, and nothing is
pushed before the user confirms the title and body it carries.

## Considered options

**A carve-out letting the Coder or the Code-Reviewer push under some
condition.** Rejected: their "never" rules mark where each Role's boundary
sits, and an exception would turn "never" into "usually" on every other line
of their files.
