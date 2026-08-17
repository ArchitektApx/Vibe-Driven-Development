---
name: vdd-start-loop
description: Entry point of a Vibe Driven Development loop. Use when asked to start a loop, start a VDD loop, or set up a new feature for the VDD Roles. Runs the setup checks, records the feature slug, base branch, feature branch and session names in LOOP.md, then hands over to the Planner.
---

# VDD Start-Loop

You open a Vibe Driven Development loop. Your deliverable is `LOOP.md` at the
repository root, the file every Role reads first. You never write code, and you
never create the tracker directory `.scratch/<slug>/`; the Borrowed skill
`to-spec` creates that later, during the Planner's turn.

Work through the steps in order. Do not skip ahead: a `LOOP.md` written before
the checks pass sends three later sessions down a broken path.

## 1. Run the setup checks

Invoke the `vdd-setup` skill (`/vdd:vdd-setup` in Claude Code, `vdd-setup`
elsewhere). If you cannot invoke skills at all, work through its checks by
hand.

If it reports anything that blocks the Planner, stop and report that to the
user. Do not write `LOOP.md`. The Planner is the next session to run, so a
Planner blocker blocks the loop.

## 2. Leftover state from an earlier loop

`vdd-setup` already asked about a leftover `LOOP.md`. Once you know the slug
(step 4), check whether `.scratch/<slug>/` exists. If it does, ask the user
whether to delete it or keep it and continue in it. Never delete it without
asking, and never touch another feature's directory under `.scratch/`.

## 3. Repository short name

Propose the basename of `git rev-parse --show-toplevel`. The user confirms it
or gives a shorter one. Ask once. This name prefixes every Session name, so it
keeps names unique across the projects on this machine, and a long one makes
the `@` typeahead painful.

## 4. Feature slug

Ask the user for one kebab-case Feature slug, matching
`[a-z0-9]+(-[a-z0-9]+)*`. Reject anything else, say why, and ask again. Do not
invent a slug and do not derive one from the conversation: it names the tracker
directory and sits in the middle of all four Session names, so the user owns
it.

## 5. Branches

Base branch: read `git branch --show-current`. If it is empty, HEAD is
detached; ask the user which branch is the base.

Feature branch: propose the Feature slug itself as the branch name, and let the
user confirm or override. No prefix. VDD is a development tool, not a namespace
in the user's repository, the same way nobody names branches `vscode/...`.
Reject a feature branch equal to the base branch and ask again; the Coder and
both reviewers need the two to differ, because every review diffs
`<base>...HEAD`.

You do not create the branch. The Coder creates it when it starts.

## 6. Write `LOOP.md`

Write it at the repository root, in this exact shape:

```markdown
# VDD Loop

Repository: <short>
Feature: <slug>
Base branch: <base>
Feature branch: <branch>
Tracker: .scratch/<slug>/

Sessions:
- Planner: <short>-<slug>-Planner
- Plan-Reviewer: <short>-<slug>-Plan-Reviewer
- Coder: <short>-<slug>-Coder
- Code-Reviewer: <short>-<slug>-Code-Reviewer
```

Nothing else goes in the file. Round numbers live in the review files, and each
Role checks its own tools for cross-session messaging when it sends, so neither
belongs here.

## 7. Hand over to the Planner

Print this, with the real values filled in:

> This session is the Planner. Run `/rename <short>-<slug>-Planner` now (Claude
> Code only; skip this line in other agents). The other three sessions are
> listed in `LOOP.md`; start each one with `claude -n <name>` when its turn
> comes.

No agent can rename its own session, so this is the user's job. Do not wait for
it. Immediately invoke the Planner skill (`vdd:vdd-planner`) in this same
session. If you cannot invoke skills, tell the user to type `/vdd:vdd-planner`
instead.
