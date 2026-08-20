<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="workflow-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="workflow-light.svg">
  <img alt="The VDD workflow: you start the loop as the Planner, and an Orchestrator session hosts the rest. The Planner and its hosted Plan-Reviewer exchange the spec and PLAN-REVIEW.md until sign-off, the hosted Coder and Code-Reviewer exchange FIXES.md and CODEREVIEW.md until sign-off, then the Orchestrator hosts the PR-Author, which opens the PR or hands it to you. Every file named here lives in the tracker directory .scratch/&lt;slug&gt;/, beside the spec and the tickets; only LOOP.md sits at the repository root." src="workflow-light.svg" width="900">
</picture>

</div>

# 🔁 The Vibe Driven Development Workflow

A loop runs in three phases. Installation and requirements are in the [README](../README.md); this page walks through the loop itself.

> [!NOTE]
> You do not have to drive any of this by hand. `/vdd:vdd-start-loop` starts the loop, and from there each Role tells you the one thing it needs from you at the moment it needs it. Everything below is the detailed walkthrough of what the Roles do, for when you want to know what is happening and why.

- [📐 Phase 1: The Plan / Plan-Review loop](#-phase-1-the-plan--plan-review-loop)
- [🔧 Phase 2: The Coder / Code-Review loop](#-phase-2-the-coder--code-review-loop)
- [🚢 Phase 3: Ship](#-phase-3-ship)
- [💡 Tips](#-tips)

## 📐 Phase 1: The Plan / Plan-Review loop

### Model selection

Token cost bears hardest on the Planner and the Coder: both read and explore the codebase before they write anything. The Plan-Reviewer and the Code-Reviewer read far less and want judgement over throughput. When the Planner's or the Coder's work is complex, you may want to buy judgement there too.

| Role | Model |
|------|-------|
| 🧠 Planner | Claude Sonnet 5 |
| 🔍 Plan-Reviewer | Claude Fable 5 |

| Role | Model | Thinking Level |
|------|-------|----------------|
| 🧠 Planner | Claude Opus 5 | High |
| 🔍 Plan-Reviewer | Claude Opus 5 | X-High |

The first table varies the model, the second varies the thinking level with the model held constant across both rows. Where a reviewer runs a fast tier, the thinking level buys its judgement, as the second table's X-High row shows.

The same applies to the Coder and Code-Reviewer in Phase 2.

You open the Planner session yourself, so its row is a choice you make at launch. The Plan-Reviewer runs as a subagent you never launch, and you approve its row at Model approval, the prompt the Orchestrator prints before its first spawn.

The Orchestrator itself does no in-depth work: it spawns the hosted Roles, relays Doorbells and tracks rounds, so a mid-tier model like Claude Sonnet 5 is enough there. Its model does not limit the Roles it hosts: at Model approval it reads what your environment says about models, a file like the `AGENT_SELECTION.md` below for instance, fills the per-Role list from that, and shows you the list to approve or correct before it spawns the first one. What you approve holds for every spawn in the session.

An example, `~/.claude/AGENT_SELECTION.md`:

```markdown
# Agent Model Selection

Default subagents to haiku. Upgrade only when task requires judgment:
- haiku (claude-haiku-4-5-20251001): file reading, data gathering, counting, scanning, search, formatting
- sonnet (claude-sonnet-5): analysis, writing, simple coding tasks, moderate reasoning
- opus (claude-opus-5): architecture decisions, complex coding work including vdd-coder, novel debugging, cross-cutting synthesis
- fable (claude-fable-5): fast-output tier, vdd-plan-reviewer and vdd-code-reviewer
```

Put it where your harness reads its instructions, in the way your harness reads it; the path above is a Claude Code one. A user-level configuration is the durable place, and a repository-level one suits a quick change at the cost of a `.gitignore` entry and a change to a tracked file.

### Starting the loop

Open the first session and run `/vdd:vdd-start-loop`. It runs the environment check, asks you for a short name for the repository and a kebab-case slug for this piece of work, confirms the base branch and the feature branch, asks once whether an open minor should hold up Sign-off (`fix`, or `leave` them listed), asks once whether VDD should open the PR at the end of the Workflow (open it, ask again at Sign-off, or leave it manual), and writes all of it plus the two session names to `LOOP.md`. Every Role reads that file first, so none of them has to ask you again.

It then prints the line that renames this session to the Planner, previews the line that starts the Orchestrator, and hands over to the Planner in the same session.

### Sessions, names and Doorbells 🔔

`LOOP.md` names two sessions, as `<repository>-<slug>-<Role>`, for example `VDD-new-release-Orchestrator`. You rename this one to the Planner with `/rename <name>`; no agent can rename its own session, which is why the Planner asks you to. You open the Orchestrator yourself, once, with `claude -n <name>` then `/vdd:vdd-orchestrator`, when the Planner rings its first Doorbell. From there the Orchestrator hosts the Plan-Reviewer, the Coder and the Code-Reviewer as subagents, each in a fresh context, and later the PR-Author in its own session; none of them is a session you open.

A Role that finishes its turn rings its counterpart's doorbell instead of waiting for you: the Planner rings the Orchestrator, and the Orchestrator relays every Plan-Reviewer round back to the Planner. The message is deliberately dull: which working file was written, which round, and how many open findings per severity. The receiving end reads the file and ignores the message text, so nothing leaks between the two contexts, which is why they run apart. Without Claude Code, or before the Orchestrator session exists (always true for round 1), the same line prints for you to paste.

### 🧠 The Planner

The Planner is the session that:

- Identifies an issue described by the user, or
- Identifies improvements to the codebase (refactoring, adding tests, etc.)
- Grills you on it until you both agree what the work is
- Hands you `/to-spec` and then `/to-tickets`, which publish the spec and the tickets under `.scratch/<slug>/`
- Passes the published spec and every ticket through `writing-for-agents` before handing them on, so the Coder gets documents written for the way it reads

The Planner never writes code. Its deliverables are `.scratch/<slug>/spec.md` and the ticket files in `.scratch/<slug>/issues/`.

`/vdd:vdd-start-loop` starts it for you, in the same session you renamed. Its own Doorbell starts the Orchestrator, the first time it rings.

### 🔍 The Plan-Reviewer

The Plan-Reviewer reviews the spec and the tickets and checks that they are complete and that every claim in them holds against the actual codebase. It also checks them against `writing-for-agents`, because the Planner cannot grade its own prose. It documents its findings and pushbacks in `PLAN-REVIEW.md` and hands that back to the Planner to work on.

It runs as a subagent hosted by the Orchestrator, in a fresh context, resumed round after round for the life of this loop. You never start it yourself.

Its Doorbells and the Planner's pass through the Orchestrator each round until the Plan-Reviewer signs off. A blocker or a major always holds up Sign-off; on `Minors: fix` the loop runs until no minor is open too, however many rounds that takes, and on `Minors: leave` the Plan-Reviewer signs off with the open minors listed. In practice this takes one to three rounds. If it takes more, the scope is probably too big: split the work.

## 🔧 Phase 2: The Coder / Code-Review loop

The Orchestrator starts this phase itself, the moment `PLAN-REVIEW.md` signs off. Nothing here is a session you open.

### 💻 The Coder

The Coder works on the feature branch from `LOOP.md`, which defaults to the feature slug. It takes the tickets in dependency order, implements one at a time, runs its acceptance criteria, commits it, and writes what it did to `FIXES.md` for the Code-Reviewer.

Hosted by the Orchestrator, resumed round after round. If it finds itself on neither the base branch nor the feature branch, or holds a Ticket it finds wrong or impossible, it asks; the Orchestrator relays the question to you and resumes it with your answer.

### 🧪 The Code-Reviewer

The Code-Reviewer runs Matt Pocock's `code-review` over the branch, with the spec as its reference, and then adds the checks that skill does not make: it reruns the verification itself, distrusts `FIXES.md` and the ticked checkboxes, and looks for anything in the diff the tickets did not ask for. When the branch changed a skill file, an `AGENTS.md`, a `CLAUDE.md` or anything one of those points at, it checks those lines against `writing-for-agents` as well; on a branch of ordinary source code that step costs nothing. It documents its findings and pushbacks in `CODEREVIEW.md` and hands that back to the Coder to work on.

Hosted by the Orchestrator too, the same way. `FIXES.md` and `CODEREVIEW.md` pass between the Coder and the Code-Reviewer, inside the Orchestrator's own session, until the Code-Reviewer signs off. A blocker or a major always holds up Sign-off; on `Minors: fix` the loop runs until no minor is open too, however many rounds that takes, and on `Minors: leave` the Code-Reviewer signs off with the open minors listed.

## 🚢 Phase 3: Ship

On Sign-off, the Orchestrator runs the PR-Author in its own session. It reads the `PR:` line `/vdd:vdd-start-loop` wrote to `LOOP.md`: `PR: yes` shows you the assembled body, pushes the branch and opens the PR; `PR: ask at sign-off` asks you then; `PR: manual` prints the body and touches neither the branch nor the remote. Either VDD opens the PR or you do, from the printed body.

1. If the PR-Author did not open the PR, open it yourself from the feature branch, pasting the printed body. The commits are already there, one per ticket plus any commit no ticket owned, and the working files are gitignored and stay behind.
2. Delete `LOOP.md`. Keep `.scratch/<slug>/`: the spec, the tickets and the three review files are in there, and they are that loop's record. It is gitignored, so it stays on this machine and reaches no clone.
3. Start the next loop with fresh sessions.

## 💡 Tips

- **One session or subagent per Role, start to finish.** Fresh means fresh per Role, not per round. Reusing the Planner session as the Coder defeats the purpose: it will implement its own assumptions instead of the spec. But a Role keeps its own session or subagent across every round of its loop, so a reviewer holds its findings and a Coder holds the reasoning behind its deviations.
- **Name your two sessions as `LOOP.md` says**, or the Doorbell between the Planner and the Orchestrator cannot find its target and you are back to copying a line between terminals.
- **A Doorbell is a bell, not a letter.** Never ask a Role to explain itself across sessions; the working files are for that, and it is the leak the separate sessions exist to prevent.
- **Reviewers never write code.** The moment a reviewer edits files it stops being a reviewer. Findings go in the review file, fixes go back to the other session.
- **Sign-off is explicit.** "Looks good overall" is not sign-off. Require the literal "SIGNED OFF" line so you can tell at a glance whether a loop is done.
- **Keep loops small.** One bug or one refactoring per loop. Loops that do not converge within a few rounds are a sign the work should be split.
- **Mix vendors if you can.** A Claude planner reviewed by a different model family (or the reverse) catches blind spots that two sessions of the same model share.
