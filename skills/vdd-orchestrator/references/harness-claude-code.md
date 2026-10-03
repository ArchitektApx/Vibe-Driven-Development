# Orchestrator on Claude Code

- **Spawn and resume.** The Agent tool spawns a fresh subagent. `SendMessage`
  addressed to that subagent's name resumes it with its context intact. When
  your Harness defers the schema of `SendMessage`, load it with `ToolSearch`
  first.
- **The Spawn prompt's skill name.** `vdd:vdd-<role>`: `vdd:vdd-plan-reviewer`,
  `vdd:vdd-coder` or `vdd:vdd-code-reviewer`.
- **The context size.** It sits in the trailer under the Agent tool's result
  for the finished subagent.
- **Starting with no review file on disk.** Arm the wait at 0, as
  [`doorbell-file-posix.md`](doorbell-file-posix.md) says, so the Planner's
  round-1 Doorbell already in the Doorbell file fires at once.
- **Relaying to the Planner.** Through the Doorbell file: ring and arm your
  wait as [`doorbell-file-posix.md`](doorbell-file-posix.md) says. Nothing
  confirms that the Planner's Session is reachable, so every relay also
  prints, worded: "If the Planner's Session does not wake, paste this into
  it:" followed by the exact Doorbell.
- **The wait.** Run the wait form as a background Bash, with
  `run_in_background` set and an explicit `timeout` of at least 2760000 ms:
  the default timeout is below the script's 45 minutes and would end the wait
  early. The Session wakes when the Bash exits.

Trust your live tools over this file when they disagree.
