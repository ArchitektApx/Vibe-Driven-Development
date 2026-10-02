# Start-Loop on Copilot CLI

- **Typed skill names.** Where you tell the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, `/vdd:vdd-<role>` for a VDD
  skill, such as `/vdd:vdd-planner`.
- **The Fresh Coder question.** Skip it and write `Fresh Coder: never`.
  Copilot CLI reports no context size for a subagent, so the Orchestrator
  would have no size to hold against a limit. Say in the closing summary that
  the user can ask the Orchestrator for a fresh Coder at any round.
- **Doorbell delivery.** This Harness delivers Doorbells through the
  Doorbell file, never by Session name.
- **The Orchestrator launch.** `copilot` in a terminal in this repository,
  then `/vdd:vdd-orchestrator` in that Session.

Trust your live tools over this file when they disagree.
