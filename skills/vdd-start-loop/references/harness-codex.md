# Start-Loop on Codex

- **Typed skill names.** Where you tell the user to invoke a skill, give the
  form they type: `$<name>` for a Borrowed skill, `$vdd:vdd-<role>` for a VDD
  skill, such as `$vdd:vdd-planner`.
- **The Fresh Coder question.** Skip it and write `Fresh Coder: never`. Codex
  reports no context size for a subagent, so the Orchestrator would have no
  size to hold against a limit. Say in the closing summary that the user can
  ask the Orchestrator for a fresh Coder at any round.
- **The rename command.** `/rename <short>-<slug>-Planner`.
- **The Orchestrator launch.** `codex` in a terminal in this repository, then
  `/rename <short>-<slug>-Orchestrator`, then `$vdd:vdd-orchestrator`. Codex
  takes no Session name at launch, so the rename comes first.

Trust your live tools over this file when they disagree.
