# Vibe Driven Development

A collection of Agent Skills, under `skills/`, and the VDD tool they run,
shipped as a plugin for Claude Code, Codex, Cursor and Copilot CLI. Together
they give a coding project a workflow to brainstorm ideas, chart larger
changes, and plan, implement and review each change.

Before any change, read [`CONTRIBUTING.md`](CONTRIBUTING.md): its skill-text
style, tests, code layout and invariants apply to you.

## Working in this repository

Every change goes through a VDD loop, opened with `/vdd:vdd-start-loop`;
a change that leaves every Role's behaviour alone, a typo fix for example,
may skip it. A loop's pull request targets `beta`. The user merges every
pull request; never merge one yourself.

## Gotchas

- `.scratch/` is gitignored, and a loop's Loop file sits in it, so a loop on
  this repository leaves nothing behind to commit.

## Local Development

@AGENTS.local.md

## Agent skills

### Issue tracker

Local markdown: specs and tickets live under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary, label strings equal role names. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
