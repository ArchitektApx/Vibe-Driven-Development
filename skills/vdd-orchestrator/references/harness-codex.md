# Orchestrator on Codex

- **Naming this Session.** Act on this at start, once you have read
  `LOOP.md`: call `set_thread_title` (`mcp__codex_tui__set_thread_title`, a
  deferred tool you find by tool search) with the title set to the
  Orchestrator Session name and no `threadId`, which names this thread. Where
  the tool is missing or the call fails, tell the user to type
  `/rename <Orchestrator Session name>` in this Session, the real name filled
  in.
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
  Coder's context" applies from the first Coder return.
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
- **A lost or doubled Session name.** `/new` and `/clear` start a new thread
  with no name, and the old thread keeps the Session name, so a Doorbell sent
  to that name goes to the old thread. A fork copies the thread's name, so
  `codex queue --thread <name>` fails with "Multiple sessions match" until
  one of the two threads is renamed or archived. The fix in each case is
  `/rename <Session name>` in the thread that should carry the name, once
  the other thread carrying it is archived or renamed: two active threads
  with one name fail as a fork does. When a delivery fails or goes quiet
  after one of these, tell the user this fix.

Trust your live tools over this file when they disagree.
