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
- **Doorbell delivery.** This Harness delivers Doorbells through the
  Doorbell file, never by Session name.
- **The Orchestrator launch.** In the Cursor IDE, a new chat, then
  `/vdd-orchestrator` in it. In the Cursor CLI, `agent` in a terminal in this
  repository, then `/vdd-orchestrator` in that Session.

Trust your live tools over this file when they disagree.
