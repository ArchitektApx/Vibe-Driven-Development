# Working in this repository

This repository is developed with its own workflow. Use the VDD Roles on
changes to it, the same way a user would on their own project:
`/vdd:vdd-start-loop` opens the loop and writes `LOOP.md`, the Planner grills
you and produces the Spec and Tickets under `.scratch/<feature-slug>/`, then
an Orchestrator session, opened with `claude` and `/vdd:vdd-orchestrator`
when the Planner rings its first Doorbell, hosts the Plan-Reviewer, the Coder
and the Code-Reviewer as subagents until Sign-off, then invokes the PR-Author,
which opens the pull request. Proportionality applies: a typo fix can skip the
loop, and anything that changes how a Role behaves takes it.
`docs/VDD-WORKFLOW.md` walks the same loop from the user's side.

The Planner's grilling step produced the glossary and the decision records
below, and they are committed so every clone reads the same vocabulary and the
same decisions:

- `CONTEXT.md` is the glossary. Use its terms exactly when editing the skills,
  so the ten `SKILL.md` files keep one vocabulary.
- `docs/adr/` holds the ADRs, which follow `ADR-FORMAT.md` in the
  `domain-modeling` skill. Read `0001` before proposing that a Role run
  outside the Orchestrator, or that the Planner be hosted too; both were
  decided there.

An ADR records a decision that is hard to reverse, surprising without context
and the result of a real trade-off, and says in a few sentences what was
decided and why. It states the long-term decision, never the wording or
mechanics of the skill that carries it out, so a change to a skill leaves the
ADR as it is. An ADR that would need an edit with every change to a skill
records current ruling, and that ruling belongs in the skill.

When a decision changes, rewrite the record that owns it in place to state the
decision that holds now, with the discarded option under
`## Considered options`, so superseded records never pile up.

The repository is prose plus the shell scripts the Roles run, with no build.
Its tests are the two fixture tests for the Codex `Stop` hook and the Doorbell
wait, each run by hand from anywhere and not in CI:
`sh tests/vdd-codex-stop.test.sh` for the POSIX scripts, and
`pwsh -NoProfile -File tests/vdd-codex-stop.test.ps1` for the PowerShell
scripts, run once with `powershell.exe` on Windows as well.
`docs/agents/VERIFICATION.md` is what verification means here, and CI only
checks that what ships is well formed (see Invariants).

## House style

Write plain declarative sentences. Say each thing once. Name the concrete
object rather than the category it belongs to. Give the reason where the reader
needs it.

This style binds work on this repository alone. In a user's project their prose
stays theirs, in whatever style they write it.

In a skill, a sentence earns its place by changing what a Role does.
Whether it does is settled by running a draft on a lower-tier model, not by
reading it. A reason stays when the Role needs it to act; a reason only a
maintainer needs lives in the commit or the ADR that records it. A slip is
fixed by removing the text that competed with the right instruction, and only
when it breaks a step or a call. A `SKILL.md` aims to fit one 240-line read
window; text every run needs may take it past.

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

Commit signing, SHA pinning and the workflow-registration quirk are in
`docs/agents/LANDING-A-CHANGE.md`.

## Invariants

This repository is a supplier: everything committed here is cloned onto every
machine that installs the plugin, and a plugin manifest can declare hooks and
MCP servers that execute there. `verify.yml` enforces the following on every
PR; preserve them through any refactor of `.github/`.

- **No executable surface.** No hooks, no MCP servers, no symlinks, no
  executable files. The plugin ships prose and shell scripts at mode 644 that
  a Role runs with `sh`, or on native Windows with `powershell.exe -NoProfile
  -ExecutionPolicy Bypass -File`, never with an executable bit. Setup copies
  the shipped scripts into the shared directory,
  `${XDG_DATA_HOME:-$HOME/.local/share}/vdd/`, or `%LOCALAPPDATA%\vdd\` on
  native Windows, where a Role runs the Doorbell wait and the user's
  `~/.codex/hooks.json` runs the Codex `Stop` hook, both through that named
  shell, so the plugin still executes nothing itself.
  Adding one of the four
  is a deliberate decision: edit the `Reject executable surface` step in
  the same PR so the reviewer sees both.
- **A Codex policy file carries policy only.** Every `agents/openai.yaml`
  under `skills/` has the top-level keys `interface` and `policy` and no
  other, because a `dependencies` key there can declare tools, MCP servers
  among them. The `Reject executable surface` step checks it, finding the
  files with `find` so a plain copy of the tree is checked like a checkout.
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
  cannot strand a reader who follows it. A target carrying `<angle brackets>`
  is a template placeholder and is skipped.
- **A user-invoked skill is user-invoked on every Harness.** A skill's
  frontmatter carries `disable-model-invocation: true`, which Claude Code,
  Cursor and Copilot CLI honour, exactly when its `agents/openai.yaml` sets
  `policy.allow_implicit_invocation: false`, which Codex honours. Each half is
  ignored by the Harnesses the other covers, so a skill carrying one alone is
  model-invocable on those Harnesses.
- **Every file under a skill directory is linked from its `SKILL.md`.** A
  Reference file no skill file points at is one no reader can be sent to.
  Each file is linked from the step in `SKILL.md` that reads it, a Harness
  file from `## Harnesses`, which is what makes the direct link enough, so the
  check does not follow links between Reference files.
  `agents/openai.yaml` directly inside a skill directory is the one exemption:
  Codex reads it as the skill's policy file, and no reader reaches it by a
  link.
- **Every skill with a Harness file indexes every Harness.** A skill that
  ships a `references/harness-<slug>.md` has a `## Harnesses` section with an
  entry for every slug that has a Harness file in any skill: a link to its own
  `references/harness-<slug>.md`, or a bullet naming that Harness with the
  text `none: the inline text is complete`. A Role reads the Harness file that
  section sends it to, so a Harness missing from it is a Harness whose reader
  gets sent nowhere.
- **Every shell script under `skills/` parses.** Each `.sh` file passes
  `sh -n`, and each `.ps1` file passes the PowerShell parser with none of the
  token kinds Windows PowerShell 5.1 cannot parse (`&&`, `||`, `??`, `??=`,
  the ternary `?`, `?.` and `?[`), all found with `find` so a plain copy of
  the tree is checked like a checkout. A Role runs the script in the user's
  Session, so a syntax error reaches the user as a script that fails on its
  first run.
- **Every shipped script is ASCII-only.** No `.sh` or `.ps1` under `skills/`
  holds a byte outside tab, line feed, carriage return and printable ASCII,
  found with `find`. Windows PowerShell 5.1 reads a script without a byte
  order mark in the ANSI code page, so any other byte reaches it as a
  different character.
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

## Local Development

@AGENTS.local.md

## Agent skills

### Issue tracker

Local markdown: specs and tickets live under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary, label strings equal role names. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
