# A seventh Role, PR-Author, is the only Role that pushes, and only after Sign-off

A new Role, PR-Author, runs in the Code-Reviewer's session on Sign-off and is
the only Role in the Workflow that pushes a branch or opens a PR. The user's
consent for that push is one line in `LOOP.md`, written once at Workflow start
by `vdd-start-loop`, so the PR-Author reads it instead of asking again.

## Considered options

**A fifth Session for the PR-Author.** Rejected. A fifth Session name would
mean a fifth terminal the user opens by hand at the exact point the Workflow
is closest to finished and the user is closest to walking away. The
PR-Author's read list, `LOOP.md`, `CODEREVIEW.md`, `PLAN-REVIEW.md`,
`FIXES.md` and the Spec, is exactly what the Code-Reviewer's session already
holds or can read fresh, so a new session would buy no independence a
reviewer needs, only a copy-paste step a Doorbell already removes elsewhere.

**A carve-out on the Coder or the Code-Reviewer instead of a new Role.**
Rejected. The Coder's rule that it never pushes and the Code-Reviewer's rule
that it edits no files are both guardrails a user reads to know where each
Role's boundary sits. A carve-out that let either Role push under some
condition would turn "never" into "usually", and the next reader would have
to hold the exception in mind on every other line of that Role's file.

**Consent asked at Sign-off only, with no line in `LOOP.md`.** Rejected. A
question asked at Sign-off with no record anywhere is a question asked again
on every branch that reaches that point, which is the manual step User Story
3 exists to remove for the regular user. Writing the answer into `LOOP.md` at
Workflow start is the same pattern every other Role already reads from that
file, and it is what lets `PR: yes` skip the question entirely.

## Consequences

A new Doorbell template line exists for the case where `CODEREVIEW.md` signs
off with minors still open and the user chooses to fix them first: `VDD
PR-Author: CODEREVIEW.md SIGNED OFF with <p> minor open. Read it.` ADR-0002
stays as it is, because that line carries no substance beyond which file to
read and which round, the same bound every other Doorbell keeps.

The Coder's "never push" rule and the Code-Reviewer's "never edits" rule stay
literally true. Neither Role gained an exception; the PR-Author is a new Role
with the one capability neither of the other two ever had.

The PR-Author runs in a session the user started, on the same in-session
hand-over `vdd-start-loop` already uses to reach `vdd-planner`. ADR-0001
stands unamended: the workflow's value still comes from the user invoking
each Role by hand, and the PR-Author is invoked the same way, inside a
session the user is already sitting in.

A `LOOP.md` written by a release before this one has no `PR:` line. The
PR-Author reads a missing line the same way it reads an unrecognised one: as
`PR: ask at sign-off`, so an older Loop file fails safe into a question
rather than a silent push.
