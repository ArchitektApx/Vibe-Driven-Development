# Working in this repository

This repository is developed with its own workflow. Use the VDD Roles on
changes to it, the same way a user would on their own project:
`/vdd:vdd-start-loop` opens the loop and writes `LOOP.md`, the Planner grills
you and produces the Spec and Tickets under `.scratch/<feature-slug>/`, a
separate session reviews them, the Coder implements them on the feature branch,
and a fourth session reviews the diff. Proportionality applies: a typo fix can
skip the four sessions, and anything that changes how a Role behaves takes them.

The Planner's grilling step is what produced the two files below, and they are
committed for the same reason any project keeps them:

- `CONTEXT.md` is the glossary. Use its terms exactly when editing the skills,
  so the six `SKILL.md` files keep one vocabulary.
- `docs/adr/` records decisions that are hard to reverse and surprising without
  context. Read `0001` before proposing that the Roles be orchestrated
  automatically; that has been tried and rejected.

The repository is prose only. There is no build and no tests. Verification
means reading the skill files as an agent would read them cold; CI only checks
that what ships is well formed (see Invariants).

## House style

Write plain declarative sentences. Say each thing once. Name the concrete
object rather than the category it belongs to. Give the reason where the reader
needs it.

This style binds work on this repository alone. In a user's project their prose
stays theirs, in whatever style they write it.

`writing-for-agents` covers the defects that change how an agent behaves. What
it leaves behind is phrasing that reads like a machine wrote it, and these six
tells are all of it. The list is closed at six: a seventh replaces one of these
rather than joining them.

1. Em dashes. Use a comma, a colon or a full stop.
2. The "not just X, but Y" cadence, and its relatives ("it is not only A, it is
   also B"). State the half you mean.
3. Triads of adjectives or verbs used for rhythm. Keep the one word that
   carries the meaning.
4. Openers that restate the heading or the question. Answer in the first
   sentence.
5. Hedging modifiers: simply, just, basically, really, actually. State the
   claim plainly.
6. Closing paragraphs that summarise the section above them. End on the last
   point.

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

The pull request body is where a loop's evidence goes: how many review rounds it
took, the findings per severity, and the verification that was run. The Working
files are gitignored, so the body is the only place any of it survives the loop.

Every commit must be signed. Local commits inherit `commit.gpgsign`; an
unsigned commit is rejected at merge, not at push. A rebase re-creates the
commits it moves and signs them again under the same setting, so a signing
failure leaves the rebase stopped part-way rather than producing an unsigned
commit.

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
- `LOOP.md` and `.scratch/` are Working files here too, gitignored like the
  review files; a loop on this repository leaves nothing behind to commit.
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
