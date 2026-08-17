# Vibe Driven Development

tl;dr: an opinionated wrapper around Matt Pocock's [skills](https://github.com/mattpocock/skills). It splits planning, plan review, implementation and code review across separate Claude Code / Codex / GitHub Copilot CLI sessions that adversarially check each other's work. His collection is a hard requirement rather than an optional extra: without it the Planner stops at its first handoff.

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
- **Written handoffs.** Forcing the spec, the implementation notes, and the review into files makes every claim checkable and keeps each session's context small.

The result is a loop that converges: plan, push back, revise, sign off, implement, push back, fix, sign off.

## Requirements

- A repository to work in
- The ability to run two agent sessions side by side (two terminals is enough)
- Matt Pocock's [skills](https://github.com/mattpocock/skills), the whole collection. In Claude Code: `/plugin install mattpocock-skills` (official marketplace). The Roles borrow seven of them:

  | Borrowed skill | Started by | Needed by |
  |----------------|-----------|-----------|
  | `setup-matt-pocock-skills` | you | once per repository, see Phase 0 |
  | `grill-with-docs` | you | Planner |
  | `improve-codebase-architecture` | you | Planner |
  | `to-spec` | you | Planner |
  | `to-tickets` | you | Planner |
  | `code-review` | the agent | Code-Reviewer |
  | `writing-for-agents` | the agent | Planner, Plan-Reviewer, Code-Reviewer |

  All of them except `code-review` and `writing-for-agents` are user-invoked: their author blocked agents from starting them, so the Role will ask you to type the slash command yourself at the right moment. The Coder is the one Role that borrows nothing. The Plan-Reviewer borrows only `writing-for-agents`, and runs without it: a Role that cannot resolve that skill drops its writing check and says so in the file it writes.
- `/setup-matt-pocock-skills`, run once per repository, answering **Local markdown** when it asks which issue tracker to use. That is what puts the spec and the tickets in `.scratch/<feature-slug>/`, where the Roles look for them.
- Optional: Claude Code 2.1.224+ on macOS or Linux. That is what lets one session ring the next one's doorbell instead of you copying a line between terminals. Everything works without it; the Roles print the line for you to paste.

## Install (Claude Code)

This repository is a Claude Code plugin marketplace. The `vdd` plugin ships one skill per role, so you start each session with a single slash command.

```
/plugin marketplace add ArchitektApx/Vibe-Driven-Development
/plugin install vdd@vibe-driven-development
```

| Role | Skill |
|------|-------|
| Environment check | `/vdd:vdd-setup` |
| Start a loop | `/vdd:vdd-start-loop` |
| Planner | `/vdd:vdd-planner` |
| Plan-Reviewer | `/vdd:vdd-plan-reviewer` |
| Coder | `/vdd:vdd-coder` |
| Code-Reviewer | `/vdd:vdd-code-reviewer` |

Run `/vdd:vdd-setup` once per repository: it verifies the borrowed skills are installed, the issue tracker is configured, the gitignore entries from Phase 0 exist, and no stale working files are left over from a previous loop. `/vdd:vdd-start-loop` runs it for you at the start of every loop.

## Install (Cursor, GitHub Copilot CLI, Codex, other agents)

