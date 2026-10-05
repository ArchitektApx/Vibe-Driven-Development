# Setup on Codex

- **Typed skill names.** Where you tell the user to invoke a skill, give the
  form they type: `$<name>` for a Borrowed skill, such as
  `$setup-matt-pocock-skills` or `$writing-for-agents`, and `$vdd:vdd-<role>`
  for a VDD skill, such as `$vdd:vdd-start-loop`.
- **`code-review` in your skill list.** Codex lists Matt Pocock's
  `code-review` under its bare name and ships no skill of that name of its
  own.
- **The Present search roots.** Search these, and no other store: the
  skills-CLI stores, Codex's own skill stores, which it still reads and has
  deprecated, and its plugin cache, the last two moved by `CODEX_HOME` when
  set. Put these lines in front of the search. In a POSIX shell, Git Bash
  on native Windows included:

  ```sh
  set -- "$HOME/.agents/skills" ./.agents/skills "${CODEX_HOME:-$HOME/.codex}/skills" ./.codex/skills "${CODEX_HOME:-$HOME/.codex}/plugins/cache"
  ```

  In PowerShell, on native Windows:

  ```powershell
  $codex = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
  $roots = @("$env:USERPROFILE\.agents\skills", ".\.agents\skills", "$codex\skills", ".\.codex\skills", "$codex\plugins\cache")
  ```
- **A skill added mid-Session.** A plugin or skill installed while a Codex
  Session runs appears only after the Session restarts. After any install or
  repair, tell the user to start a new Codex Session before they rerun this
  check.
- **The shared scripts check.** It applies on this Harness.
- **The `Stop` hook registration.** It applies on this Harness, as check 7
  in `SKILL.md` says.

Trust your live tools over this file when they disagree.
