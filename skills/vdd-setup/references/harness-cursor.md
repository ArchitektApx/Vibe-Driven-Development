# Setup on Cursor

- **Typed skill names.** Where you tell the user to invoke a skill, give the
  form they type: `/<name>` for a Borrowed skill, such as
  `/setup-matt-pocock-skills` or `/writing-for-agents`, and `/vdd-<role>` for
  a VDD skill, unprefixed, such as `/vdd-start-loop`.
- **`code-review` in your skill list.** Matt Pocock's is the one whose
  description names "Standards" and "Spec". Cursor also lists skills it
  imports from Claude Code and Codex installs, so read the description of each
  `code-review` hit.
- **The Present search roots.** The Cursor IDE and the Cursor CLI read the
  same stores. Search these, and no other store:
  - `~/.agents/skills`
  - `./.agents/skills`
  - `~/.cursor/skills`
  - `./.cursor/skills`
  - `~/.cursor/plugins/cache`

  No variable relocates them. Leave out every `.claude` and `.codex` store:
  Cursor reads those only through the IDE's third-party import, which the
  user can turn off. Setup does not read that toggle, because no shell can
  tell the IDE's Agent from the CLI, and the CLI ignores the toggle.
- **The shared scripts check.** It applies on this Harness.

Trust your live tools over this file when they disagree.