Other agents can use the same skills via the [skills CLI](https://github.com/vercel-labs/skills), which writes them into your repo as ordinary files you own:

```bash
npx skills@latest add ArchitektApx/Vibe-Driven-Development
npx skills@latest add mattpocock/skills
```

The installer asks which skills to take and which agents to install them for. Take all six `vdd-*` skills, and take all of Matt Pocock's collection: the Roles need seven skills from it, and installing the whole set is what lets `/vdd:vdd-setup` verify your install without asking you to test it by hand. Run `/setup-matt-pocock-skills` once per repository afterwards, and pull updates later with `npx skills update`.

If your agent does not support skills at all, the skill files are ordinary Markdown: paste the body of the relevant `skills/vdd-*/SKILL.md` into your session as a prompt.

This repository is developed using its own workflow; `CONTEXT.md` and `docs/adr/` are the glossary and decision records that produces. See `CLAUDE.md`.

## Workflow

### Phase 0: Prepare the Environment

`.gitignore` the working files the loops below will create. They are scratch space for the sessions, not part of your project.

```gitignore
LOOP.md
.scratch/
PLAN.md
PLAN-REVIEW.md
FIXES.md
CODEREVIEW.md
```

With the plugin installed, `/vdd:vdd-setup` handles this phase for you, including checking that the borrowed skills are installed and the issue tracker is configured. Then run `/setup-matt-pocock-skills` yourself if it asks you to, and choose Local markdown.

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

#### Starting the loop

Open the first session and run `/vdd:vdd-start-loop`. It runs the environment check, asks you for a short name for the repository and a kebab-case slug for this piece of work, confirms the base branch and the feature branch, and writes all of it plus the four session names to `LOOP.md`. Every Role reads that file first, so none of them has to ask you again.

It then prints the line that renames this session to the Planner and hands over to the Planner in the same session.

#### Sessions, names and Doorbells

`LOOP.md` names the four sessions, as `<repository>-<slug>-<Role>`, for example `VDD-new-release-Plan-Reviewer`. Name them exactly that way: rename the current one with `/rename <name>`, and start the next one with `claude -n <name>`. No agent can rename a session, which is why every Role asks you to.

Once the names match, a Role that finishes its turn rings the next one's doorbell instead of waiting for you. The message is deliberately dull: which working file was written, which round, and how many findings per severity. The receiving Role reads the file and ignores the message text, so nothing leaks between the two contexts, which is the whole point of running them apart. Without Claude Code, or without the names, the Role prints the same line for you to paste.

#### The Planner

The Planner is a session that performs the following tasks:

- Identify an issue described by the user, or
- Identify improvements to the codebase (refactoring, adding tests, etc.)
- Grill you on it until you both agree what the work is
- Hand you `/to-spec` and then `/to-tickets`, which publish the spec and the tickets under `.scratch/<slug>/`
- Pass the published spec and every ticket through `writing-for-agents` before handing them on, so the Coder reads them the way it actually reads

The Planner never writes code. Its deliverables are `.scratch/<slug>/spec.md` and the ticket files in `.scratch/<slug>/issues/`.

`/vdd:vdd-start-loop` starts it for you. In a session that already exists, start it with `/vdd:vdd-planner`.

#### The Plan-Reviewer

The Plan-Reviewer is a session that reviews the spec and the tickets and makes sure they are complete, accurate, and grounded in the actual codebase. It also checks them against `writing-for-agents`, because the Planner cannot grade its own prose. It documents its findings and pushbacks in `PLAN-REVIEW.md` and hands that back to the Planner to work on.

Start the session with `/vdd:vdd-plan-reviewer`.

Hand the spec and `PLAN-REVIEW.md` between the two sessions until all issues are resolved and the Plan-Reviewer signs off. In practice this takes one to three rounds. If it takes more, the scope is probably too big: split the work.

### Phase 2: The Coder / Code-Review Loop

#### The Coder

The Coder works on the feature branch from `LOOP.md`, which defaults to the feature slug. It takes the tickets in dependency order, implements one at a time, runs its acceptance criteria, commits it, and writes what it did to `FIXES.md`, which is passed to the Code-Reviewer.

Start the session with `/vdd:vdd-coder`.

#### The Code-Reviewer

The Code-Reviewer runs Matt Pocock's `code-review` over the branch, with the spec as its reference, and then adds the checks that skill does not make: it reruns the verification itself, distrusts `FIXES.md` and the ticked checkboxes, and looks for anything in the diff the tickets did not ask for. When the branch changed a skill file, an `AGENTS.md`, a `CLAUDE.md` or anything one of those points at, it checks those lines against `writing-for-agents` as well; on a branch of ordinary source code that step costs nothing. It documents its findings and pushbacks in `CODEREVIEW.md` and hands that back to the Coder to work on.

Start the session with `/vdd:vdd-code-reviewer`.

Hand `FIXES.md` and `CODEREVIEW.md` between the two sessions until all issues are resolved and the Code-Reviewer signs off.

### Phase 3: Ship

Once the Code-Reviewer has signed off:

1. Open the PR from the feature branch. The commits are already there, one per ticket, and the working files are gitignored and stay behind.
2. Delete `LOOP.md`, `.scratch/<slug>/`, `PLAN-REVIEW.md`, `FIXES.md`, and `CODEREVIEW.md`, or leave them to be overwritten by the next run.
3. Start the next loop with fresh sessions.

## Tips

- **One session per Role, start to finish.** Fresh means fresh per Role, not per round. Reusing the Planner session as the Coder defeats the purpose: it will implement its own assumptions instead of the spec. But a Role keeps its own session across every round of its loop, so a reviewer holds its findings and a Coder holds the reasoning behind its deviations. Each Role starts cold exactly once.
- **Name your sessions as `LOOP.md` says**, or the Doorbells cannot find their target and you are back to copying lines between terminals.
- **A Doorbell is a bell, not a letter.** Never ask a Role to explain itself across sessions; that is what the working files are for, and it is the leak the separate sessions exist to prevent.
- **Reviewers never write code.** The moment a reviewer edits files it stops being a reviewer. Findings go in the review file, fixes go back to the other session.
- **Sign-off is explicit.** "Looks good overall" is not sign-off. Require the literal "SIGNED OFF" line so you can tell at a glance whether a loop is done.
- **Keep loops small.** One bug or one refactoring per loop. Loops that do not converge within a few rounds are a sign the work should be split.
- **Mix vendors if you can.** A Claude planner reviewed by a different model family (or the reverse) catches blind spots that two sessions of the same model share.
