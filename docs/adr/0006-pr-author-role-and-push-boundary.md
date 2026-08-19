# A seventh Role, PR-Author, is the only Role that pushes, and only after Sign-off

A new Role, PR-Author, runs on Sign-off and is the only Role in the Workflow
that pushes a branch or opens a PR. It runs in the Orchestrator's session,
which hosts it the same way it hosted the Code-Reviewer, or in the
Code-Reviewer's own session when the Workflow is run by hand. The user's
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

The Coder's "never push" rule and the Code-Reviewer's "never edits" rule stay
literally true. Neither Role gained an exception; the PR-Author is a new Role
with the one capability neither of the other two ever had.

The PR-Author never runs as a subagent, because every path in it shows the
assembled title and body to the user and waits for one confirmation, and that
body is substance the Orchestrator is forbidden to carry (ADR-0002). Hosting
it in the Orchestrator's session is the construction this record already uses
for the Code-Reviewer, where one session hosts a reviewing Role and then the
PR-Author, and the second Role's read list is its own.

A `LOOP.md` written by a release before this one has no `PR:` line. The
PR-Author reads a missing line the same way it reads an unrecognised one: as
`PR: ask at sign-off`, so an older Loop file fails safe into a question
rather than a silent push.

What ends a Loop, and what the user decides about it at Workflow start, are
ADR-0007's subject rather than this one's. This record keeps the Role and the
push boundary.
