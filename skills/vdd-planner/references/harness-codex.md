# Planner on Codex

- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `$<name>` for a Borrowed skill, such as `$grill-with-docs`
  or `$to-tickets .scratch/<slug>/spec.md`, and `$vdd:vdd-<role>` for a VDD
  skill, such as `$vdd:vdd-setup`.
- **The wait.** A background shell cannot wake an idle Codex Session, so
  VDD's `Stop` hook waits for you. `doorbell wait` arms it and returns at
  once; then end your turn. End every turn in which you expect a Doorbell
  that way, a turn that acted on a pasted Doorbell included. Run no `wait` in
  a turn that ends asking the user a question, whose answer the hook would
  hold back until it exits, nor after the plan Sign-off. Running it again in
  a later turn is harmless: the hook claims it at most once per turn end.
- **How the wait wakes you.** When your turn ends, the hook waits on the
  Doorbell file with no model turn, then continues this Session with the
  `take` command, or `TIMEOUT`, as your next prompt: run it, or on `TIMEOUT`
  do what it says. A hook that is missing or untrusted never wakes you, and
  the line the Orchestrator printed is the fallback.
- **Esc and typed prompts.** Esc ends the hook's wait together with the turn.
  A prompt the user types while the hook waits arrives when it exits, and Esc
  sends it at once. Either way the rule above covers it: the next turn ends
  with `doorbell wait` run again.
- **A resume.** `codex resume --no-daemon` resumes a Session the user quit.
  The quit ended its turn and its hook wait: run `doorbell take` first, as
  `SKILL.md` says, and the first turn you end arms the hook again.
- **A refused command.** When a sandbox refuses a command, rerun it once with
  `sandbox_permissions: "require_escalated"` on the same call. When that is
  denied too, stop with one line naming the command and what it was for; a
  wait falls back to hand relay instead.

Trust your live tools over this file when they disagree.
