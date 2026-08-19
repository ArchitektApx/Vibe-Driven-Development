# The Orchestrator asks which model each hosted Role gets and names none itself

The Orchestrator derives the model and the thinking level for each hosted Role
from what its harness and the user's configuration have put in its context, and
states them at Model approval before its first spawn in a session. It guesses at
nothing: a field its context does not settle reads `inherited`, and the user
still answers. The skill itself names no model, no thinking level, and no
mapping from a Role to a kind of work.

The reason is that any mapping the skill states is a claim about a configuration
file the skill has never read. The words a user's configuration uses are the
user's: one file says "plan review", another names the skill
`vdd-plan-reviewer`, and a mapping written into the skill matches whichever of
them it was written against. The user reads their own configuration correctly by
construction, and Model approval is where they say what it means.

The version this replaces asked the Orchestrator to pass a model "where the
user's own steering names one for a Role's kind of work" while naming no kind of
work for any Role, and opened with the flat imperative `You name no model` three
sentences above the condition that overrode it. In the run that produced this
record the host was Fable, the user's configuration named opus for plan review,
and the Plan-Reviewer ran on Fable because nothing was passed.

## Considered options

**Stating the mapping in the skill, so the Orchestrator can match a Role to a
line in the user's configuration.** Rejected. The mapping would be a guess about
vocabulary the skill cannot see, and it would keep producing a confident answer
after the configuration it was written against had been rewritten. A wrong
mapping is worse than no mapping, because it is silent: the user learns which
model a Role got by reading the spawn line after the tokens are spent. Asking
costs one prompt and cannot be wrong about a configuration it never claims to
have read.

**Recording the approved selection in `LOOP.md`, so the prompt fires once per
Workflow rather than once per session.** Rejected. `LOOP.md` holds facts the
user states once and no Role changes, and a model line there would freeze a
selection across the restart where the user most wants to change it. The
derivation reads the same context on either side of a restart, so re-deriving
costs nothing but the prompt.

## Consequences

Model approval costs a prompt at the start of every session, including for a
user whose context names nothing about models and whose prompt therefore reads
`inherited` on every field. That user is the one the old behaviour served
silently and wrongly, so the prompt is what tells them the choice exists.

The approved selection holds for every spawn in that session, so a fourth Coder
round does not ask again. A restarted Orchestrator derives and asks again,
because the trigger is the first spawn in this session rather than the state of
the Workflow.

`You name no model` leaves the Orchestrator skill, and the sentence
characterising what the reviewing Roles want against what the Coder wants moves
into `docs/VDD-WORKFLOW.md`, where it addresses the user making the choice. A
rule leaving these files is a design decision made in its own Loop with a
reviewer who saw it go, which is the exception ADR-0004 names, and this record
is that decision's evidence.
