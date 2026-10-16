# Orchestrator on Cursor

- **Spawn and resume.** The Task tool spawns a fresh subagent, and its result
  carries the subagent's agent ID. The Task tool given that agent ID resumes
  the same subagent with its context intact.
- **The Spawn prompt's skill name.** `vdd-<role>`, bare: `vdd-plan-reviewer`,
  `vdd-coder` or `vdd-code-reviewer`. A child loads the skill by reading its
  `SKILL.md`.
- **The context size.** None reaches the parent: a Task result carries the
  reply and the agent ID only.
- **The wait.** Run the wait command a `Next:` line names as a
  background shell; the Session wakes when the shell finishes. The IDE Agent
  and the CLI may each wake twice for one wait: on the second, `take` finds no
  new Doorbell, and while a wait of yours still runs its `Next:` says to end
  your turn rather than start another. Run `ring` and `take` in the foreground
  with a `block_until_ms` of 120000, so each finishes inside its call: in the
  Cursor CLI, a shell moved to the background that finishes while your turn
  runs stops every later wake in this Session.
- **A refused command.** When a sandbox refuses a command, rerun it once with
  the Shell call's request to run outside the sandbox. When that is denied
  too, stop with one line naming the command and what it was for; a wait
  falls back to hand relay instead.

Trust your live tools over this file when they disagree.
