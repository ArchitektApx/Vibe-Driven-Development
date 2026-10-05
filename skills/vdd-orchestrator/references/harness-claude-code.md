# Orchestrator on Claude Code

- **Spawn and resume.** The Agent tool spawns a fresh subagent. `SendMessage`
  addressed to that subagent's name resumes it with its context intact. When
  your Harness defers the schema of `SendMessage`, load it with `ToolSearch`
  first. End every resume message with the line `Deliver the line that ends
  this round with SubagentHandback.` after the Doorbell: a subagent that has
  handed back once reaches you only through that call, and a later round it
  ends in plain text never arrives.
- **The Spawn prompt's skill name.** `vdd:vdd-<role>`: `vdd:vdd-plan-reviewer`,
  `vdd:vdd-coder` or `vdd:vdd-code-reviewer`.
- **The context size.** It sits in the trailer under the Agent tool's result
  for the finished subagent.
- **The Doorbell file.** You ring and wait through it, as the Doorbell file
  for your platform says, `doorbell-file-unix.md` or on native Windows
  `doorbell-file-windows.md`, which `SKILL.md` links.
- **Starting with no review file on disk.** Arm the wait at 0, so the
  Planner's round-1 Doorbell already in the Doorbell file fires at once.
- **Relaying to the Planner.** Ring and arm your wait. Nothing confirms that
  the Planner's Session is reachable, so every relay also prints, worded: "If
  the Planner's Session does not wake, paste this into it:" followed by the
  exact Doorbell.
- **The wait.** Run the wait command in the background in your shell tool,
  Bash or PowerShell, with `run_in_background` set and an explicit `timeout`
  of at least 2760000 ms: the default timeout is below the script's 45
  minutes and would end the wait early. The Session wakes when the command
  exits.

Trust your live tools over this file when they disagree.
