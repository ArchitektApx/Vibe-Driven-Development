# Setup on Copilot CLI

- **Typed skill names.** Where you tell the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as
  `/setup-matt-pocock-skills` or `/writing-for-agents`, and `/vdd:vdd-<role>`
  for a VDD skill, such as `/vdd:vdd-start-loop`.
- **`code-review` in your skill list.** Matt Pocock's `code-review` is the one
  in your skill list, which the `skill` tool runs. The `task` tool offers a
  `code-review` agent type: that is Copilot CLI's own reviewer and not Matt
  Pocock's skill, and it answers nothing about the collection.
- **The Present search roots.** Search these, and no other store:
  - `~/.agents/skills`
  - `./.agents/skills`
  - `~/.copilot/skills`
  - `./.github/skills`
  - `./.claude/skills`
  - `~/.copilot/installed-plugins`

  `COPILOT_HOME`, when set, replaces `~/.copilot` in `~/.copilot/skills` and
  `~/.copilot/installed-plugins`, and drops `~/.agents/skills` from the list:
  Copilot CLI does not read that store while `COPILOT_HOME` is set. Leave out
  `~/.claude/skills`, which Copilot CLI has not read since 1.0.36.
- **The shared scripts check.** It applies on this Harness.

Trust your live tools over this file when they disagree.
