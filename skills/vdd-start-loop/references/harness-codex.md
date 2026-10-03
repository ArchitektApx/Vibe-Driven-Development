# Start-Loop on Codex

- **Typed skill names.** Where you tell the user to invoke a skill, give the
  form they type: `$<name>` for a Borrowed skill, `$vdd:vdd-<role>` for a VDD
  skill, such as `$vdd:vdd-planner`.
- **The Fresh Coder question.** Skip it and write `Fresh Coder: never`. Codex
  reports no context size for a subagent, so the Orchestrator would have no
  size to hold against a limit. Say in the closing summary that the user can
  ask the Orchestrator for a fresh Coder at any round.
- **Naming this Session.** Call `set_thread_title`
  (`mcp__codex_tui__set_thread_title`, a deferred tool you find by tool
  search) with the title set to the Planner Session name and no `threadId`,
  which names this thread. A missing tool or a failed call is the case where
  the way fails.

Trust your live tools over this file when they disagree.
