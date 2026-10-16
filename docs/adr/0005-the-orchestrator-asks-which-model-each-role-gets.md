# The Orchestrator asks which model each hosted Role gets

The skills name no model, no thinking level and no mapping from a Role to a
kind of work. Before its first spawn in a Session the Orchestrator tells the
user which model each hosted Role would get, as far as its own context
says, and the user approves or changes it. The skill cannot see which
models the user has, so a mapping written into it would name models that
may not exist there and would go stale when they change.

## Considered options

**Recording the approved selection in the Loop file.** Rejected: it would
freeze the selection across the restart where the user most wants to change
it.
