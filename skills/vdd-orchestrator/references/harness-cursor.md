# Orchestrator on Cursor

- **Spawn and resume.** The Task tool spawns a fresh subagent, and its result
  carries the subagent's agent ID. The Task tool given that agent ID resumes
  the same subagent with its context intact.
- **The Spawn prompt's skill name.** `vdd-<role>`, bare: `vdd-plan-reviewer`,
  `vdd-coder` or `vdd-code-reviewer`. A child loads the skill by reading its
  `SKILL.md`.
- **The context size.** None reaches the parent: a Task result carries the
  reply and the agent ID only. From the first Coder return, whatever the
  `Fresh Coder:` line says, the no-size path of the fresh-Coder file that
  `SKILL.md` links applies: tell the user once that the check cannot run and
  that they can ask for a fresh Coder at any round. On that request, spawn as
  that file says.
- **The Doorbell file.** You ring and wait through it, as the Doorbell file
  for your platform that `SKILL.md` links says.
- **Starting with no review file on disk.** Arm the wait at 0, so the
  Planner's round-1 Doorbell already in the Doorbell file fires at once.
- **Relaying to the Planner.** Ring and arm your wait. Nothing confirms that
  the Planner's Session is reachable, so every relay also prints, worded: "If
  the Planner's Session does not wake, paste this into it:" followed by the
  exact Doorbell.
- **The wait.** Run it as a background shell; the Session wakes when the
  shell finishes. The IDE Agent and the CLI may each wake twice for one wait,
  delivering the same output again; the duplicate rule in
  the Doorbell file for your platform makes the second wake a no-op.

Trust your live tools over this file when they disagree.
