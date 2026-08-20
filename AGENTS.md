# Working in this repository

This repository is developed with its own workflow. Use the VDD Roles on
changes to it, the same way a user would on their own project:
`/vdd:vdd-start-loop` opens the loop and writes `LOOP.md`, the Planner grills
you and produces the Spec and Tickets under `.scratch/<feature-slug>/`, then
an Orchestrator session, opened with `claude -n <name>` and
`/vdd:vdd-orchestrator` when the Planner rings its first Doorbell, hosts the
Plan-Reviewer, the Coder and the Code-Reviewer as subagents until Sign-off,
then hosts the PR-Author, which opens the pull request. Proportionality
applies: a typo fix can skip the loop, and anything that changes how a Role
behaves takes it.
`docs/VDD-WORKFLOW.md` walks the same loop from the user's side.

The Planner's grilling step produced the glossary and the decision records
below, and they are committed so every clone reads the same vocabulary and the
same decisions:

- `CONTEXT.md` is the glossary. Use its terms exactly when editing the skills,
  so the eight `SKILL.md` files keep one vocabulary.
- `docs/adr/` records decisions that are hard to reverse and surprising without
  context. Read `0001` before proposing that a Role run outside the
  Orchestrator, or that the Planner be hosted too; both were decided there.

One decision, one record, kept current. When a decision changes, rewrite the
record that owns it in place to state the decision that holds now. A reversal
appears as one line under `## Considered options`, written as the correction
rather than as the discarded claim, so the false claim is never stated in its
own voice. No stubs, no `Status:` lines, no `Superseded by` lines: nothing
accumulates. A record states the decision that holds now: an ordinal or a
count that reads as a claim about the present is dropped rather than updated,
and a number that records a measurement stays.

The repository is prose only. There is no build and no tests;
`docs/agents/VERIFICATION.md` is what verification means here, and CI only
checks that what ships is well formed (see Invariants).

## House style

Write plain declarative sentences. Say each thing once. Name the concrete
object rather than the category it belongs to. Give the reason where the reader
needs it.

This style binds work on this repository alone. In a user's project their prose
stays theirs, in whatever style they write it.

The six tells of machine prose, a closed list, are in
`docs/agents/VERIFICATION.md`, beside the other checks a reviewer applies.

## Landing a change

`master` is protected by a ruleset with no bypass, so every change lands through
a pull request. Branch, push the branch, open a PR, merge it yourself. To merge,
a PR needs the `verify` check green and squash as its merge method; it needs no
approvals.

Commit subjects carry a conventional prefix: `feat`, `fix`, `docs`, `ci`,
`chore`. The prefix names what the change does, not which file it touches. The
skill files are this plugin's product, so a change to what a Role does is `feat`
or `fix` even though the file is prose, and `docs` is for a change that leaves
behaviour alone.

What the PR body must carry, commit signing, SHA pinning and the
workflow-registration quirk are in `docs/agents/LANDING-A-CHANGE.md`.

## Invariants

This repository is a supplier: everything committed here is cloned onto every
machine that installs the plugin, and a plugin manifest can declare hooks and
MCP servers that execute there. `verify.yml` enforces the following on every
PR; preserve them through any refactor of `.github/`.

- **No executable surface.** No hooks, no MCP servers, no symlinks, no
  executable files. The plugin ships prose and nothing else. Adding one of
  these is a deliberate decision: edit the `Reject executable surface` step in
  the same PR so the reviewer sees both.
- **`verify.yml` triggers on `pull_request`.** It runs PR-head content, so
  `pull_request_target` would hand fork PRs write access and secrets. Its
  `permissions` stay `contents: read`.
- **Manifests parse and agree.** `.claude-plugin/plugin.json` and the plugin's
  entry in `.claude-plugin/marketplace.json` share name, version and
  `source: "./"`. A broken manifest breaks install for every user; there is no
  staged rollout.
- **Skill names are unique.** `npx skills` installs flat by frontmatter `name`,
  so a second skill with the same name silently clobbers the first. Every
  `SKILL.md` opens with frontmatter that carries `name` and `description`.
- **Every relative link under `skills/` resolves.** A pointer in a `SKILL.md`
  or in a Reference file names a file that ships, so a rename or a deletion
  cannot strand a reader who follows it.
- **Every file under a skill directory is linked from its `SKILL.md`.** A
  Reference file no skill file points at is one no reader can be sent to. The
  index section each split skill carries is what makes the direct link enough,
  so the check does not follow links between Reference files.
- **The canonical sentence appears once in each of two skills.**
  `An Orchestrator hosts this Workflow.` occurs exactly once in
  `skills/vdd-orchestrator/SKILL.md`, in the Spawn prompt template, and once
  in `skills/vdd-code-reviewer/SKILL.md`, in its own test. A hosted
  Code-Reviewer compares its Spawn prompt against that sentence word for word
  to decide whether to invoke the PR-Author. The `canonical` string in
  `verify.yml` is the authority: change the sentence in a skill and CI fails
  until the same change lands there too.
- **`CLAUDE.md` is the one line `@AGENTS.md`.** Claude Code reads `CLAUDE.md`
  and wins precedence over `AGENTS.md`; the stub is what makes the rules in
  `AGENTS.md` reach it exactly once.

## Gotchas

- Bump the version in both manifests in the same commit; CI fails on drift.
- `LOOP.md` and `.scratch/` are Working files here too, and the review files
  are inside `.scratch/<feature-slug>/`; both are gitignored, so a loop on this
  repository leaves nothing behind to commit.
- The skills tell users, not agents, to run `npx skills@latest add
  mattpocock/skills`. That is delegated trust to a third-party repository and
  is deliberate; the Planner cannot run without it. Keep it a user instruction.

## Agent skills

### Issue tracker

Local markdown: specs and tickets live under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary, label strings equal role names. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
