# Vibe Driven Development

The vocabulary of an adversarial multi-session coding workflow, and of the plugin that ships it as skills.

## The workflow

**Workflow**:
Everything from the environment check to the pull request, on one Feature slug. A repository runs one Workflow at a time.
_Avoid_: phase, pipeline, run

**Role**:
One of the ten jobs the plugin ships, each as one skill: the Planner, the Orchestrator, the Plan-Reviewer, the Coder, the Code-Reviewer, the PR-Author, Setup and Start-Loop inside the Workflow, and the Brainstormer and the Wayfinder before it. ADR 0001 says where each runs.
_Avoid_: agent, persona, mode

**Orchestrator**:
The Role that hosts the Plan-Reviewer, the Coder and the Code-Reviewer as subagents in its own Session, carries Doorbells between the Planner and the Loop it hosts, relays a hosted Role's question to the user and resumes it with the answer, and invokes the PR-Author at Sign-off.
_Avoid_: dispatcher, controller, coordinator

**PR-Author**:
Runs in the Orchestrator's session on Sign-off and is the only Role that pushes. Reads the Loop file's `PR:` line and either opens the PR or prints the assembled body for the user. On `PR: no` it does not run.
_Avoid_: extra session, autopilot, bot

**Brainstormer**:
The Role that keeps a project's ideas in `.scratch/_brainstorming/`, one Idea file each plus an index, and talks or grills each idea to `decided` or `dropped`. Runs in the user's session, outside any Workflow, and names no next stage; the user carries a decided Idea file to a Planner or a Wayfinder by hand.
_Avoid_: ideation, backlog, discovery

**Idea file**:
`.scratch/_brainstorming/<slug>.md`, written from the Brainstormer's template: frontmatter with status, importance, size, fog and typed relations, then Key Metrics, Summary, Proposal, Pro, Con, Open Questions, Evidence, Prior Art, Related Ideas, Decision and Next Steps. With the index, the Brainstormer's deliverables.
_Avoid_: proposal, RFC, note

**Wayfinder**:
The Role that opens a change too large for one loop. Briefs Matt Pocock's `wayfinder` skill on VDD once, fixes the Handoffs as the map's destination, and hands the user to that skill. Runs in the user's session, outside any Workflow.
_Avoid_: architect, epic planner, pre-planner

**Handoff**:
One file per loop of a wayfinding effort under `.scratch/<effort>/handoffs/`, `00-overview.md` for the series and `NN-<slug>.md` per loop, in the shape the Wayfinder's handoff contract fixes. The user gives each loop's Planner its Handoff with the prompt the overview carries.
_Avoid_: brief, epic, chunk

**Session**:
A conversation the user opens: the Planner's and the Orchestrator's inside a Workflow, the Brainstormer's or the Wayfinder's before one. A hosted Role runs as a subagent, a fresh conversation the Orchestrator spawns inside its own Session, whose context begins with its Spawn prompt.
_Avoid_: instance, window, context

**Harness**:
The program a Session runs in, which decides how a Role invokes skills, spawns subagents and delivers Doorbells: Claude Code, Codex, Cursor (its IDE Agent or its CLI), Copilot CLI, or Generic for any other. Selected once per Workflow and recorded in the Loop file. Changes mechanics, never the Workflow.
_Avoid_: host, platform, runtime, client, agent, model, provider

**Harness file**:
`references/harness-<slug>.md` in a Role skill, the Reference file that holds what the skill does differently on one Harness: the calls the model makes with its Harness's own tools, and judgment that differs by Harness. A Role reads the one for its Harness once, at the start, through the skill's `## Harnesses` section. Generic has one like the others in the Planner, the Orchestrator and the Code-Reviewer; Start-Loop carries Generic's path inline.
_Avoid_: adapter, platform file, harness reference

**Loop**:
A Role and its reviewer exchanging a working file until sign-off. The workflow has two: Plan/Plan-Review and Coder/Code-Review.
_Avoid_: cycle, iteration, phase

**Working file**:
Scratch space for handoff between sessions, gitignored, never part of the user's project. Every Working file sits in the tracker directory: the Loop file, the Spec and the Tickets, the three review files `PLAN-REVIEW.md`, `FIXES.md` and `CODEREVIEW.md`, the Recap `RECAP.md`, and the Doorbell file. Matt Pocock's local-markdown issue tracker counts as a Working file because VDD is what invokes it.
_Avoid_: artifact, output, deliverable

**Feature slug**:
The kebab-case name of one Loop's piece of work, chosen by the user when the Loop starts. It names the tracker directory, and Start-Loop proposes it as the feature branch.
_Avoid_: feature name, ticket name, branch name

**Tracker directory**:
`.scratch/<feature slug>/`, the directory of one Loop. Holds every Working file, the Loop file included, so one Workflow's Spec, Tickets and review files stay together and the next Workflow on another slug overwrites none of them. Gitignored, so it survives on the machine that ran the Workflow and reaches no clone.
_Avoid_: scratch dir, feature folder, workspace

**Loop file**:
`.scratch/<feature slug>/loop.md`, in the tracker directory. Records the Workflow's settings, the Feature slug, the branches, the user's answers at Workflow start and the Harness, so every Role reads them instead of asking. Only the VDD tool writes, changes and reads it, and it closes and reopens the Loop; whether the Loop is open or closed is kept in the Loop's state file beside it. A finished Loop is closed, not deleted, so its files stay as the record. A `LOOP.md` at the repository root is a Loop file from before 0.16 and is not read.
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

