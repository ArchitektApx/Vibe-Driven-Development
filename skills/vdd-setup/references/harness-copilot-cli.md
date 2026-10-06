# Setup on Copilot CLI

- **Typed skill names.** Where you tell the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as
  `/setup-matt-pocock-skills` or `/writing-for-agents`, and `/vdd:vdd-<role>`
  for a VDD skill, such as `/vdd:vdd-start-loop`.
- **`code-review` in your skill list.** Matt Pocock's `code-review` is the one
  in your skill list, which the `skill` tool runs. The `task` tool offers a
  `code-review` agent type: that is Copilot CLI's own reviewer and not Matt
  Pocock's skill, and it answers nothing about the collection.
- **The Present search roots.** Search these, and no other store: the
  skills-CLI stores, Copilot's own skill store and plugin directory, both
  moved by `COPILOT_HOME` when set, and the project's `.github/skills` and
  `.claude/skills`. Copilot CLI does not read `~/.agents/skills` while
  `COPILOT_HOME` is set, so the second line adds it only when `COPILOT_HOME`
  is empty or unset. Put these lines in front of the search. In a POSIX shell, Git Bash on
  native Windows included:

  ```sh
  set -- ./.agents/skills "${COPILOT_HOME:-$HOME/.copilot}/skills" ./.github/skills ./.claude/skills "${COPILOT_HOME:-$HOME/.copilot}/installed-plugins"
  [ -n "$COPILOT_HOME" ] || set -- "$@" "$HOME/.agents/skills"
  ```

  In PowerShell, on native Windows:

  ```powershell
  $copilot = if ($env:COPILOT_HOME) { $env:COPILOT_HOME } else { Join-Path $env:USERPROFILE '.copilot' }
  $roots = @(".\.agents\skills", "$copilot\skills", ".\.github\skills", ".\.claude\skills", "$copilot\installed-plugins")
  if (-not $env:COPILOT_HOME) { $roots += "$env:USERPROFILE\.agents\skills" }
  ```
- **The shared scripts check.** It applies on this Harness.

Trust your live tools over this file when they disagree.
