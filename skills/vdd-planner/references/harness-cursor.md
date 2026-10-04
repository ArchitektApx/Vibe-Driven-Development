# Planner on Cursor

- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as `/grill-with-docs`
  or `/to-tickets .scratch/<slug>/spec.md`, and `/vdd-<role>` for a VDD
  skill, unprefixed, such as `/vdd-setup`.
- **The Orchestrator launch.** In the Cursor IDE, a new chat, then
  `/vdd-orchestrator` in it. In the Cursor CLI, `agent` in a terminal in this
  repository, then `/vdd-orchestrator` in that Session.
- **Delivering a Doorbell.** Through the Doorbell file: ring and arm your
  wait as [`doorbell-file-posix.md`](doorbell-file-posix.md) says. Nothing
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
  [`doorbell-file-posix.md`](doorbell-file-posix.md) makes the second wake a
  no-op.
- **A resume.** In the Cursor CLI, `agent --continue`, `agent --resume` and
  `agent resume` resume a Session; in the IDE, a reopened chat does. When the
  user names one of them, or tells you this Session was resumed, re-arm as
  "Your wait" in [`doorbell-file-posix.md`](doorbell-file-posix.md) says.

Trust your live tools over this file when they disagree.
