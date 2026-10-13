# Code-Reviewer on Cursor

- **Which `code-review` to use.** The `code-review` whose description names
  "Standards" and "Spec". Cursor also lists skills it imports from Claude Code
  and Codex installs, so more than one `code-review` can appear: read the
  description of each hit.
- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/setup-matt-pocock-skills`, `/vdd-start-loop`.
- **A refused command.** When a sandbox refuses a command, rerun it once with
  the Shell call's request to run outside the sandbox. When that is denied
  too, stop with one line naming the command and what it was for, and return
  `BLOCKED`.

Trust your live tools over this file when they disagree.
