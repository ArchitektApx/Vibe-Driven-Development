# Code-Reviewer on Codex

- **The `code-review` sub-agents.** Spawn both with
  `collaboration.spawn_agent` and `fork_turns: "none"`, so neither inherits
  your context, then wait for them inside your turn with
  `collaboration.wait_agent`, a timeout of several minutes, until both
  completions have arrived. A sub-agent that finishes after your turn has
  ended does not wake you, and its report is lost.
- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `$<name>` for a Borrowed skill, such as
  `$setup-matt-pocock-skills`, and `$vdd:vdd-<role>` for a VDD skill.
- **A refused command.** When a sandbox refuses a command, rerun it once with
  `sandbox_permissions: "require_escalated"` on the same call. When that is
  denied too, stop with one line naming the command and what it was for, and
  return `BLOCKED`.

Trust your live tools over this file when they disagree.
