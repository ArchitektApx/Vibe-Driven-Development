# Planner on a Harness VDD does not know

- **Typed skill names.** Where you ask the user to invoke a skill, give its
  bare name: `grill-with-docs`, `to-tickets .scratch/<slug>/spec.md`,
  `vdd-setup`.
- **The wait.** Where your tools can run a command in the background and
  wake you when it exits, run the `doorbell wait` command a `Next:` line
  names that way. Otherwise relay by hand: the user pastes the Orchestrator's
  next Doorbell into this Session, and you take it with `--pasted`.
- **A resume.** When the user tells you this Session was resumed, run
  `doorbell take --resumed` first, as `SKILL.md` says.
- **A refused command.** When a sandbox refuses a command, rerun it once
  outside the sandbox if your tools offer a way; otherwise treat the refusal
  as a denial. On a denial, stop with one line naming the command and what it
  was for; a wait falls back to hand relay instead.

Trust your live tools over this file when they disagree.
