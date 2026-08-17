# Working in this repository

This repository is developed with its own workflow. Use the VDD Roles on
changes to it, the same way a user would on their own project:
`/vdd:vdd-planner` writes `PLAN.md`, a separate session reviews it, and so on.
Proportionality applies, a typo fix does not need four sessions; anything that
changes how a Role behaves does.

The Planner's grilling step is what produced the two files below, and they are
committed for the same reason any project keeps them:

- `CONTEXT.md` is the glossary. Use its terms exactly when editing the skills,
  so the five `SKILL.md` files keep one vocabulary.
- `docs/adr/` records decisions that are hard to reverse and surprising without
  context. Read `0001` before proposing that the Roles be orchestrated
  automatically; that has been tried and rejected.

The repository is prose only. There is no build and no tests. Verification
means reading the skill files as an agent would read them cold; CI only checks
that what ships is well formed (see Invariants).

## Landing a change

`master` is protected by a ruleset with no bypass, so nothing lands by pushing
to it. Branch, push the branch, open a PR, merge it yourself. To merge, a PR
needs the `verify` check green and squash as its merge method; it needs no
approvals.

Every commit must be signed. Local commits inherit `commit.gpgsign`; an
unsigned commit is rejected at merge, not at push.

Repository policy requires every action in `.github/workflows/` to be pinned to
a full commit SHA. A tag reference does not fail review, it fails the run.
Dependabot owns action versions and bumps them in one grouped PR monthly;
bumping a SHA by hand only creates a conflict with the next one.

A workflow file registers with GitHub only when a push modifies it. A workflow
added in a repository's first push stays invisible, absent from the Actions
list, until some later commit touches the file.

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
  so a second skill with the same name silently clobbers the first.

## Gotchas

- Bump the version in both manifests in the same commit; CI fails on drift.
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
