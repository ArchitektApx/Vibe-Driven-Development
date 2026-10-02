# Vibe Driven Development

The vocabulary of an adversarial multi-session coding workflow, and of the plugin that ships it as skills.

## The workflow

**Workflow**:
Everything from the environment check to the pull request, on one Feature slug. A repository runs one Workflow at a time.
_Avoid_: phase, pipeline, run

**Role**:
One of the ten jobs the plugin ships (Planner, Orchestrator, Plan-Reviewer, Coder, Code-Reviewer, PR-Author, plus Setup and Start-Loop inside the Workflow; Brainstormer and Wayfinder before it). Each ships as one skill file. The Planner, the Brainstormer and the Wayfinder run in the user's session; the Orchestrator hosts the Plan-Reviewer, the Coder and the Code-Reviewer and invokes the PR-Author.
_Avoid_: agent, persona, mode

**Orchestrator**:
The Role that puts Model approval to the user before its first spawn, hosts the Plan-Reviewer, the Coder and the Code-Reviewer as subagents, carries Doorbells between the Planner and the Loop it hosts, relays a Role's question to the user and resumes the same subagent with the answer, and invokes the PR-Author in its own session at Sign-off. Runs in its own session, opened when the Planner rings its first Doorbell.
_Avoid_: dispatcher, controller, coordinator

**PR-Author**:
Runs in the Orchestrator's session on Sign-off and is the only Role that pushes. Reads the `PR:` line in `LOOP.md` and either opens the PR or prints the assembled body for the user. On `PR: no` it does not run.
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
One of the two conversations the user opens: the Planner's, and the Orchestrator's. A hosted Role runs as a subagent, a fresh conversation the Orchestrator spawns inside its own session, and that freshness is what still makes the review adversarial: a subagent's context begins with its Spawn prompt and holds nothing of its host's reasoning.
_Avoid_: instance, window, context

**Harness**:
The program a Session runs in, which decides how a Role invokes skills, spawns subagents and delivers Doorbells: Claude Code, Codex, Cursor (its IDE Agent or its CLI), Copilot CLI, or Generic for any other. Selected once per Workflow and recorded in the Loop file. Changes mechanics, never the Workflow.
_Avoid_: host, platform, runtime, client, agent, model, provider

**Harness file**:
`references/harness-<slug>.md` in a Role skill, the Reference file that holds what the skill does differently on one Harness; the slug is the Harness lowercased with spaces as hyphens. A Role reads the one for its Harness once, at the start, through the skill's Harnesses index: the `## Harnesses` section, which names every Harness that has a file in any skill, with a link to this skill's file or the line `none: the inline text is complete`. Every Harness file ends on the drift line, "Trust your live tools over this file when they disagree." Generic has none.
_Avoid_: adapter, platform file, harness reference

**Loop**:
A Role and its reviewer exchanging a working file until sign-off. The workflow has two: Plan/Plan-Review and Coder/Code-Review.
_Avoid_: cycle, iteration, phase

**Working file**:
Scratch space for handoff between sessions, gitignored, never part of the user's project. The Loop file sits at the repository root; every other Working file sits in the tracker directory, the Spec and the Tickets alongside `PLAN-REVIEW.md`, `FIXES.md`, `CODEREVIEW.md` and the Doorbell file. Matt Pocock's local-markdown issue tracker counts as a Working file because VDD is what invokes it.
_Avoid_: artifact, output, deliverable

**Feature slug**:
The kebab-case name of one Loop's piece of work, chosen by the user when the Loop starts. It names the tracker directory and sits in the middle of every Session name.
_Avoid_: feature name, ticket name, branch name

**Tracker directory**:
`.scratch/<feature slug>/`, created by the Borrowed skill `to-spec` and named by the Loop file's `Tracker:` line. Holds every Working file except the Loop file, so one Workflow's Spec, Tickets and review files stay together and the next Workflow on another slug overwrites none of them. Gitignored, so it survives on the machine that ran the Workflow and reaches no clone.
_Avoid_: scratch dir, feature folder, workspace

**Loop file**:
`LOOP.md` at the repository root. Records the Feature slug, the repository short name, the base branch, the feature branch, the tracker path, the `Minors:` line, the `PR:` line, the `Fresh Coder:` line, the Harness and the two Session names, so every Role reads them instead of asking. It is the one Working file outside the tracker directory, because every Role reads it before it knows a Feature slug and no tracker path resolves until it has. `vdd-start-loop` and `LOOP.md` were named before Workflow and Loop were split, and keep their names.
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

