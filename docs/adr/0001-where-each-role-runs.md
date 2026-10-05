# Where each Role runs

The Orchestrator hosts a Role as a subagent only when the Role needs a fresh,
independent context and needs no conversation with the user, and a contract
holds every hosted Role to both conditions. The Planner runs in a Session of
its own and the PR-Author in the Orchestrator's Session, because both need the
user directly.

The Plan-Reviewer, the Coder and the Code-Reviewer meet both conditions. A
review is worth something only when the reviewer has not inherited the
reasoning it reviews, and the Coder works from the Spec and the Tickets rather
than from the conversation that produced them. None of the three has to talk
the work through with the user. The contract: a hosted Role communicates only
through its Working file and a turn that ends in `DOORBELL`, `QUESTION` or
`BLOCKED`, relies only on skills an agent can invoke, and needs the user for
nothing beyond what one `QUESTION` or `BLOCKED` carries.

The Planner's grilling is the most intense conversation with the user in the
Workflow and relies on Borrowed skills only the user can start, so it cannot
be hosted. It runs in a Session of its own rather than in the Orchestrator's,
where the planning would fill the context of a Role whose only job is to
orchestrate.

The PR-Author shows the title and body for the user to accept or change as
often as they want, which the contract cannot carry. The Orchestrator invokes
it in its own Session after Sign-off. That is harmless, because at Sign-off
the orchestration is finished and nothing is left to pollute.

## Considered options

**Each Role in its own Session, started by hand.** Rejected: a subagent starts
from its Spawn prompt alone, so hosting gives each Role a context as fresh as
its own Session would, and saves the user a Session per Role.
