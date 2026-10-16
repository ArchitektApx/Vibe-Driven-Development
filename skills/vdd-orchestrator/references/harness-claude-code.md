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
- **The wait.** Run the wait command a `Next:` line names in the
  background in your shell tool, Bash or PowerShell, with `run_in_background`
  set and an explicit `timeout` of at least 2760000 ms: the default timeout
  is below the wait's 45 minutes and would end it early. The Session wakes
  when the command exits.
- **A refused command.** When a sandbox refuses a command, rerun it once with
  `dangerouslyDisableSandbox: true` on the same call. When that is denied
  too, stop with one line naming the command and what it was for; a wait
  falls back to hand relay instead.

Trust your live tools over this file when they disagree.
