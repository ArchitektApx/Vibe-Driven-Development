# Start-Loop on Claude Code

- **Typed skill names.** Where you tell the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, `/vdd:vdd-<role>` for a VDD
  skill, such as `/vdd:vdd-planner`.
- **The Fresh Coder question.** Offer 350k as the limit.
- **The rename command.** `/rename <short>-<slug>-Planner`.
- **The Orchestrator launch.** `claude -n <short>-<slug>-Orchestrator` in a
  terminal in this repository, then `/vdd:vdd-orchestrator` in that Session.

Trust your live tools over this file when they disagree.
