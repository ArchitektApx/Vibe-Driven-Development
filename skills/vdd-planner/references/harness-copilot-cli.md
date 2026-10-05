# Planner on Copilot CLI

- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as `/grill-with-docs`
  or `/to-tickets .scratch/<slug>/spec.md`, and `/vdd:vdd-<role>` for a VDD
  skill, such as `/vdd:vdd-setup`.
- **The Orchestrator launch.** `copilot` in a terminal in this repository,
  then `/vdd:vdd-orchestrator` in that Session.
- **Delivering a Doorbell.** You ring and wait through the Doorbell file:
  ring and arm your wait as the Doorbell file for your platform that
  `SKILL.md` links says. Nothing
  confirms that the Orchestrator's Session is reachable, so every ring also
  prints, worded: "If the Orchestrator's Session does not wake, paste this
  into it:" followed by the exact Doorbell.
- **Round 1.** The Orchestrator reads your round-1 Doorbell from the Doorbell
  file when it starts. In place of "Paste the Doorbell below into it once it
  is up", say: "It picks up the Doorbell below from the Doorbell file; paste
  it in only if it does not start the review."
- **The wait.** Run it in `async` or `detach` mode, never `sync`: a `sync`
  shell blocks the whole Session until it exits (github/copilot-cli #2533). The
  Session wakes when the shell exits.
- **A resume.** `copilot --continue` and `copilot --resume` resume a Session.
  When the user names one of them, or tells you this Session was resumed,
  re-arm as "Your wait" in the Doorbell file for your platform says.

Trust your live tools over this file when they disagree.
