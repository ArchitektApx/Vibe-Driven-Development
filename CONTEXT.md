# Vibe Driven Development

The vocabulary of an adversarial multi-session coding workflow, and of the plugin that ships it as skills.

## The workflow

**Workflow**:
Everything from the environment check to the pull request, on one Feature slug. A repository runs one Workflow at a time.
_Avoid_: phase, pipeline, run

**Role**:
One of the seven jobs in the workflow (Planner, Plan-Reviewer, Coder, Code-Reviewer, PR-Author, plus Setup and Start-Loop). Each ships as one skill file; the four reviewing and producing Roles each run in their own session.
_Avoid_: agent, persona, mode

**PR-Author**:
Runs in the Code-Reviewer's session on Sign-off and is the only Role that pushes. Reads the `PR:` line in `LOOP.md` and either opens the PR or prints the assembled body for the user.
_Avoid_: seventh session, autopilot, bot

**Session**:
A single agent conversation running one Role. Separate sessions are what make the review adversarial, because a session cannot see another's reasoning.
_Avoid_: instance, window, context

**Loop**:
A Role and its reviewer exchanging a working file until sign-off. The workflow has two: Plan/Plan-Review and Coder/Code-Review.
_Avoid_: cycle, iteration, phase

**Working file**:
Scratch space for handoff between sessions, gitignored, never part of the user's project: the Loop file, the Spec and Tickets under `.scratch/<feature slug>/`, `PLAN-REVIEW.md`, `FIXES.md`, `CODEREVIEW.md`. Matt Pocock's local-markdown issue tracker counts as a Working file because VDD is what invokes it.
_Avoid_: artifact, output, deliverable

**Feature slug**:
The kebab-case name of one Loop's piece of work, chosen by the user when the Loop starts. It names the tracker directory and sits in the middle of every Session name.
_Avoid_: feature name, ticket name, branch name

**Loop file**:
`LOOP.md` at the repository root. Records the Feature slug, the repository short name, the base branch, the feature branch, the tracker path, the `Minors:` line, the `PR:` line and the four Session names, so every Role reads them instead of asking. `vdd-start-loop` and `LOOP.md` were named before Workflow and Loop were split, and keep their names.
_Avoid_: session file, config, manifest

**Spec**:
`.scratch/<feature slug>/spec.md`, written by the Borrowed skill `to-spec` at the end of the Planner's grilling. Replaces `PLAN.md` as the contract between Planner and Coder.
_Avoid_: plan, PLAN.md, design doc

**Ticket**:
One file under `.scratch/<feature slug>/issues/`, written by the Borrowed skill `to-tickets`. A vertical slice sized for one context window with acceptance criteria; the Coder works Tickets in dependency order.
_Avoid_: task, issue, story

**Agent document**:
A file written to be read by an agent: a skill file, an `AGENTS.md`, a `CLAUDE.md`, and any document reached by a pointer from one of those. Inside a Loop the Spec and the Tickets are Agent documents too.
_Avoid_: prompt, instruction file, agent-facing doc

**Session name**:
`<repository short name>-<Feature slug>-<Role>`, for example `VDD-new-release-Planner`. Set by the user rather than by an agent; it is how one Role addresses another with a Doorbell.
_Avoid_: session id, title, label

**Doorbell**:
A cross-session message from one Role to its counterpart with a fixed template and no free text: which Working file was written, which round, how many open findings per severity, or `SIGNED OFF`.
_Avoid_: notification, handoff message, ping

**Sign-off**:
The literal line `SIGNED OFF` at the top of a review file. The only thing that ends a Loop, withheld while a blocker or a major is open and, on a Minors answer of `fix`, while any minor is open; hedged approval is not sign-off.
_Avoid_: approval, LGTM, done

**Minors answer**:
The `Minors:` line in the Loop file, `fix` or `leave`, given by the user at Workflow start and read by both reviewers. It decides whether an open minor holds up Sign-off.
_Avoid_: minors setting, strictness, thoroughness flag

**Open minor**:
A minor the latest review lists as `open`; a minor the reviewer marked `fixed` or `accepted` is closed. On a Minors answer of `fix` an open minor holds up Sign-off, and on `leave` it does not.
_Avoid_: outstanding nit, unresolved comment, leftover

**Rule inventory**:
One entry per behavioural rule in an Agent document, taken before a writing pass over it and marked afterwards as unchanged, re-expressed or proposed for deletion. Written into the Working file of the Role that made the pass, where it is the evidence that no rule left the document.
_Avoid_: rule list, checklist, audit

**Lever log**:
One entry per passage a writing pass changed, naming the lever from `writing-for-agents` that the passage broke, in that skill's own term. Written beside the Rule inventory, where it is the evidence that no change was made on taste.
_Avoid_: change log, diff summary, rationale

## Skill dependencies

**Borrowed skill**:
A skill from another collection that a Role depends on but does not ship. Currently, from Matt Pocock's collection: `setup-matt-pocock-skills`, `grill-with-docs`, `improve-codebase-architecture`, `to-spec`, `to-tickets` (all User-invoked), and `code-review` and `writing-for-agents` (both agent-invocable).
_Avoid_: external skill, third-party skill, dependency

**User-invoked**:
A property of a skill whose author blocked agents from starting it, so only a human typing the slash command can. All Borrowed skills except `code-review` and `writing-for-agents` are user-invoked. In Claude Code this is `disable-model-invocation: true` in the frontmatter; in Codex, `policy.allow_implicit_invocation: false`.
_Avoid_: manual, disabled, blocked

**Present**:
A Borrowed skill's `SKILL.md` exists in a known store on this machine. Says nothing about whether any agent can run it.
_Avoid_: installed, downloaded

**Resolvable**:
The agent running right now can run a Borrowed skill. Present is necessary but not sufficient: a Borrowed skill sitting in a store this agent was never wired to is Present and not Resolvable.
_Avoid_: available, wired, active, visible

**Sibling probe**:
Testing Resolvable by looking for one of the Borrowed skills' collection-mates that is not User-invoked, and therefore does appear in an agent's own skill list. A hit proves the collection is wired to this agent; a miss proves nothing, because collections can be installed one skill at a time.
_Avoid_: skill check, availability check
