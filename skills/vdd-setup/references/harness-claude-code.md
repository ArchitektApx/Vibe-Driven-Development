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
- **The Present search roots.** Search these, and no other store:
  - `~/.claude/skills`
  - `./.claude/skills`
  - `~/.claude/plugins/cache/*/mattpocock-skills`

  `CLAUDE_CONFIG_DIR`, when set, replaces `~/.claude` in `~/.claude/skills`
  and in the cache root. `CLAUDE_CODE_PLUGIN_CACHE_DIR`, when set, replaces
  `~/.claude/plugins` in the cache root, and wins over `CLAUDE_CONFIG_DIR`
  there. Claude Code can scrub variables from the environment of the shell it
  runs your commands in, so a `CLAUDE_CONFIG_DIR` the user set may not reach
  your shell. The search then reads the literal `~/.claude` path, and that gap
  is accepted.
- **The shared scripts check.** It applies on this Harness.

Trust your live tools over this file when they disagree.
