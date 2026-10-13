# Planner on Copilot CLI

- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as `/grill-with-docs`
  or `/to-tickets .scratch/<slug>/spec.md`, and `/vdd:vdd-<role>` for a VDD
  skill, such as `/vdd:vdd-setup`.
- **The wait.** Run the `doorbell wait` command a `Next:` line names in
  `async` or `detach` mode, never `sync`: a `sync` shell blocks the whole
  Session until it exits (github/copilot-cli #2533). The Session wakes when
  the shell exits.
- **A resume.** `copilot --continue` and `copilot --resume` resume a Session.
  When the user names one of them, or tells you this Session was resumed,
  run `doorbell take` first, as `SKILL.md` says.
- **A refused command.** Copilot CLI offers no way to rerun a command outside
  its sandbox, so a refusal counts as a denial: stop with one line naming the
  command and what it was for; a wait falls back to hand relay instead.

Trust your live tools over this file when they disagree.
