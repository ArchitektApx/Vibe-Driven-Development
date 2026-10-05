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
- **The `code-review` sub-agents.** Spawn both in one message, each Agent
  call carrying `"run_in_background": false`. Each call's result is then that
  sub-agent's report. A result saying the agent was launched asynchronously
  means the value went in as text and the sub-agent runs in the background:
  stop both with `TaskStop` and spawn them again with the boolean.
- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/setup-matt-pocock-skills`, `/vdd:vdd-start-loop`.

Trust your live tools over this file when they disagree.
