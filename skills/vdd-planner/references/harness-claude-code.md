# Planner on Claude Code

- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as `/grill-with-docs`
  or `/to-tickets .scratch/<slug>/spec.md`, and `/vdd:vdd-<role>` for a VDD
  skill, such as `/vdd:vdd-setup`.
- **The `code-review` reading.** In the wiring check, a hit on
  `mattpocock-skills:code-review` counts: it is the plugin install. Claude
  Code ships a bundled `code-review` skill of the same name that reviews
  against something else, which is why a bare hit needs its description read.
- **The wait.** Run the `doorbell wait` command a `Next:` line names in the
  background in your shell tool, Bash or PowerShell, with `run_in_background`
  set and an explicit `timeout` of at least 2760000 ms: the default timeout
  is below the wait's 45 minutes and would end it early. The Session wakes
  when the command exits.
- **A resume.** `claude --continue` and `claude --resume` resume a Session.
  When the user names one of them, or tells you this Session was resumed,
  run `doorbell take --resumed` first, as `SKILL.md` says.
- **A refused command.** When a sandbox refuses a command, rerun it once with
  `dangerouslyDisableSandbox: true` on the same call. When that is denied
  too, stop with one line naming the command and what it was for; a wait
  falls back to hand relay instead.

Trust your live tools over this file when they disagree.