**Session name**:
`<repository short name>-<Feature slug>-<Role>`, for example `VDD-new-release-Planner` or `VDD-new-release-Orchestrator`. There are two, the Planner's and the Orchestrator's. Set by the user rather than by an agent; it is the address a Doorbell is sent to. On a Harness that delivers no Doorbell the name is still recorded in the Loop file, and nothing is sent to it.
_Avoid_: session id, title, label

**Spawn prompt**:
The prompt the Orchestrator spawns a hosted Role with. Names the Working files outright, tells the Role to invoke its skill, declares that an Orchestrator hosts this Workflow, and states the three prefixed return shapes. Carries the return contract; no Role skill does.
_Avoid_: system prompt, task prompt, instructions

**Model approval**:
The Orchestrator's one blocking prompt, put to the user before its first spawn in a session. It states the model and the thinking level the Orchestrator would give each of the three hosted Roles, the Plan-Reviewer, the Coder and the Code-Reviewer, and the user approves that list or adapts it. The approved selection holds for every spawn in that session.
_Avoid_: model prompt, model config, model check

**Doorbell**:
A fixed contract naming which Working file was written, which round, and the open findings per severity or `SIGNED OFF`, with no free text. Carried by whichever of four carriers the two ends have: a cross-session message from the Planner to the Orchestrator, the Orchestrator's relay of the Plan-Reviewer's Doorbell back to the Planner, a hosted Role's return value to the Orchestrator, or the Orchestrator's resume message waking a hosted Role. The two cross-session Doorbells, the Planner's to the Orchestrator and the Orchestrator's relay back to the Planner, are sent to the other Session by name, or appended to the Doorbell file where the Harness cannot send one by Session name.
_Avoid_: notification, handoff message, ping

**Doorbell file**:
`.scratch/<feature slug>/doorbells`, the append-only Working file in the tracker directory that carries a cross-session Doorbell on a Harness that cannot send one by Session name. Holds one line per ring, addressed to the Role that receives it.
_Avoid_: doorbell log, mailbox, inbox

**Sign-off**:
The literal line `SIGNED OFF` at the top of a review file. The only thing that ends a Loop, withheld while a blocker or a major is open and, on a Minors answer of `fix`, while any minor is open; hedged approval is not sign-off.
_Avoid_: approval, LGTM, done

**Minors answer**:
The `Minors:` line in the Loop file, `fix` or `leave`, given by the user at Workflow start and read by both reviewers. It decides whether an open minor holds up Sign-off.
_Avoid_: minors setting, strictness, thoroughness flag

**Fresh Coder line**:
The `Fresh Coder:` line in the Loop file, `over <n>` or `never`, given by the user at Workflow start and read by the Orchestrator on every Coder return. On `over <n>` a Coder whose reported context size passed `<n>`, or reported none, is spawned fresh for its next round with `FIXES.md` and the commits as its state; the reviewers are resumed regardless.
_Avoid_: restart rule, context limit, respawn flag

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
A skill from another collection that a Role depends on but does not ship. From Matt Pocock's collection: `setup-matt-pocock-skills`, `grill-with-docs`, `improve-codebase-architecture`, `to-spec`, `to-tickets`, `wayfinder` (all User-invoked), and `code-review`, `writing-for-agents` and `grilling` (agent-invocable).
_Avoid_: external skill, third-party skill, dependency

**User-invoked**:
A property of a skill whose author blocked agents from starting it, so only a human typing the slash command can. All Borrowed skills except `code-review`, `writing-for-agents` and `grilling` are user-invoked. In Claude Code, Cursor and Copilot CLI this is `disable-model-invocation: true` in the frontmatter; in Codex, `policy.allow_implicit_invocation: false`.
_Avoid_: manual, disabled, blocked

**Present**:
A Borrowed skill's `SKILL.md` exists in a known store on this machine. Says nothing about whether any Harness can run it.
_Avoid_: installed, downloaded

**Resolvable**:
The Harness this Session runs in can run a Borrowed skill. Present is necessary but not sufficient: a Borrowed skill sitting in a store this Harness was never wired to is Present and not Resolvable.
_Avoid_: available, wired, active, visible

**Sibling probe**:
Testing Resolvable by looking for one of the Borrowed skills' collection-mates that is not User-invoked, and therefore does appear in a Harness's own skill list. A hit proves the collection is wired to this Harness; a miss proves nothing, because collections can be installed one skill at a time.
_Avoid_: skill check, availability check
