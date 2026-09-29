# Planner on Cursor

- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as `/grill-with-docs`
  or `/to-tickets .scratch/<slug>/spec.md`, and `/vdd-<role>` for a VDD
  skill, unprefixed, such as `/vdd-setup`.
- **The Orchestrator launch.** In the Cursor IDE, a new chat, then
  `/vdd-orchestrator` in it. In the Cursor CLI, `agent` in a terminal in this
  repository, then `/vdd-orchestrator` in that Session.
- **Delivering a Doorbell.** None: print the exact Doorbell at once and ask
  the user to paste it into the Orchestrator's Session; make no reachability
  attempt.

Trust your live tools over this file when they disagree.
