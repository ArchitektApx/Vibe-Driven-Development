# Placing a Workflow that was already under way

Read `LOOP.md`, then each of `.scratch/<slug>/PLAN-REVIEW.md`,
`.scratch/<slug>/CODEREVIEW.md` and `.scratch/<slug>/FIXES.md` down to and
including its `Round` line. Those lines place the Workflow, and one of these
five states holds:

- **No review file on disk.** The Workflow has not reached a review yet. Wait
  for the Planner's Doorbell and do nothing else.
- **`PLAN-REVIEW.md` present and not signed off.** The plan Loop is open.
  Relay `VDD Plan-Reviewer: PLAN-REVIEW.md written, round <n>. Read it.` to
  the Planner and wait; the Planner owns the next move.
- **`PLAN-REVIEW.md` signed off, no `CODEREVIEW.md`.** The code Loop has not
  started. Spawn the Coder.
- **`CODEREVIEW.md` present and not signed off.** Compare its `Round` line
  with `FIXES.md`'s. The same round means the Coder owes the answer: spawn
  the Coder. `FIXES.md` one round above `CODEREVIEW.md` means the
  Code-Reviewer owes the review: spawn the Code-Reviewer. `FIXES.md` below
  `CODEREVIEW.md` cannot happen in a live Loop.
- **`CODEREVIEW.md` signed off.** The Loop is over. Invoke the PR-Author in
  your own session.

The relay in the second state is what the read boundary lets you say. The
counts of open findings per severity live below the `Round` line, which you may
not read, so a restarted relay carries the file and the round and asks the
Planner to read the findings itself rather than a count you cannot see.

A restart costs the Role that was in flight the context it accumulated across
earlier rounds: the round after a crash costs what a first round costs.
