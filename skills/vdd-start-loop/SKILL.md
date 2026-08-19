---
name: vdd-start-loop
description: Entry point of a Vibe Driven Development loop. Use when asked to start a VDD loop, or to set up a new feature for the VDD Roles. Runs the setup checks, writes LOOP.md, then hands over to the Planner.
---

# VDD Start-Loop

You open a Vibe Driven Development loop. Your deliverable is `LOOP.md` at the
repository root, the file every Role reads first. It is the only file you create
or change: code belongs to the Coder, and the tracker directory
`.scratch/<slug>/` is created by the Borrowed skill `to-spec` later, during the
Planner's turn.

Work through the steps in order, each one on the answers the ones before it
produced. A `LOOP.md` written before the checks pass sends three later sessions
down a broken path.

## 1. Run the setup checks

Invoke the `vdd-setup` skill (`/vdd:vdd-setup` in Claude Code, `vdd-setup`
elsewhere). If you cannot invoke skills at all, work through its checks by
hand.

If it reports anything that blocks the Planner, stop and report that to the
user. `LOOP.md` is written once the checks pass and not before. The Planner is
the next session to run, so a Planner blocker blocks the loop.

## 2. Leftover state from an earlier loop

`vdd-setup` already asked about a leftover `LOOP.md`. Once you know the slug
(step 4), check whether `.scratch/<slug>/` exists. If it does, ask the user
whether to delete it or keep it and continue in it. Delete it on the user's word
alone, and keep every path you touch under `.scratch/` inside this loop's slug.

## 3. Repository short name

Propose the basename of `git rev-parse --show-toplevel`. The user confirms it
or gives a shorter one. Ask once. This name prefixes every Session name, so it
keeps names unique across the projects on this machine, and a long one makes
the `@` typeahead painful.

## 4. Feature slug

Ask the user for one kebab-case Feature slug, matching
`[a-z0-9]+(-[a-z0-9]+)*`. Reject anything else, say why, and ask again. The
slug comes from the user and from nowhere else: it names the tracker directory
and sits in the middle of both Session names, so the user owns it.

## 5. Branches

Base branch: read `git branch --show-current`. If it is empty, HEAD is
detached; ask the user which branch is the base.

Feature branch: propose the Feature slug itself as the branch name, and let the
user confirm or override. The bare slug is the whole branch name. VDD is a
development tool, and a tool keeps out of the user's branch namespace, the same
way nobody names branches `vscode/...`.
Reject a feature branch equal to the base branch and ask again; the Coder and
both reviewers need the two to differ, because every review diffs
`<base>...HEAD`.

The Coder creates the branch when it starts, so this step ends on the two names.

## 6. The Minors question

Ask the user once whether an open minor holds up Sign-off. Present these two
answers and no other, in this order:

- Leave them. Writes `Minors: leave`. A reviewer signs off with the open minors
  listed, and the Loop ends there.
- Fix them. Writes `Minors: fix`. Both Loops run until no minor is open,
  however many rounds that takes.

A third answer that defers the decision has no Role to defer it to. Both
reviewers read the line this answer produces, and a reviewer that stops to ask
the user a question stalls the Loop it is in, so this is the only place the
question is asked.

## 7. The PR question

Ask the user once, now that the branches are settled, whether VDD should open
the PR at the end of the Workflow. Present three answers, in this order, with
the middle one as the one that defers the decision:

- Open it. Writes `PR: yes`.
- Ask at Sign-off. Writes `PR: ask at sign-off`.
- Manual. Writes `PR: manual`.

The line the user's answer produces is what the PR-Author reads later, so
this is the only place the question is asked; on `PR: ask at sign-off` the
PR-Author asks again at Sign-off, and on the other two answers it does not.

On `PR: yes`, run these two checks now and print a warning naming any that
failed. The two checks judge on exit code alone; stderr is ignored, because
`git ls-remote` has been observed printing `fatal: failed to store` on a
call that exited 0. They warn without blocking: the Workflow continues
either way, and a broken `gh` login surfaces here instead of at Sign-off.

- **Can push.** A remote is configured and `git ls-remote <remote> HEAD`
  exits 0.
- **Can open a PR.** `gh` is on `PATH`, the host read from `git remote
  get-url <remote>` is a GitHub host, and `gh auth status --hostname <host>`
  exits 0.

Both checks use the same remote: the one the base branch tracks when it
tracks one, else the single configured remote, else `origin`.

## 8. Write `LOOP.md`

Write it at the repository root, in this exact shape:

```markdown
# VDD Loop

Repository: <short>
Feature: <slug>
Base branch: <base>
Feature branch: <branch>
Tracker: .scratch/<slug>/
Minors: <answer>
PR: <answer>

Sessions:
- Planner: <short>-<slug>-Planner
- Orchestrator: <short>-<slug>-Orchestrator
```

The file holds these lines and stops. Round numbers live in the review files,
and each Role checks its own tools for cross-session messaging when it sends, so
neither belongs here; the `Minors:` line and the `PR:` line do belong, because
each is a fact the user states once at Workflow start and no Role changes
afterwards.

## 9. Hand over to the Planner

Print this, with the real values filled in:

> This session is the Planner. Run `/rename <short>-<slug>-Planner` now (Claude
> Code only; skip this line in other agents). The Orchestrator is the other
> session this Workflow uses. It has nothing to do until a Spec exists, so you
> open it when this Planner rings its first Doorbell: `claude -n
> <short>-<slug>-Orchestrator`, then `/vdd:vdd-orchestrator`.

No agent can rename its own session, so this is the user's job and you carry
straight on. Immediately invoke the Planner skill (`vdd:vdd-planner`) in this
same session. If you cannot invoke skills, tell the user to type
`/vdd:vdd-planner` instead.
