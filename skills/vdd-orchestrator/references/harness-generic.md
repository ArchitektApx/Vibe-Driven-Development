# Orchestrator on a Harness VDD does not know

- **Spawn and resume.** Your Harness's own subagent tools: one spawns a fresh
  subagent, the other resumes that same subagent with a message, its context
  intact.
- **The Spawn prompt's skill name.** Bare: `vdd-plan-reviewer`, `vdd-coder`
  or `vdd-code-reviewer`.
- **The wait.** Where your tools can run a command in the background and
  wake you when it exits, run the wait command a `Next:` line names that
  way. Otherwise relay by hand: the user pastes the Planner's next
  Doorbell into this Session, and you take it as a pasted line.
- **A refused command.** When a sandbox refuses a command, rerun it once
  outside the sandbox if your tools offer a way; otherwise treat the refusal
  as a denial. On a denial, stop with one line naming the command and what it
  was for; a wait falls back to hand relay instead.

Trust your live tools over this file when they disagree.
