# Planner on Claude Code

- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as `/grill-with-docs`
  or `/to-tickets .scratch/<slug>/spec.md`, and `/vdd:vdd-<role>` for a VDD
  skill, such as `/vdd:vdd-setup`.
- **The `code-review` reading.** In the wiring check, a hit on
  `mattpocock-skills:code-review` counts: it is the plugin install. Claude
  Code ships a bundled `code-review` skill of the same name that reviews
  against something else, which is why a bare hit needs its description read.
- **The Orchestrator launch.** `claude` in a terminal in this repository,
  then `/vdd:vdd-orchestrator` in that Session.
- **Delivering a Doorbell.** Through the Doorbell file: ring and arm your
  wait as [`doorbell-file-posix.md`](doorbell-file-posix.md) says. Nothing
  confirms that the Orchestrator's Session is reachable, so every ring also
  prints, worded: "If the Orchestrator's Session does not wake, paste this
  into it:" followed by the exact Doorbell.
- **Round 1.** The Orchestrator reads your round-1 Doorbell from the Doorbell
  file when it starts. In place of "Paste the Doorbell below into it once it
  is up", say: "It picks up the Doorbell below from the Doorbell file; paste
  it in only if it does not start the review."
- **The wait.** Run the wait form as a background Bash, with
  `run_in_background` set and an explicit `timeout` of at least 2760000 ms:
  the default timeout is below the script's 45 minutes and would end the wait
  early. The Session wakes when the Bash exits.

Trust your live tools over this file when they disagree.
