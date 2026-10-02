# Planner on Codex

- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `$<name>` for a Borrowed skill, such as `$grill-with-docs`
  or `$to-tickets .scratch/<slug>/spec.md`, and `$vdd:vdd-<role>` for a VDD
  skill, such as `$vdd:vdd-setup`.
- **The Orchestrator launch.** `codex` in a terminal in this repository, then
  `$vdd:vdd-orchestrator` in that Session.
- **Delivering a Doorbell.** Run
  `codex queue --thread <Orchestrator Session name> --message '<Doorbell>'`
  with escalated permissions, outside the sandbox: the default sandbox makes
  `~/.codex` read-only, and the command fails inside it. `codex queue`
  resolves the Session name when it sends, so its exit code is the
  reachability check and the delivery in one step. Exit 0 means delivered. Any
  other exit is a failed delivery: print.
- **Approval prompts.** Under default approvals, each Doorbell raises one
  approval prompt for the escalated command. That is normal: the user's
  permission mode governs a Doorbell like any other command.
- **A busy recipient.** A Doorbell sent while the Orchestrator's Session is in
  a turn arrives when that turn ends. It is not lost, and it interrupts
  nothing.
- **After `codex resume`.** A resumed Session takes no queued Doorbell until it
  has taken one turn of its own. When the user has resumed this Session or the
  Orchestrator's with `codex resume`, tell them to send the resumed Session one
  message, or the Doorbells queued for it wait.
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
