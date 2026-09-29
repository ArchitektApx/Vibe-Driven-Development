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

Trust your live tools over this file when they disagree.
