# The Orchestrator hosts the Plan-Reviewer, the Coder and the Code-Reviewer as subagents

The Orchestrator, a new Role, spawns the Plan-Reviewer, the Coder and the
Code-Reviewer as subagents, each in a fresh context, and carries Doorbells in
both directions between the Planner and the Loop it hosts. The PR-Author runs
in the Orchestrator's own session at the end. The user runs two sessions
instead of four: the Planner in the foreground, where the design decisions
are made, and the Orchestrator, opened when the Planner rings its first
Doorbell.

## Considered options

**The user invoking each Role by hand, in a fixed sequence, with no
orchestration.** Taken through release 0.6.0 on two grounds: a subagent
inherits its parent's framing, so a reviewer would arrive already knowing the
planner's reasoning, and a subagent has no one to ask, so the reviewing Roles
could not do the asking they do in practice. Reversed on 2026-08-19: both
grounds were measured false during this Workflow's grilling. A subagent's
context begins with its Spawn prompt and holds nothing of its parent's
conversation, probed on four hosts on 2026-08-18. A subagent can end its turn
with a question, its parent can put that question to the user, and the same
subagent resumes with the answer, its context intact, measured end to end
during this Workflow's grilling.

## Consequences

Two claims survive the reversal and move into this record rather than out of
it. Each Role's context must be genuinely fresh, which is why the Planner
still runs in the user's own foreground session rather than as a subagent of
the Orchestrator: the Planner is where the design decisions are made, and no
later Role may inherit that reasoning. And the user must be present in the
Loop, which is why a Role that its own instructions send to the user ends its
turn with a question rather than guessing; the Orchestrator relays it and
resumes the same subagent with the answer. No reviewer gains a right to ask
about the work in hand from this: a review is still judged from the Working
files alone, and a Coder reading this record and ADR-0007 together cannot
conclude otherwise.

A known limit, undiagnosed: headless `codex exec` was observed hanging twice,
five minutes each with no output, against a trivial prompt returning in
seconds, when asked to spawn a child. A VDD Orchestrator is an interactive
session, so this does not reach it.

This also settles how the Planner handles Borrowed skills. `grill-with-docs`
and `improve-codebase-architecture` are User-invoked, so an agent cannot start
them. Here it is the same pattern the rest of the workflow already uses: the
Planner asks, the user types the command, the session continues.
