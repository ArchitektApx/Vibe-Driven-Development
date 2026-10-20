# Vibe Driven Development

A collection of Agent Skills, under `skills/`, and the VDD tool they run,
shipped as a plugin for Claude Code, Codex, Cursor and Copilot CLI. Together
they give a coding project a workflow to brainstorm ideas, chart larger
changes, and plan, implement and review each change.

## Working in this repository

Every change goes through a VDD loop, opened with `/vdd:vdd-start-loop`;
a change that leaves every Role's behaviour alone, a typo fix for example,
may skip it.

## House style

In a skill, a sentence earns its place by changing what a Role does.
Whether it does is settled by running a draft on a lower-tier model, not by
reading it. A reason stays when the Role needs it to act; a reason only a
maintainer needs lives in the commit or the ADR that records it. A slip is
fixed by removing the text that competed with the right instruction, and only
when it breaks a step or a call. A `SKILL.md` aims to fit one 240-line read
window; text every run needs may take it past. Work with one right outcome
goes into the shipped VDD tool, not into a skill (ADR 0010).

## Tests

The VDD tool's tests use the standard library alone and run from any working
directory:

```sh
python3 -B -m unittest discover -s tests
```

On native Windows run it as `py -3 -B -m unittest discover -s tests`. `-B`
keeps Python from caching the test modules; the tool turns bytecode off
itself, so a run leaves no `__pycache__` behind. A test drives the tool from
outside, as a Role or a user sees it. The one exception is the Harness
contract test, `tests/test_harness_contract.py`, which imports the package to
check that every Harness module implements the whole interface. A test that
replaces a guardrail says in its docstring which failure it prevents.

## Code layout

The VDD tool is the package `skills/vdd-setup/scripts/vdd/`.

- Shared helpers sit at the top of the package. A group or concern with
  several modules of its own may be a subpackage, as `harness/`, `setup/` and
  `loop/` are.
- A group module holds its command surface: help, parsing, dispatch and
  printed lines. No group module imports another group's module; `loop fold`
  is part of the `loop` group.
- Code with one user stays with that user: in the group's subpackage, or
  beside the group's module when the group is one module. It moves to the top
  when a second group adopts it.
- One concern per module, about 500 lines at most, as guidance.
- A helper returns facts, and the group that calls it words what the Role
  reads. A helper may supply a fixed part every site shares, with the caller
  passing the rest, as the write refusal in `textfile` does.
- Tests reach the tool through `vdd.py`, as under Tests; the Harness contract
  test stays the one that imports the package.

## Landing a change

A loop's pull request targets `beta`. The user merges every pull request;
never merge one yourself.

Commit subjects carry a conventional prefix: `feat`, `fix`, `docs`, `ci`,
`chore`. The prefix names what the change does, not which file it touches. The
skill files are this plugin's product, so a change to what a Role does is `feat`
or `fix` even though the file is prose, and `docs` is for a change that leaves
behaviour alone.

## Invariants

`verify.yml` enforces these on every PR; preserve them through any refactor
of `.github/`. The comment at each step gives its reason, and a deliberate
exception edits the step in the same PR so the reviewer sees both.

- One hook: the Codex `Stop` hook inline in `.codex-plugin/plugin.json`, in
  its fixed form. No other hook, a `hooks` key in a `SKILL.md` frontmatter
  included, no MCP servers, no symlinks, no executable files.
- A Role runs the VDD tool through a named interpreter: `python3`, or
  `py -3` on native Windows.
- The VDD tool writes only inside the project (its `.gitignore`,
  `.scratch/<slug>/` and the `.scratch/<slug>-<n>/` a loop is moved aside
  to, and in its repository the feature branch `coder start` switches to or
  creates from the base, the fold's rewrite of the loop's commits, as new
  objects and the feature branch's ref, the push of the feature branch, and
  the PR `pr open` opens with `gh pr create`),
  in the Shared directory (`vdd.py` and `vdd/`), and on Codex in
  `~/.codex/hooks.json` (removing an older VDD's entry), and writes no
  bytecode.
- A Codex policy file, `agents/openai.yaml`, has the top-level keys
  `interface` and `policy` and no other.
- `verify.yml` triggers on `pull_request`, never `pull_request_target`, and
  on a push to every branch. Its `permissions` stay `contents: read`.
- `release.yml` alone grants `contents: write`, only on a version tag push or
  `workflow_dispatch`.
- `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json` and the
  plugin's entry in `.claude-plugin/marketplace.json` share name and version,
  the entry's `source` is `"./"`, and the two plugin manifests share every
  other field they both carry. Bump all three versions in the same commit.
- Skill names are unique, and every `SKILL.md` opens with frontmatter that
  carries `name` and `description`.
- Every relative link under `skills/` resolves, a `<placeholder>` target
  excepted.
- Every file under a skill's `references/` is linked directly from its
  `SKILL.md`, a Harness file from `## Harnesses`.
- Every file under a skill's `references/` is at most 8 KB.
- Under `skills/` every tracked file is `.md`, `agents/openai.yaml` or `.py`.
- Outside `skills/`, `.github/`, `tests/` and `docs/` every tracked file is
  `.md`, a manifest `.json` under `.claude-plugin/` or `.codex-plugin/`,
  `.gitignore`, `.gitattributes`, `LICENSE` or `pyrightconfig.json`.
- Every tracked file under `skills/` is at mode 644, and no `.py` starts
  with a shebang.
- Every `.py` under `skills/` is ASCII only and parses as Python 3.9.
- Every `.py` under `skills/` imports only the standard library and the
  tool's own package, and no network module.
- No `.py` under `skills/` calls `shell=True`, `os.system`, `os.popen`,
  `eval`, `exec` or `__import__`, under any alias, or imports `importlib`,
  `runpy`, `posix` or `nt`, any submodule included.
- The tool's tests run on Ubuntu, Windows and macOS against Python 3.9 and
  the newest 3.x.
- A skill has `disable-model-invocation: true` exactly when its
  `agents/openai.yaml` sets `policy.allow_implicit_invocation: false`.
- A skill that ships a `references/harness-<slug>.md` has a `## Harnesses`
  entry for every slug any skill ships: a link to its own file, or `none: the
  inline text is complete`.
- `CLAUDE.md` is the one line `@AGENTS.md`.

## Gotchas

- `.scratch/` is gitignored, and a loop's Loop file sits in it, so a loop on
  this repository leaves nothing behind to commit.
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

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
