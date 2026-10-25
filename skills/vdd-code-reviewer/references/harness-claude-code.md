# Code-Reviewer on Claude Code

- **Which `code-review` to try first.** `mattpocock-skills:code-review` in
  your skill list is the Claude Code plugin install of Matt Pocock's skill.
  Use it when it is there. Otherwise a bare `code-review` whose description
  names "Standards" and "Spec" is a skills-CLI install
  (`.claude/skills/code-review/` or `.agents/skills/code-review/`, frontmatter
  `name: code-review`); a project or personal skill of that name replaces the
  bundled one, so there the bare name is Matt's.
- **The bundled `code-review`.** Claude Code ships a `code-review` skill of its
  own, which reviews against something else. A bare `code-review` with any
  other description is that one.
- **The `code-review` sub-agents.** Spawn both in one message with the Agent
  tool's `run_in_background` set to the JSON boolean `false`, unquoted: a
  quoted `"false"` starts them in the background. They run side by side, and
  the calls return with both reports inside your turn. If a call returns
  that its agent was launched in the background anyway, go on to Step 2 while
  they work. When you have nothing left to do and a report is still out, end
  your turn with no Doorbell: Claude Code holds you and resumes you with each
  report as it arrives. Never sleep, poll, or start a `Monitor` or a
  background command to wait for them.
- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/setup-matt-pocock-skills`, `/vdd:vdd-start-loop`.
- **A refused command.** When a sandbox refuses a command, rerun it once with
  `dangerouslyDisableSandbox: true` on the same call. When that is denied
  too, stop with one line naming the command and what it was for, and return
  `BLOCKED`.

Trust your live tools over this file when they disagree.
