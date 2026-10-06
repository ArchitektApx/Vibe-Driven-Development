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
  same stores: the skills-CLI stores, Cursor's own skill stores and its
  plugin cache. Search these, and no other store. Put these lines in front of
  the search. In a POSIX shell, Git Bash on native Windows included:

  ```sh
  set -- "$HOME/.agents/skills" ./.agents/skills "$HOME/.cursor/skills" ./.cursor/skills "$HOME/.cursor/plugins/cache"
  ```

  In PowerShell, on native Windows:

  ```powershell
  $roots = @("$env:USERPROFILE\.agents\skills", ".\.agents\skills", "$env:USERPROFILE\.cursor\skills", ".\.cursor\skills", "$env:USERPROFILE\.cursor\plugins\cache")
  ```

  No variable relocates them. Every `.claude` and `.codex` store stays out:
  Cursor reads those only through the IDE's third-party import, which the
  user can turn off. Setup does not read that toggle, because no shell can
  tell the IDE's Agent from the CLI, and the CLI ignores the toggle.
- **Resolvable with no search hit.** Continue check 1's line for this case
  with: "This is likely Claude Code's or Codex's store, read through Cursor's
  third-party import, which the IDE setting can turn off. A skills-CLI install
  that selects Cursor does not depend on it."
- **The shared scripts check.** It applies on this Harness.

Trust your live tools over this file when they disagree.