**Reference file**:
A file under a Role skill's `references/` directory, read when a pointer in that skill's `SKILL.md` names the situation at hand. It ships inside the skill directory on every install route, so it is an Agent document like the skill file that points at it.
_Avoid_: resource file, sibling file, appendix

**Spawn prompt**:
The prompt the Orchestrator spawns a hosted Role with. Names the Loop's slug and the Working files outright, tells the Role to invoke its skill, declares that an Orchestrator hosts this Workflow, and states the three prefixed return shapes. Carries the return contract; no Role skill does.
_Avoid_: system prompt, task prompt, instructions

**Model approval**:
The Orchestrator's one blocking prompt, put to the user before its first spawn in a session. It states the model and the thinking level the Orchestrator would give each of the three hosted Roles, the Plan-Reviewer, the Coder and the Code-Reviewer, and the user approves that list or adapts it. The approved selection holds for every spawn in that session.
_Avoid_: model prompt, model config, model check

**Doorbell**:
A fixed line telling a Role that a Working file is ready: which file, which round, and the open findings per severity or `SIGNED OFF`, with no free text. It travels by one of four carriers: the Planner's cross-Session message to the Orchestrator, the Orchestrator's relay back to the Planner, a hosted Role's return value, or the Orchestrator's resume message. The two cross-Session carriers go through the Doorbell file.
_Avoid_: notification, handoff message, ping

**Doorbell file**:
`.scratch/<feature slug>/doorbells`, the append-only Working file in the tracker directory that carries a cross-session Doorbell. Holds one line per ring, addressed to the Role that receives it. Only the VDD tool writes it, with each Role's record of what it handled beside it; on Codex the tool also writes an armed file, `codex-armed-<thread id>`, which the `Stop` hook claims.
_Avoid_: doorbell log, mailbox, inbox

**Shared directory**:
`${XDG_DATA_HOME:-$HOME/.local/share}/vdd/` on macOS and Linux and `%LOCALAPPDATA%\vdd\` on native Windows, outside the project, where Setup copies the VDD tool and from which the Planner and the Orchestrator run it. One per machine, shared by every Workflow on every Harness.
_Avoid_: install directory, scripts folder, hooks directory

**VDD tool**:
The Python program the plugin ships in the Setup skill, `scripts/vdd.py` and its package, and Setup copies into the Shared directory. A Role calls it by subcommand, through `python3` or `py -3`, and learns each command from `--help`; every run ends with the next step.
_Avoid_: script, CLI, helper

**Sign-off**:
A reviewer's round recorded as `SIGNED OFF`, the status line the VDD tool writes under the review file's title. The only thing that ends a Loop, withheld while a blocker or a major is open and, on a Minors answer of `fix`, while any minor is open; hedged approval is not sign-off.
_Avoid_: approval, LGTM, done

**Minors answer**:
The `Minors:` line in the Loop file, `fix` or `leave`, given by the user at Workflow start and read by both reviewers. It decides whether an open minor holds up Sign-off.
_Avoid_: minors setting, strictness, thoroughness flag

**Respawn policy**:
When a hosted Role is respawned: `never`, `every round` after its first, or `over <n>`, once its token count passed `<n>` (Claude Code only). Set per hosted Role in the Loop's state file: the Coder's is asked at Model approval, the reviewers' start at `never`, and any of them changes on the user's word.
_Avoid_: restart rule, context limit, respawn flag

**Respawn**:
A hosted Role spawned anew at a later round of the same Loop, in place of a resume. It starts from the Spawn prompt, that round's number and its Working files. Its Respawn policy and the user's request cause it. A spawn after a restart is not a respawn; restart is the word for the Orchestrator's Session coming back.
_Avoid_: fresh spawn, restart

**Recap**:
`.scratch/<feature slug>/RECAP.md`, the account of one Loop that only the VDD tool writes: every closed finding with what was wrong and how it was resolved, and each Ticket's record. No Role reads it during the Loop; it is for the user afterwards.
_Avoid_: log, history, archive

**Open minor**:
A minor the latest review lists as `open`; a minor the reviewer marked `fixed` or `accepted` is closed. On a Minors answer of `fix` an open minor holds up Sign-off, and on `leave` it does not.
_Avoid_: outstanding nit, unresolved comment, leftover

## Skill dependencies

**Borrowed skill**:
A skill from another collection that a Role depends on but does not ship. From Matt Pocock's collection: `setup-matt-pocock-skills`, `grill-with-docs`, `to-spec`, `to-tickets`, `wayfinder` (all User-invoked), and `code-review`, `writing-for-agents`, `grilling`, `domain-modeling`, `research` and `prototype` (agent-invocable).
_Avoid_: external skill, third-party skill, dependency

**User-invoked**:
A property of a skill whose author blocked agents from starting it, so only a human typing the slash command can.
_Avoid_: manual, disabled, blocked

**Present**:
A Borrowed skill's `SKILL.md` exists in a store the Harness this Session runs in reads. Says nothing about whether this Session can run it.
_Avoid_: installed, downloaded

**Resolvable**:
This Session can run a Borrowed skill. Present is not sufficient: a skill in a store the Harness reads that this Session has not loaded, through a Session that predates the install or a disabled plugin, is Present and not Resolvable. A skill this Session runs from a store Setup does not search is Resolvable and not Present.
_Avoid_: available, wired, active, visible

**Sibling probe**:
Testing Resolvable by looking for one of the Borrowed skills' collection-mates that is not User-invoked, and therefore does appear in a Harness's own skill list. A hit proves the collection is wired to this Harness; a miss proves nothing, because collections can be installed one skill at a time.
_Avoid_: skill check, availability check
