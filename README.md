<div align="center">

# Vibe Driven Development

**Separate agent sessions that plan, review the plan, implement, and review the code. Each one grades the other's homework, never its own.**

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
  - [📐 Phase 1: The Plan / Plan-Review loop](#-phase-1-the-plan--plan-review-loop)
  - [🔧 Phase 2: The Coder / Code-Review loop](#-phase-2-the-coder--code-review-loop)
  - [🚢 Phase 3: Ship](#-phase-3-ship)
- [💡 Tips](#-tips)

## 🎯 Why this works

A single agent session grades its own homework. It plans, implements, and reviews with the same context, the same blind spots, and the same incentive to declare itself done. Splitting the work across separate sessions fixes that:

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
- `/setup-matt-pocock-skills`, run once per repository, answering **Local markdown** when it asks which issue tracker to use. That is what puts the spec and the tickets in `.scratch/<feature-slug>/`, where the Roles look for them.

> [!TIP]
> **Optional:** Claude Code 2.1.224+ on macOS or Linux. That is what lets one session ring the next one's doorbell instead of you copying a line between terminals. Everything works without it; the Roles print the line for you to paste.

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

The installer asks which skills to take and which agents to install them for. Take all eight `vdd-*` skills, and take all of Matt Pocock's collection: the Roles need seven skills from it, and installing the whole set is what lets `/vdd:vdd-setup` verify your install without asking you to test it by hand. Run `/setup-matt-pocock-skills` once per repository afterwards, and pull updates later with `npx skills update`.

> [!NOTE]
> If your agent does not support skills at all, the skill files are ordinary Markdown: paste the body of the relevant `skills/vdd-*/SKILL.md` into your session as a prompt.

This repository is developed with its own workflow; `CONTEXT.md` and `docs/adr/` are the glossary and decision records it produced. See `AGENTS.md`.

## 🔁 Workflow

### 📐 Phase 1: The Plan / Plan-Review loop

#### Model selection

The Planner burns the most tokens on context: it reads and explores the codebase, then drafts. It can run on a lower grade model or thinking level. The Plan-Reviewer reads far less but needs sharper judgment, so give it a higher grade model or thinking level than the Planner.

| Session | Model | Thinking Level |
|---------|-------|----------------|
| 🧠 Planner | Claude Opus 5 | High |
| 🔍 Plan-Reviewer | Claude Opus 5 | X-High |

or even better:

| Session | Model | Thinking Level |
|---------|-------|----------------|
| 🧠 Planner | Claude Opus 5 | High |
| 🔍 Plan-Reviewer | Claude Fable 5 | X-High |

The same applies to the Coder and Code-Reviewer in Phase 2.

VDD itself names no model: `vdd-orchestrator` passes one to a hosted Role
only when it finds a choice for that Role's kind of work in your own
user-level steering file, and otherwise lets the child inherit whatever the
host gives it. The tables above are what to put in that file, not a setting
inside this plugin.

#### Starting the loop

Open the first session and run `/vdd:vdd-start-loop`. It runs the environment check, asks you for a short name for the repository and a kebab-case slug for this piece of work, confirms the base branch and the feature branch, asks once whether an open minor should hold up Sign-off (`fix`, or `leave` them listed), asks once whether VDD should open the PR at the end of the Workflow (open it, ask again at Sign-off, or leave it manual), and writes all of it plus the two session names to `LOOP.md`. Both answers go into that file with the rest, and every Role reads it first, so none of them has to ask you again.

It then prints the line that renames this session to the Planner, previews the line that starts the Orchestrator, and hands over to the Planner in the same session.

#### Sessions, names and Doorbells 🔔

`LOOP.md` names two sessions, as `<repository>-<slug>-<Role>`, for example `VDD-new-release-Orchestrator`. You rename this one to the Planner with `/rename <name>`; no agent can rename its own session, which is why the Planner asks you to. You open the Orchestrator yourself, once, with `claude -n <name>` then `/vdd:vdd-orchestrator`, when the Planner rings its first Doorbell. From there the Orchestrator hosts the Plan-Reviewer, the Coder and the Code-Reviewer as subagents, each in a fresh context, and later the PR-Author in its own session; none of them is a session you open.

A Role that finishes its turn rings its counterpart's doorbell instead of waiting for you: the Planner rings the Orchestrator, and the Orchestrator relays every Plan-Reviewer round back to the Planner. The message is deliberately dull: which working file was written, which round, and how many open findings per severity. The receiving end reads the file and ignores the message text, so nothing leaks between the two contexts, which is the whole point of running them apart. Without Claude Code, or before the Orchestrator session exists (always true for round 1), the same line prints for you to paste.

#### 🧠 The Planner

The Planner is the session that:

- Identifies an issue described by the user, or
- Identifies improvements to the codebase (refactoring, adding tests, etc.)
- Grills you on it until you both agree what the work is
- Hands you `/to-spec` and then `/to-tickets`, which publish the spec and the tickets under `.scratch/<slug>/`
- Passes the published spec and every ticket through `writing-for-agents` before handing them on, so the Coder gets documents written for the way it reads

The Planner never writes code. Its deliverables are `.scratch/<slug>/spec.md` and the ticket files in `.scratch/<slug>/issues/`.

`/vdd:vdd-start-loop` starts it for you, in the same session you renamed. Its own Doorbell is what starts the Orchestrator, the first time it rings.

#### 🔍 The Plan-Reviewer

The Plan-Reviewer reviews the spec and the tickets and checks that they are complete and that every claim in them holds against the actual codebase. It also checks them against `writing-for-agents`, because the Planner cannot grade its own prose. It documents its findings and pushbacks in `PLAN-REVIEW.md` and hands that back to the Planner to work on.

It runs as a subagent hosted by the Orchestrator, in a fresh context, resumed round after round for the life of this loop. You never start it yourself.

Its Doorbells and the Planner's pass through the Orchestrator each round until the Plan-Reviewer signs off. A blocker or a major always holds up Sign-off; on `Minors: fix` the loop runs until no minor is open too, however many rounds that takes, and on `Minors: leave` the Plan-Reviewer signs off with the open minors listed. In practice this takes one to three rounds. If it takes more, the scope is probably too big: split the work.

### 🔧 Phase 2: The Coder / Code-Review loop

The Orchestrator starts this phase itself, the moment `PLAN-REVIEW.md` signs off. Nothing here is a session you open.

#### 💻 The Coder

The Coder works on the feature branch from `LOOP.md`, which defaults to the feature slug. It takes the tickets in dependency order, implements one at a time, runs its acceptance criteria, commits it, and writes what it did to `FIXES.md` for the Code-Reviewer.

Hosted by the Orchestrator, resumed round after round. If it finds itself on neither the base branch nor the feature branch, or holds a Ticket it finds wrong or impossible, it asks; the Orchestrator relays the question to you and resumes it with your answer.

#### 🧪 The Code-Reviewer

The Code-Reviewer runs Matt Pocock's `code-review` over the branch, with the spec as its reference, and then adds the checks that skill does not make: it reruns the verification itself, distrusts `FIXES.md` and the ticked checkboxes, and looks for anything in the diff the tickets did not ask for. When the branch changed a skill file, an `AGENTS.md`, a `CLAUDE.md` or anything one of those points at, it checks those lines against `writing-for-agents` as well; on a branch of ordinary source code that step costs nothing. It documents its findings and pushbacks in `CODEREVIEW.md` and hands that back to the Coder to work on.

Hosted by the Orchestrator too, the same way. `FIXES.md` and `CODEREVIEW.md` pass between the Coder and the Code-Reviewer, inside the Orchestrator's own session, until the Code-Reviewer signs off. A blocker or a major always holds up Sign-off; on `Minors: fix` the loop runs until no minor is open too, however many rounds that takes, and on `Minors: leave` the Code-Reviewer signs off with the open minors listed.

### 🚢 Phase 3: Ship

On Sign-off, the Orchestrator runs the PR-Author in its own session. It reads the `PR:` line `/vdd:vdd-start-loop` wrote to `LOOP.md`: `PR: yes` shows you the assembled body, pushes the branch and opens the PR; `PR: ask at sign-off` asks you then; `PR: manual` prints the body and touches neither the branch nor the remote. Either VDD opens the PR or you do, from the printed body.

1. If the PR-Author did not open the PR, open it yourself from the feature branch, pasting the printed body. The commits are already there, one per ticket plus any commit no ticket owned, and the working files are gitignored and stay behind.
2. Delete `LOOP.md`. Keep `.scratch/<slug>/`: the spec, the tickets and the three review files are in there, and they are that loop's record. It is gitignored, so it survives on this machine and reaches no clone; your teammates cannot see it.
3. Start the next loop with fresh sessions.

## 💡 Tips

- **One session or subagent per Role, start to finish.** Fresh means fresh per Role, not per round. Reusing the Planner session as the Coder defeats the purpose: it will implement its own assumptions instead of the spec. But a Role keeps its own session or subagent across every round of its loop, so a reviewer holds its findings and a Coder holds the reasoning behind its deviations.
- **Name your two sessions as `LOOP.md` says**, or the Doorbell between the Planner and the Orchestrator cannot find its target and you are back to copying a line between terminals.
- **A Doorbell is a bell, not a letter.** Never ask a Role to explain itself across sessions; that is what the working files are for, and it is the leak the separate sessions exist to prevent.
- **Reviewers never write code.** The moment a reviewer edits files it stops being a reviewer. Findings go in the review file, fixes go back to the other session.
- **Sign-off is explicit.** "Looks good overall" is not sign-off. Require the literal "SIGNED OFF" line so you can tell at a glance whether a loop is done.
- **Keep loops small.** One bug or one refactoring per loop. Loops that do not converge within a few rounds are a sign the work should be split.
- **Mix vendors if you can.** A Claude planner reviewed by a different model family (or the reverse) catches blind spots that two sessions of the same model share.

---

<div align="center">

Built with its own workflow. Glossary in [`CONTEXT.md`](CONTEXT.md), decisions in [`docs/adr/`](docs/adr/), house rules in [`AGENTS.md`](AGENTS.md).

MIT · [ArchitektApx](https://github.com/ArchitektApx)

</div>
