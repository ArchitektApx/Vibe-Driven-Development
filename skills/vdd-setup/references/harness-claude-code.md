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
- **The Session-name hook check.** It applies on this Harness on macOS and
  Linux. On Windows, skip it and report in one line why: the hook is a POSIX
  sh script, and its Windows form has not shipped.

Trust your live tools over this file when they disagree.
