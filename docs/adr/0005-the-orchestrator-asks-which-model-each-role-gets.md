# The Orchestrator asks which model each hosted Role gets

The skills name no model, no thinking level and no mapping from a Role to a
kind of work. Before its first spawn in a Session the Orchestrator states what
its context settles for each hosted Role, `inherited` where it settles
nothing, and the user approves or changes it. A mapping in the skill would be
a claim about a configuration the skill has never read, in words that
configuration may not use, and it would stay confidently wrong after the
configuration changed.

## Considered options

**Recording the approved selection in `LOOP.md`.** Rejected: it would freeze
the selection across the restart where the user most wants to change it.
