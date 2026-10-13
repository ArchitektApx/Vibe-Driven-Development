# Planner on Cursor

- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as `/grill-with-docs`
  or `/to-tickets .scratch/<slug>/spec.md`, and `/vdd-<role>` for a VDD
  skill, unprefixed, such as `/vdd-setup`.
- **The wait.** Run the `doorbell wait` command a `Next:` line names as a
  background shell; the Session wakes when the shell finishes. The IDE Agent
  and the CLI may each wake twice for one wait: on the second, `take` finds no
  new Doorbell, and while a wait of yours still runs its `Next:` says to end
  your turn rather than start another. Run `ring` and `take` in the foreground
  with a `block_until_ms` of 120000, so each finishes inside its call: in the
  Cursor CLI, a shell moved to the background that finishes while your turn
  runs stops every later wake in this Session.
- **A resume.** In the Cursor CLI, `agent --continue`, `agent --resume` and
  `agent resume` resume a Session; in the IDE, a reopened chat does. When the
  user names one of them, or tells you this Session was resumed, run
  `doorbell take --resumed` first, as `SKILL.md` says.
- **A refused command.** When a sandbox refuses a command, rerun it once with
  the Shell call's request to run outside the sandbox. When that is denied
  too, stop with one line naming the command and what it was for; a wait
  falls back to hand relay instead.

Trust your live tools over this file when they disagree.
