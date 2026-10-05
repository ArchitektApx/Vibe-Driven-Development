# Setup on Claude Code

- **Typed skill names.** Where you tell the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as
  `/setup-matt-pocock-skills` or `/writing-for-agents`, and `/vdd:vdd-<role>`
  for a VDD skill, such as `/vdd:vdd-start-loop`.
- **`code-review` in your skill list.** Claude Code ships a bundled
  `code-review` skill of its own, unrelated to Matt Pocock's and reviewing
  against something else, which is why a bare hit needs its description read.
  `mattpocock-skills:code-review` is the Claude Code plugin install of Matt
  Pocock's. Claude Code bundles nothing named `writing-for-agents`.
- **The Present search roots.** Search these, and no other store: your
  user skills, the project's `.claude/skills`, and the Matt Pocock plugin in
  the plugin cache, each moved by `CLAUDE_CONFIG_DIR` and
  `CLAUDE_CODE_PLUGIN_CACHE_DIR` when set. Put these lines in front of the
  search. In a POSIX shell, Git Bash on native Windows included:

  ```sh
  set -- "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills" ./.claude/skills "${CLAUDE_CODE_PLUGIN_CACHE_DIR:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins}/cache"/*/mattpocock-skills
  ```

  In PowerShell, on native Windows:

  ```powershell
  $claude = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE '.claude' }
  $claudePlugins = if ($env:CLAUDE_CODE_PLUGIN_CACHE_DIR) { $env:CLAUDE_CODE_PLUGIN_CACHE_DIR } else { Join-Path $claude 'plugins' }
  $roots = @("$claude\skills", ".\.claude\skills", "$claudePlugins\cache\*\mattpocock-skills")
  ```

  Claude Code can scrub variables from the environment of the shell it runs
  your commands in, so a `CLAUDE_CONFIG_DIR` the user set may not reach your
  shell. The search then reads the literal `~/.claude` path, and that gap is
  accepted.
- **The shared scripts check.** It applies on this Harness.

Trust your live tools over this file when they disagree.
