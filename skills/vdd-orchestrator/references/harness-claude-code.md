# Orchestrator on Claude Code

- **Spawn and resume.** The Agent tool spawns a fresh subagent. `SendMessage`
  addressed to that subagent's name resumes it with its context intact. When
  your Harness defers the schema of `SendMessage` or `ListAgents`, load it with
  `ToolSearch` first.
- **The Spawn prompt's skill name.** `vdd:vdd-<role>`: `vdd:vdd-plan-reviewer`,
  `vdd:vdd-coder` or `vdd:vdd-code-reviewer`.
- **The context size.** It sits in the trailer under the Agent tool's result
  for the finished subagent.
- **Relaying to the Planner.** Reachability is confirmed when `ListAgents`
  lists the Planner's Session name; then send the Doorbell line with
  `SendMessage` addressed to that name. Either tool missing, or the name not
  listed, is a reachability you cannot confirm: print. When `ListAgents` runs
  and does not list the Planner's Session name, print the Doorbell together
  with the line `/rename <Planner Session name>`, the real name filled in,
  for the user to type in the Planner Session: one rename there lets every
  later relay reach it.

Trust your live tools over this file when they disagree.
