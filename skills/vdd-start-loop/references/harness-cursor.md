# Start-Loop on Cursor

- **The Harness value.** The Cursor IDE Agent and the Cursor CLI are one
  Harness: both write `Harness: Cursor`. Ask the user nothing about which of
  the two they run.
- **Typed skill names.** Where you tell the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, `/vdd-<role>` for a VDD
  skill, unprefixed, such as `/vdd-planner`.
- **The Fresh Coder question.** Skip it and write `Fresh Coder: never`. Cursor
  reports no context size for a subagent, so the Orchestrator would have no
  size to hold against a limit. Say in the closing summary that the user can
  ask the Orchestrator for a fresh Coder at any round.

Trust your live tools over this file when they disagree.
