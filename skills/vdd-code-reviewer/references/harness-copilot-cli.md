# Code-Reviewer on Copilot CLI

- **`code-review` and its sub-agents.** Run Matt Pocock's `code-review`
  skill with the `skill` tool. It hands its two reviews to sub-agents: spawn
  both in one message with the `task` tool, `agent_type: "general-purpose"`
  and no `mode`, so each call is synchronous and returns with its report
  inside your turn. `general-purpose` is the agent type for both; the `task`
  tool's `code-review` type is Copilot CLI's own reviewer, which reviews
  against something else.
- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `/setup-matt-pocock-skills`, `/vdd:vdd-start-loop`.

Trust your live tools over this file when they disagree.
