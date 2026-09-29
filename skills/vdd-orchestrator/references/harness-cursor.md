# Orchestrator on Cursor

- **Spawn and resume.** The Task tool spawns a fresh subagent, and its result
  carries the subagent's agent ID. The Task tool given that agent ID resumes
  the same subagent with its context intact.
- **The Spawn prompt's skill name.** `vdd-<role>`, bare: `vdd-plan-reviewer`,
  `vdd-coder` or `vdd-code-reviewer`. A child loads the skill by reading its
  `SKILL.md`.
- **The context size.** None reaches the parent: a Task result carries the
  reply and the agent ID only. The no-size path of "The Coder's context"
  applies from the first Coder return.
- **Relaying to the Planner.** None: print the exact Doorbell at once and ask
  the user to paste it into the Planner's Session; make no reachability
  attempt.

Trust your live tools over this file when they disagree.
