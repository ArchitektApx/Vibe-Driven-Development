# Orchestrator on Codex

- **Spawn and resume.** `collaboration.spawn_agent` spawns a fresh child.
  `collaboration.followup_task` addressed to that child resumes the same child
  with its context intact.
- **The Spawn prompt's skill name.** `$vdd:vdd-<role>`:
  `$vdd:vdd-plan-reviewer`, `$vdd:vdd-coder` or `$vdd:vdd-code-reviewer`. A
  child spawned with that name in its task loads the plugin's skill.
- **The return.** A child's completion arrives as a message of type
  `FINAL_ANSWER` with a `Task name`, a `Sender` and a `Payload`. The `Payload`
  is the return to parse.
- **The context size.** Codex reports none for a subagent, in any field of the
  spawn, wait, follow-up or completion results. The no-size path of "The
  Coder's context" applies from the first Coder return: tell the user once
  that the check cannot run and that they can ask for a fresh Coder at any
  round.
- **Relaying to the Planner.** Run
  `codex queue --thread <Planner Session name> --message '<Doorbell>'` with
  escalated permissions, outside the sandbox: the default sandbox makes
  `~/.codex` read-only, and the command fails inside it. `codex queue`
  resolves the Session name when it sends, so its exit code is the
  reachability check and the delivery in one step. Exit 0 means delivered. Any
  other exit is a failed delivery: print.
- **Approval prompts.** Under default approvals, each relay raises one
  approval prompt for the escalated command. That is normal: the user's
  permission mode governs a Doorbell like any other command.
- **A busy recipient.** A Doorbell sent while the Planner's Session is in a
  turn arrives when that turn ends. It is not lost, and it interrupts nothing.
- **After `codex resume`.** A resumed Session takes no queued Doorbell until it
  has taken one turn of its own. When the user restarted this Orchestrator,
  or the Planner, with `codex resume`, tell them to send the resumed Session
  one message, or the Doorbells queued for it wait.

Trust your live tools over this file when they disagree.
