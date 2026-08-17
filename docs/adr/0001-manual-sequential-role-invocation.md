# Roles are invoked manually, in sequence, by the user

Each Role runs in a session the user starts by hand, in a fixed order: Planner
and Plan-Reviewer until `PLAN-REVIEW.md` signs off the Spec, then Coder and
Code-Reviewer. The user is what sequences them, and the plugin orchestrates none
of it. The workflow's value comes from each session's context being genuinely
fresh, and from the user being present in the loop.

## Considered options

**Roles as subagents, orchestrated by one parent session.** Rejected after
trying it. Two things broke. A subagent inherits its parent's framing, so the
reviewer arrives already knowing the planner's reasoning, which is the exact
blind spot the split exists to remove. And the reviewer Roles turned out to be
interactive in practice: the Plan-Reviewer and Code-Reviewer routinely need to
ask the user a question mid-review, and a subagent has no one to ask.

## Consequences

The workflow is brittle in a known way: it depends on the user invoking the
Roles in the right order, and nothing enforces that. Accepted deliberately, no
better option was found.

This also settles how the Planner handles Borrowed skills. `grill-with-docs`
and `improve-codebase-architecture` are User-invoked, so an agent cannot start
them. Under any orchestrated design that would be an obstacle to work around.
Here it is the same pattern the rest of the workflow already uses: the
Planner asks, the user types the command, the session continues.
