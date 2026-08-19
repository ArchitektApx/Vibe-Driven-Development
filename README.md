<div align="center">

# Vibe Driven Development

**Separate agent sessions that plan, review the plan, implement, and review the code. Each one grades the other's homework and never its own work.**

[![Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FArchitektApx%2FVibe-Driven-Development%2Fmaster%2F.claude-plugin%2Fplugin.json&query=%24.version&prefix=v&label=plugin&color=blue)](.claude-plugin/plugin.json)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude_Code-plugin-d97757)](#-install-claude-code)
[![Works with npx skills](https://img.shields.io/badge/npx_skills-compatible-000)](#-install-cursor-github-copilot-cli-codex-other-agents)
[![Built on mattpocock/skills](https://img.shields.io/badge/built_on-mattpocock%2Fskills-8250df)](https://github.com/mattpocock/skills)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/workflow-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/workflow-light.svg">
  <img alt="The VDD workflow: you start the loop as the Planner, and an Orchestrator session hosts the rest. The Planner and its hosted Plan-Reviewer exchange the spec and PLAN-REVIEW.md until sign-off, the hosted Coder and Code-Reviewer exchange FIXES.md and CODEREVIEW.md until sign-off, then the Orchestrator hosts the PR-Author, which opens the PR or hands it to you. Every file named here lives in the tracker directory .scratch/&lt;slug&gt;/, beside the spec and the tickets; only LOOP.md sits at the repository root." src="docs/workflow-light.svg" width="900">
</picture>

</div>

**tl;dr:** an opinionated wrapper around Matt Pocock's [skills](https://github.com/mattpocock/skills). It splits planning, plan review, implementation and code review across separate Claude Code / Codex / GitHub Copilot CLI sessions that adversarially check each other's work.

> [!IMPORTANT]
> Matt Pocock's skill collection is a hard requirement: without it the Planner stops at its first handoff. See [Requirements](#-requirements).

## 📚 Contents

- [🎯 Why this works](#-why-this-works)
- [📋 Requirements](#-requirements)
- [🔌 Install (Claude Code)](#-install-claude-code)
- [🧰 Install (Cursor, GitHub Copilot CLI, Codex, other agents)](#-install-cursor-github-copilot-cli-codex-other-agents)
- [🔁 Workflow](#-workflow)

## 🎯 Why this works

A single agent session grades its own homework. It plans, implements and reviews with the same context and the same incentive to declare itself done. Splitting the work across separate sessions fixes that:

- **🧊 Fresh context.** The reviewer has not seen the planner's reasoning, so it has to verify claims against the actual codebase instead of nodding along.
- **🥊 Adversarial framing.** A session prompted to find problems finds problems. A session prompted to "implement and review" finds excuses.
- **📄 Written handoffs.** Forcing the spec, the implementation notes, and the review into files makes every claim checkable and keeps each session's context small.

The loop that comes out of this converges: plan, push back, revise, sign off, implement, push back, fix, sign off.

## 📋 Requirements

- A repository to work in
- The ability to run two agent sessions side by side (two terminals is enough): the Planner, in your foreground, and the Orchestrator, which hosts the rest.
- A coding agent with subagents. Claude Code, Cursor, Codex and GitHub Copilot CLI all have the primitive the Orchestrator needs to spawn the Plan-Reviewer, the Coder and the Code-Reviewer, each in a fresh context, and to resume the same one round after round. If your host asks for approval per command, grant session approval before you start the Workflow, so you are not answering prompts through the whole run.
- Matt Pocock's [skills](https://github.com/mattpocock/skills), the whole collection. In Claude Code: `/plugin install mattpocock-skills` (official marketplace). The Roles borrow seven of them:

  | Borrowed skill | Started by | Needed by |
  |----------------|-----------|-----------|
  | `setup-matt-pocock-skills` | 🧑 you | once per repository |
  | `grill-with-docs` | 🧑 you | Planner |
  | `improve-codebase-architecture` | 🧑 you | Planner |
  | `to-spec` | 🧑 you | Planner |
  | `to-tickets` | 🧑 you | Planner |
  | `code-review` | 🤖 the agent | Code-Reviewer |
  | `writing-for-agents` | 🤖 the agent | Planner, Plan-Reviewer, Code-Reviewer |

  All of them except `code-review` and `writing-for-agents` are user-invoked: their author blocked agents from starting them, so the Role will ask you to type the slash command yourself at the right moment. The Coder is the one Role that borrows nothing. The Plan-Reviewer borrows only `writing-for-agents`, and runs without it: a Role that cannot resolve that skill drops its writing check and says so in the file it writes.
- `/setup-matt-pocock-skills`, run once per repository, answering **Local markdown** when it asks which issue tracker to use. That answer puts the spec and the tickets in `.scratch/<feature-slug>/`, where the Roles look for them.

> [!TIP]
> **Optional:** Claude Code 2.1.224+ on macOS or Linux. It lets one session ring the next one's doorbell instead of you copying a line between terminals. Everything works without it; the Roles print the line for you to paste.

## 🔌 Install (Claude Code)

This repository is a Claude Code plugin marketplace. The `vdd` plugin ships one skill per role, so you start each session with a single slash command.

```
/plugin marketplace add ArchitektApx/Vibe-Driven-Development
/plugin install vdd@vibe-driven-development
```

| Role | Skill |
|------|-------|
| 🩺 Environment check | `/vdd:vdd-setup` |
| 🚀 Start a loop | `/vdd:vdd-start-loop` |
| 🧠 Planner | `/vdd:vdd-planner` |
| 🧭 Orchestrator | `/vdd:vdd-orchestrator` |
| 🔍 Plan-Reviewer | `/vdd:vdd-plan-reviewer` |
| 💻 Coder | `/vdd:vdd-coder` |
| 🧪 Code-Reviewer | `/vdd:vdd-code-reviewer` |
| 🚢 PR-Author | `/vdd:vdd-create-pr` |

Run `/vdd:vdd-setup` once per repository: it verifies that the borrowed skills are installed, the issue tracker is configured, the gitignore entries for `LOOP.md` and `.scratch/` exist, and no stale `LOOP.md` is left over from a previous loop. `/vdd:vdd-start-loop` runs it for you at the start of every loop.

## 🧰 Install (Cursor, GitHub Copilot CLI, Codex, other agents)

Other agents can use the same skills via the [skills CLI](https://github.com/vercel-labs/skills), which writes them into your repo as ordinary files you own:

```bash
npx skills@latest add ArchitektApx/Vibe-Driven-Development
npx skills@latest add mattpocock/skills
```

The installer asks which skills to take and which agents to install them for. Take all eight `vdd-*` skills, and take all of Matt Pocock's collection: the Roles need seven skills from it, and installing the whole set lets `/vdd:vdd-setup` verify your install without asking you to test it by hand. Run `/setup-matt-pocock-skills` once per repository afterwards, and pull updates later with `npx skills update`.

> [!NOTE]
> If your agent does not support skills at all, the skill files are ordinary Markdown: paste the body of the relevant `skills/vdd-*/SKILL.md` into your session as a prompt.

This repository is developed with its own workflow; `CONTEXT.md` and `docs/adr/` are the glossary and decision records it produced. See `AGENTS.md`.

## 🔁 Workflow

The loop runs in three phases: the Planner and the Plan-Reviewer argue the spec into shape, the Coder and the Code-Reviewer do the same with the code, and the PR-Author ships it. [**docs/VDD-WORKFLOW.md**](docs/VDD-WORKFLOW.md) walks a loop round by round, names what each Role reads, writes and rings, and carries the model recommendations and the tips that keep loops converging.

---

<div align="center">

Built with its own workflow. Glossary in [`CONTEXT.md`](CONTEXT.md), decisions in [`docs/adr/`](docs/adr/), house rules in [`AGENTS.md`](AGENTS.md).

MIT · [ArchitektApx](https://github.com/ArchitektApx)

</div>
