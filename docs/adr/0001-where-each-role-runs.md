# Where each Role runs

The Orchestrator hosts a Role as a subagent only when the Role needs a fresh
context and no conversation with the user. Every other Role runs in a
Session the user opens.

## The user's Session

Start-Loop runs Setup and hands the Session to the Planner. The Planner
grills the user and needs Borrowed skills only the user can start, so it
cannot be hosted. The Brainstormer and the Wayfinder, which come before a
Workflow, run in the user's Session because they talk with the user
throughout.

## The Orchestrator's Session

The Orchestrator runs in a Session of its own, opened at the Planner's first
Doorbell, so the planning does not fill its context.

It hosts the Plan-Reviewer, the Coder and the Code-Reviewer. A reviewer must
not inherit the reasoning it reviews, and the Coder works from the Spec and
the Tickets, not from the conversation behind them. A hosted Role
communicates only through its Working file and a turn that ends in
`DOORBELL`, `QUESTION` or `BLOCKED`, and relies only on skills an agent can
invoke.

After Sign-off the Orchestrator invokes the PR-Author in its own Session:
the user may change the title and body as often as they want, which a
hosted Role cannot carry, and nothing is left to pollute.

## Considered options

**Each Role in its own Session, started by hand.** Rejected: a subagent
starts from its Spawn prompt alone, as fresh as its own Session, and hosting
saves the user a Session per Role.
