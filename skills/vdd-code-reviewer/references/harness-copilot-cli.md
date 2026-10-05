# Code-Reviewer on Copilot CLI

- **Which `code-review` to use.** Matt Pocock's `code-review` skill, run with
  the `skill` tool. The `task` tool offers a `code-review` agent type: that
  is Copilot CLI's own reviewer and not Matt Pocock's skill, so do not spawn
  it for step 1.
- **The `code-review` sub-agents.** Spawn both in one message with the
  `task` tool, `agent_type: "general-purpose"` and no `mode`. Without a
  `mode` the call is synchronous: it returns with the report inside your
  turn.
- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/setup-matt-pocock-skills`, `/vdd:vdd-start-loop`.

Trust your live tools over this file when they disagree.
