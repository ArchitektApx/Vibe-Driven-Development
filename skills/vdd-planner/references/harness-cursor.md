# Planner on Cursor

- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as `/grill-with-docs`
  or `/to-tickets .scratch/<slug>/spec.md`, and `/vdd-<role>` for a VDD
  skill, unprefixed, such as `/vdd-setup`.
- **The Orchestrator launch.** In the Cursor IDE, a new chat, then
  `/vdd-orchestrator` in it. In the Cursor CLI, `agent` in a terminal in this
  repository, then `/vdd-orchestrator` in that Session.
- **Delivering a Doorbell.** You ring and wait through the Doorbell file:
  ring and arm your wait as the Doorbell file for your platform says,
  `doorbell-file-unix.md` or on native Windows `doorbell-file-windows.md`,
  which `SKILL.md` links. Nothing
  confirms that the Orchestrator's Session is reachable, so every ring also
  prints, worded: "If the Orchestrator's Session does not wake, paste this
  into it:" followed by the exact Doorbell.
- **Round 1.** The Orchestrator reads your round-1 Doorbell from the Doorbell
  file when it starts. In place of "Paste the Doorbell below into it once it
  is up", say: "It picks up the Doorbell below from the Doorbell file; paste
  it in only if it does not start the review."
- **The wait.** Run it as a background shell; the Session wakes when the
  shell finishes. The IDE Agent and the CLI may each wake twice for one wait,
  delivering the same output again; the duplicate rule in
  the Doorbell file for your platform makes the second wake a no-op. Run the
  ring and the count in the foreground with a `block_until_ms` of 120000, so
  each finishes inside its call: in the Cursor CLI, a shell moved to the
  background that finishes while your turn runs stops every later wake in
  this Session.
- **A resume.** In the Cursor CLI, `agent --continue`, `agent --resume` and
  `agent resume` resume a Session; in the IDE, a reopened chat does. When the
  user names one of them, or tells you this Session was resumed, re-arm as
  "Your wait" in the Doorbell file for your platform says.

Trust your live tools over this file when they disagree.
