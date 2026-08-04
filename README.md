# Vibe Driven Development

tl;dr: make Claude Code / Codex / GitHub Copilot CLI write better code by using multiple sessions that adversarially check each other's work.

> [!WARNING]
> This is a **work in progress** based on my experience and observations with Claude Code.
> It is not yet (battle) tested and may not work as expected.
> Use at your own risk.
> Feedback is welcome.
> Please report any issues you encounter.

## Why this works

A single agent session grades its own homework. It plans, implements, and reviews with the same context, the same blind spots, and the same incentive to declare itself done. Splitting the work across separate sessions fixes that:

- **Fresh context.** The reviewer has not seen the planner's reasoning, so it has to verify claims against the actual codebase instead of nodding along.
- **Adversarial framing.** A session prompted to find problems finds problems. A session prompted to "implement and review" finds excuses.
- **Written handoffs.** Forcing the plan, the implementation notes, and the review into files makes every claim checkable and keeps each session's context small.

The result is a loop that converges: plan, push back, revise, sign off, implement, push back, fix, sign off.

## Requirements

- A repository to work in
- The ability to run two agent sessions side by side (two terminals is enough)
- Matt Pocock's [skills](https://github.com/mattpocock/skills). The Planner depends on `grill-with-docs` and `improve-codebase-architecture`. In Claude Code: `/plugin install mattpocock-skills` (official marketplace). Both are user-invoked skills: their author blocked agents from starting them, so the Planner will ask you to type the slash command yourself at the right moment. No other Role needs them.

## Install (Claude Code)

This repository is a Claude Code plugin marketplace. The `vdd` plugin ships one skill per role, so you start each session with a single slash command.

```
/plugin marketplace add ArchitektApx/Vibe-Driven-Development
/plugin install vdd@vibe-driven-development
```

| Role | Skill |
|------|-------|
| Environment check | `/vdd:vdd-setup` |
| Planner | `/vdd:vdd-planner` |
| Plan-Reviewer | `/vdd:vdd-plan-reviewer` |
| Coder | `/vdd:vdd-coder` |
| Code-Reviewer | `/vdd:vdd-code-reviewer` |

Run `/vdd:vdd-setup` once per repository: it verifies the required skills are installed, the gitignore entries from Phase 0 exist, and no stale working files are left over from a previous loop.

## Install (Cursor, GitHub Copilot CLI, Codex, other agents)

Other agents can use the same skills via the [skills CLI](https://github.com/vercel-labs/skills), which writes them into your repo as ordinary files you own:

```bash
npx skills@latest add ArchitektApx/Vibe-Driven-Development
npx skills@latest add mattpocock/skills
```

The installer asks which skills to take and which agents to install them for. Take all five `vdd-*` skills, and take all of Matt Pocock's collection: the Planner needs `grill-with-docs` and `improve-codebase-architecture`, and installing the whole set is what lets `/vdd:vdd-setup` verify your install without asking you to test it by hand. Run `/setup-matt-pocock-skills` once per repository afterwards, and pull updates later with `npx skills update`.

If your agent does not support skills at all, the skill files are ordinary Markdown: paste the body of the relevant `skills/vdd-*/SKILL.md` into your session as a prompt.

This repository is developed using its own workflow; `CONTEXT.md` and `docs/adr/` are the glossary and decision records that produces. See `CLAUDE.md`.

## Workflow

### Phase 0: Prepare the Environment

`.gitignore` the working files the loops below will create. They are scratch space for the sessions, not part of your project.

```gitignore
PLAN.md
PLAN-REVIEW.md
FIXES.md
CODEREVIEW.md
```

With the plugin installed, `/vdd:vdd-setup` handles this phase for you, including checking that the required Matt Pocock skills are installed.

### Phase 1: The Plan / Plan-Review Loop

#### Model Selection

The Planner burns the most tokens on context: it reads the codebase, explores, and drafts. It can run on a lower grade model or thinking level. The Plan-Reviewer reads far less but needs sharper judgment, so give it a higher grade model or thinking level than the Planner.

| Session | Model | Thinking Level |
|---------|-------|----------------|
| Planner | Claude Opus 5 | High |
| Plan-Reviewer | Claude Opus 5 | X-High |

or even better:

| Session | Model | Thinking Level |
|---------|-------|----------------|
| Planner | Claude Opus 5 | High |
| Plan-Reviewer | Claude Fable 5 | X-High |

The same applies to the Coder and Code-Reviewer in Phase 2.

#### The Planner

The Planner is a session that performs the following tasks:

- Identify an issue described by the user, or
- Identify improvements to the codebase (refactoring, adding tests, etc.)
- Write a detailed plan for a future coder session to implement.

The Planner never writes code. Its only deliverable is `PLAN.md`.

Start the session with `/vdd:vdd-planner` and describe the bug or improvement.

#### The Plan-Reviewer

The Plan-Reviewer is a session that reviews `PLAN.md` and makes sure it is complete, accurate, and grounded in the actual codebase. It documents its findings and pushbacks in `PLAN-REVIEW.md` and hands that back to the Planner to work on.

Start the session with `/vdd:vdd-plan-reviewer`.

Hand `PLAN.md` and `PLAN-REVIEW.md` between the two sessions until all issues are resolved and the Plan-Reviewer signs off. In practice this takes one to three rounds. If it takes more, the scope is probably too big: split the plan.

### Phase 2: The Coder / Code-Review Loop

#### The Coder

The Coder is a session that implements the plan and writes its comments, findings, and deviations to `FIXES.md`, which is passed to the Code-Reviewer.

Start the session with `/vdd:vdd-coder`.

#### The Code-Reviewer

The Code-Reviewer is a session that reviews the actual changes against the plan and makes sure `FIXES.md` is complete and accurate. It documents its findings and pushbacks in `CODEREVIEW.md` and hands that back to the Coder to work on.

Start the session with `/vdd:vdd-code-reviewer`.

Hand `FIXES.md` and `CODEREVIEW.md` between the two sessions until all issues are resolved and the Code-Reviewer signs off.

### Phase 3: Ship

Once the Code-Reviewer has signed off:

1. Commit the changes (the working `.md` files are gitignored and stay behind).
2. Delete `PLAN.md`, `PLAN-REVIEW.md`, `FIXES.md`, and `CODEREVIEW.md`, or leave them to be overwritten by the next run.
3. Start the next loop with fresh sessions.

## Tips

- **One session per Role, start to finish.** Fresh means fresh per Role, not per round. Reusing the Planner session as the Coder defeats the purpose: it will implement its own assumptions instead of the plan. But a Role keeps its own session across every round of its loop, so a reviewer holds its findings and a Coder holds the reasoning behind its deviations. Each Role starts cold exactly once.
- **Reviewers never write code.** The moment a reviewer edits files it stops being a reviewer. Findings go in the review file, fixes go back to the other session.
- **Sign-off is explicit.** "Looks good overall" is not sign-off. Require the literal "SIGNED OFF" line so you can tell at a glance whether a loop is done.
- **Keep plans small.** One bug or one refactoring per loop. Loops that do not converge within a few rounds are a sign the plan should be split.
- **Mix vendors if you can.** A Claude planner reviewed by a different model family (or the reverse) catches blind spots that two sessions of the same model share.
