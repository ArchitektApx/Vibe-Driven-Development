# Planner on Claude Code

- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as `/grill-with-docs`
  or `/to-tickets .scratch/<slug>/spec.md`, and `/vdd:vdd-<role>` for a VDD
  skill, such as `/vdd:vdd-setup`.
- **The `code-review` reading.** In the wiring check, a hit on
  `mattpocock-skills:code-review` counts: it is the plugin install. A bare
  `code-review` counts only when its description names the two axes
  "Standards" and "Spec", because Claude Code ships a bundled `code-review`
  skill of the same name that reviews against something else.
- **The Orchestrator launch.** `claude -n <short>-<slug>-Orchestrator` in a
  terminal in this repository, then `/vdd:vdd-orchestrator` in that Session.
- **Delivering a Doorbell.** The tools are `SendMessage` and `ListAgents`.
  When your Harness defers their schemas, load them with `ToolSearch` first.
  Reachability is confirmed when `ListAgents` lists the Orchestrator's Session
  name; then send the Doorbell line with `SendMessage` addressed to that name.
  Either tool missing, or the name not listed, is a reachability you cannot
  confirm: print.

Trust your live tools over this file when they disagree.
