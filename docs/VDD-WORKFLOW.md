# Vibe Driven Development - Workflow and Skills

Install and requirements are in the [README](../README.md). You do not drive the loop by hand: `/vdd:vdd-start-loop` starts it, and each Role asks for what it needs when it needs it.

## 📚 Contents

- [🧩 Harnesses](#-harnesses)
- [🔁 The Vibe Driven Development Workflow](#-the-vibe-driven-development-workflow)
  - [🚀 Starting a loop](#-starting-a-loop)
  - [🔔 Sessions and Doorbells](#-sessions-and-doorbells)
  - [🤖 Choosing models](#-choosing-models)
  - [📐 Phase 1: The Plan / Plan-Review loop](#-phase-1-the-plan--plan-review-loop)
  - [🔧 Phase 2: The Coder / Code-Review loop](#-phase-2-the-coder--code-review-loop)
  - [🚢 Phase 3: Ship](#-phase-3-ship)
- [🧭 Before the loop](#-before-the-loop)
  - [💡 The Brainstormer](#-the-brainstormer)
  - [🗺 The Wayfinder](#-the-wayfinder)
- [💡 Tips](#-tips)

## 🧩 Harnesses

The commands on this page are Claude Code's. On the other Harnesses:

| | Claude Code | Codex | Cursor | Copilot CLI |
|-|-------------|-------|--------|-------------|
| Skill | `/vdd:vdd-start-loop` | `$vdd:vdd-start-loop` | `/vdd-start-loop` | `/vdd:vdd-start-loop` |
| Open the Orchestrator | `claude` | `codex --no-daemon` | a new chat, or `agent` | `copilot` |
| Doorbell | rings by itself | rings by itself once you trust VDD's hook in `/hooks`, and again after an update | rings by itself | rings by itself |

If the other session does not wake, paste the line the Role prints.

## 🔁 The Vibe Driven Development Workflow

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="workflow-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="workflow-light.svg">
  <img alt="The VDD workflow: you start the loop as the Planner, and an Orchestrator session runs the rest. The Planner and the Plan-Reviewer the Orchestrator hosts exchange the spec and PLAN-REVIEW.md until sign-off, the hosted Coder and Code-Reviewer exchange FIXES.md and CODEREVIEW.md until sign-off, and VDD folds the branch. Then the Orchestrator invokes the PR-Author, which opens the PR or hands it to you, unless the loop's PR: line is no. Every file named here lives in the tracker directory .scratch/&lt;slug&gt;/, beside the spec, the tickets and the Loop file." src="workflow-light.svg" width="900">
</picture>

</div>

### 🚀 Starting a loop

`/vdd:vdd-start-loop` runs the environment check, which looks at the borrowed skills, the issue tracker and your `.gitignore` and walks you through anything missing. Then it asks for:

- a kebab-case slug for the work
- the feature branch: the slug, unless you name another branch
- whether an open minor holds up Sign-off (`fix`, or `leave` it listed)
- whether VDD opens the PR at the end (yes, ask at Sign-off, manual, or no)

The loop branches from the branch you have checked out. Your answers go into the Loop file, `.scratch/<slug>/loop.md`, which every Role reads first, so none asks again. If an earlier loop used the slug, you can continue it, start fresh (the old directory moves to `.scratch/<slug>-2/`, nothing is deleted) or pick another slug. Then your session becomes the Planner.

### 🔔 Sessions and Doorbells

The session you started the loop in is the Planner. When the Planner rings its first Doorbell, open a second session in the repository and run `/vdd:vdd-orchestrator <slug>`, as the Planner prints it. The Orchestrator hosts the Plan-Reviewer, the Coder and the Code-Reviewer as subagents, each in a fresh context, and invokes the PR-Author at the end. You open no other session.

A Role that finishes its turn rings its counterpart instead of waiting for you: the Planner rings the Orchestrator, and the Orchestrator relays each Plan-Reviewer round back. After 45 minutes a waiting session may ask whether to keep waiting.

### 🤖 Choosing models

The Planner and the Coder explore the codebase before they write, so token cost bears hardest on them. The reviewers read less and need judgment. Two ways to split it:

| Role | Vary the model | Vary the thinking level |
|------|----------------|-------------------------|
| 🧠 Planner, 💻 Coder | Claude Sonnet 5.5 | Claude Opus 5.5, Medium |
| 🔍 Plan-Reviewer, 🧪 Code-Reviewer | Claude Opus 5.5 | Claude Opus 5.5, High |

When the Planner's or the Coder's work is complex, give it the stronger model too.

You pick the Planner's model when you open its session. The Orchestrator follows what the VDD tool prints, so a mid-tier model like Claude Sonnet 5.5 is enough for it. Before its first spawn it shows Model approval: a model for each hosted Role, taken from what your environment says about models, such as the file below. You approve or correct the list once, and it holds for the whole session.

With Model approval comes one question per loop: how the Coder continues between rounds. It can start fresh every round, be resumed, or, on Claude Code, start fresh once its token count passes a limit. The reviewers are resumed unless you ask otherwise, and you can ask the Orchestrator to respawn any hosted Role at any round.

An example, `~/.claude/AGENT_SELECTION.md`:

```markdown
# Agent Model Selection

Choose each subagent's model by the tier the task fits. When a task sits
between two tiers, take the higher one.

- haiku (claude-haiku-5-5): mechanical tasks with a clear answer, such as
  searching, reading files, counting and formatting.
- sonnet (claude-sonnet-5-5): scoped tasks whose goal and approach are
  settled, such as a clearly specified change, tests or docs. The vdd-coder
  on routine work.
- opus (claude-opus-5-5): tasks that need judgment, such as code and plan
  review, architecture and debugging an unclear cause. The vdd-plan-reviewer,
  the vdd-code-reviewer, and the vdd-coder on complex work.
```

Put the file where your Harness reads its instructions; the path above is Claude Code's. A user-level file covers every repository. A repository-level one needs a `.gitignore` entry or becomes a change to a tracked file.

### 📐 Phase 1: The Plan / Plan-Review loop

#### 🧠 The Planner

The Planner takes the problem you bring, or asks what it is when you bring none, and grills you until you agree what the work is. It then hands you `/to-spec` and `/to-tickets`, which publish `.scratch/<slug>/spec.md` and the tickets in `.scratch/<slug>/issues/`. It passes both through `writing-for-agents`, so the Coder gets documents written for the way it reads. The Planner never writes code.

#### 🔍 The Plan-Reviewer

The Plan-Reviewer checks that the spec and the tickets are complete and that every claim in them holds against the codebase. It checks their prose against `writing-for-agents`, because the Planner cannot grade its own. Its findings go to `PLAN-REVIEW.md`, which holds only the findings still open, and rounds pass through the Orchestrator until it signs off.

A blocker or a major always holds up Sign-off. On `Minors: fix` the loop runs until no minor is open; on `Minors: leave` the reviewer signs off with the open minors listed. One to three rounds is normal. More means the scope is too big: split the work.

### 🔧 Phase 2: The Coder / Code-Review loop

The Orchestrator starts this phase when `PLAN-REVIEW.md` signs off. You open nothing.

#### 💻 The Coder

The Coder works on the loop's feature branch and takes the tickets in dependency order: it implements one, runs its acceptance criteria, commits it in your repository's commit style, and records what it did in `FIXES.md`. In later rounds it adds new commits instead of rewriting earlier ones, and `FIXES.md` answers each open finding: fixed, or pushed back with a reason. When a ticket looks wrong or impossible, the Coder asks; the Orchestrator relays the question to you and your answer back.

#### 🧪 The Code-Reviewer

The Code-Reviewer runs Matt Pocock's `code-review` over the branch against the spec, then adds what that skill does not do: it reruns the verification itself, distrusts `FIXES.md` and the ticked checkboxes, and flags anything in the diff no ticket asked for. When the branch changes agent instructions (a skill file, an `AGENTS.md`, a `CLAUDE.md` or a file one of those points at), it checks them against `writing-for-agents`. Its findings go to `CODEREVIEW.md`, which holds only the findings still open, each with the Coder's answer under it, and rounds run until Sign-off under the same rule as Phase 1.

### 🚢 Phase 3: Ship

On each code Sign-off the Orchestrator folds the branch without asking: each later round's fix moves into the commit that wrote the lines it changes. A fix with no such commit, or one that would clash with a later commit, stays as its own commit with the Coder's message. The fold moves the branch only when the result holds exactly what the Code-Reviewer signed off. Otherwise it leaves the branch as reviewed and tells you why, for example when the branch was already pushed and someone may have fetched it.

Then the Orchestrator runs the PR-Author, which follows the Loop file's `PR:` line:

- `PR: yes` shows you the title and body, and on your yes pushes the branch and opens the PR.
- `PR: ask at sign-off` asks whether to open the PR or leave it to you.
- `PR: manual` closes the loop, prints the title and body for you, and touches neither the branch nor the remote.
- `PR: no` skips the PR-Author. The branch stays local and no body is printed.

When VDD cannot open the PR itself, it tells you why and leaves you the title and body to open it by hand.

After the loop:

1. If the PR is not open, open it from the feature branch with the printed body. The branch holds one commit per ticket, plus any fix no ticket owned.
2. Read `.scratch/<slug>/RECAP.md` for how the loop went: the rounds, each ticket, every closed finding with what was wrong and how it was resolved, and the commits each final commit was built from. It stays on this machine, beside the Loop file, the spec and the tickets.
3. Start the next loop with fresh sessions.

#### ↩️ Sending findings back

To fix something before you merge, a finding from an outside review for example, send it back into the signed-off loop. Write your findings in a file, each as `### <blocker|major|minor>: <reference>` followed by a body, and run in the repository:

```bash
python3 "${XDG_DATA_HOME:-$HOME/.local/share}/vdd/vdd.py" review add --slug <slug> --from <file> --write
```

On native Windows in PowerShell, start it with `py -3 "$env:LOCALAPPDATA\vdd\vdd.py"` instead. Leave out `--write` to see what it would do first. Then tell the Orchestrator, as `review add` prints. A fresh Coder takes your findings, the Code-Reviewer reviews its fixes, and the fold runs again at the next Sign-off. If the PR is already open, the fixes stay as their own commits and the PR-Author pushes them to it.

## 🧭 Before the loop

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="before-the-loop-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="before-the-loop-light.svg">
  <img alt="Before the loop: the Brainstormer takes rough ideas to decided or dropped in .scratch/_brainstorming/. A decided idea that fits one loop goes to /vdd:vdd-start-loop; one too big for a loop goes to the Wayfinder, which charts it into a series of loops and writes one handoff per loop under .scratch/&lt;effort&gt;/handoffs/. You can start at any of the three." src="before-the-loop-light.svg" width="900">
</picture>

</div>

Two optional Roles run in your own session before a loop. Neither starts the next Role for you: you start it in a fresh session, with the line the Brainstormer gives you or the prompt in the Wayfinder's overview.

### 💡 The Brainstormer

`/vdd:vdd-brainstormer` keeps your ideas in `.scratch/_brainstorming/`, one file per idea, with any research for an idea under `research/<slug>/`. Each idea is rated for importance, size and fog (the unknowns between you and knowing whether it works), can have parts up to three levels deep, and ends with a History of what happened to it. The Brainstormer opens with every open idea in view, so it answers your first message straight away. Like a loop, it needs `/vdd:vdd-setup` once per machine.

It talks an idea through, clears fog with the cheapest test that answers the question, and grills you with Matt Pocock's `grilling` once you can decide. An idea ends `decided` or `dropped`, with the date and the reason. A dropped idea records when it is worth reopening, so it is not argued twice. When a grilling ends in agreement, the Brainstormer asks whether to keep brainstorming or take the idea on, with `/vdd:vdd-start-loop` for one loop or the Wayfinder for an idea too big for one, and gives you the line to start it in a fresh session.

### 🗺 The Wayfinder

`/vdd:vdd-wayfinder` is for a change too big for one loop, or one whose goal is unclear. It asks for the effort's name and what it is, prints a briefing on VDD, and hands you to Matt Pocock's `wayfinder`, which charts the effort in `.scratch/<effort>/map.md` over as many sessions as it needs.

The map is done when `.scratch/<effort>/handoffs/` holds `00-overview.md` and one `NN-<slug>.md` per loop. The overview names the destination, the loops in order, the gate each loop must pass, and the rules every loop inherits. It ends with a prompt per loop: run `/vdd:vdd-start-loop`, fill in the loop number and the handoff, and paste the prompt as the problem statement. That loop's Planner reads the overview and its handoff and grills you on that loop alone.

## 💡 Tips

- **Tell a resumed Planner it was resumed.** A resumed session has stopped waiting for the Orchestrator. Your word makes the Planner wait again; otherwise you paste the next relay by hand.
- **Keep loops small.** One bug or one refactoring per loop.
- **Mix vendors if you can.** A reviewer from a different model family catches blind spots two sessions of one model share.
- **Review the codebase between loops.** Matt Pocock's `improve-codebase-architecture` is yours to run. Take the candidates you keep to the Wayfinder when there are many or the change is large, or to a loop when it is focused.
