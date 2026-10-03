# Orchestrator on Copilot CLI

- **Spawn.** The `task` tool spawns a fresh subagent. Pass
  `agent_type: "general-purpose"`, `mode: "background"`, a `name`, and
  `model` where the approved list names one for the Role. `general-purpose` is
  the built-in agent that receives the repository's instructions files, which
  the Spawn prompt relies on without naming them; the other built-in agents do
  not receive them. `mode: "background"` because a synchronous `task` returns
  no reusable `agent_id`, and a child without one cannot be resumed.
- **The return.** Read it with `read_agent`, passing the child's `agent_id`.
  A background `task` returns at once, so a `read_agent` result whose
  `status` shows the child still running is not a return: read again until
  the child has finished, using the tool's wait option where it offers one,
  and only then parse the return.
- **Resume.** `write_agent` with the child's `agent_id` and the resume message
  resumes the same child with its context intact. Then read its return with
  `read_agent`, as above.
- **The Spawn prompt's skill name.** `vdd-<role>`, bare: `vdd-plan-reviewer`,
  `vdd-coder` or `vdd-code-reviewer`. A child loads it with the `skill` tool.
- **The context size.** None reaches the parent: the `task` and `read_agent`
  results carry no context or token figure. The no-size path of "The Coder's
  context" applies from the first Coder return.
- **Starting with no review file on disk.** Arm the wait at 0, as
  [`doorbell-file-posix.md`](doorbell-file-posix.md) says, so the Planner's
  round-1 Doorbell already in the Doorbell file fires at once.
- **Relaying to the Planner.** Through the Doorbell file: ring and arm your
  wait as [`doorbell-file-posix.md`](doorbell-file-posix.md) says. Nothing
  confirms that the Planner's Session is reachable, so every relay also
  prints, worded: "If the Planner's Session does not wake, paste this into
  it:" followed by the exact Doorbell.
- **The wait.** Run it in `async` or `detach` mode, never `sync`: a `sync`
  shell blocks the whole Session until it exits (github/copilot-cli #2533). The
  Session wakes when the shell exits.
- **After `copilot --continue` or `copilot --resume`.** The hosted Roles are
  gone: a background child does not survive a restart of the Session that
  spawned it. When `write_agent` or `read_agent` answers `No agent found with
  agent_id`, or before your first relay after the user resumed this Session,
  place the Workflow from disk as [`restart.md`](restart.md) says. A wait you
  armed before the restart is gone too; placing the Workflow re-arms it, as
  [`doorbell-file-posix.md`](doorbell-file-posix.md) says for a restart.

Trust your live tools over this file when they disagree.
