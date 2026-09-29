# Setup on Copilot CLI

- **Typed skill names.** Where you tell the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as
  `/setup-matt-pocock-skills` or `/writing-for-agents`, and `/vdd:vdd-<role>`
  for a VDD skill, such as `/vdd:vdd-start-loop`.
- **`code-review` in your skill list.** Matt Pocock's `code-review` is the one
  in your skill list, which the `skill` tool runs. The `task` tool offers a
  `code-review` agent type: that is Copilot CLI's own reviewer and not Matt
  Pocock's skill, and it answers nothing about the collection.

Trust your live tools over this file when they disagree.
