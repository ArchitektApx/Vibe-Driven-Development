# Setup on Codex

- **Typed skill names.** Where you tell the user to invoke a skill, give the
  form they type: `$<name>` for a Borrowed skill, such as
  `$setup-matt-pocock-skills` or `$writing-for-agents`, and `$vdd:vdd-<role>`
  for a VDD skill, such as `$vdd:vdd-start-loop`.
- **`code-review` in your skill list.** Codex lists Matt Pocock's
  `code-review` under its bare name and ships no skill of that name of its
  own.
- **The Present search roots.** Search these, and no other store:
  - `~/.agents/skills`
  - `./.agents/skills`
  - `~/.codex/skills`, which Codex still reads and has deprecated
  - `./.codex/skills`
  - `~/.codex/plugins/cache`

  `CODEX_HOME`, when set, replaces `~/.codex` in `~/.codex/skills` and
  `~/.codex/plugins/cache`. `~/.agents/skills` does not move with it.
- **A skill added mid-Session.** A plugin or skill installed while a Codex
  Session runs appears only after the Session restarts. After any install or
  repair, tell the user to start a new Codex Session before they rerun this
  check.
- **The shared scripts check.** It applies on this Harness.
- **The `Stop` hook registration.** Once the shared scripts check has run,
  read [how to register the Codex `Stop` hook](codex-stop-hook.md) and follow
  it. The hook is how a waiting Codex Planner or Orchestrator wakes.

Trust your live tools over this file when they disagree.
