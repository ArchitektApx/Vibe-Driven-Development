---
name: vdd-start-loop
description: Entry point of a Vibe Driven Development loop.
disable-model-invocation: true
---

# VDD Start-Loop

You open a Vibe Driven Development loop. Your deliverable is `LOOP.md` at the
repository root, the file every Role reads first. It is the only file you create
or change: code belongs to the Coder, and the tracker directory
`.scratch/<slug>/` is created by the Borrowed skill `to-spec` later, during the
Planner's turn. The one exception is step 2, where you move an existing tracker
directory aside on the user's word.

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
(step 4), check whether `.scratch/<slug>/` exists. If it does not, carry on.

If it does, an earlier Workflow used this slug and its Spec, its Tickets and
its review files are all still in there. Put three answers to the user:
continue that Workflow, start fresh on this slug, or use a different slug.
Continue is the answer when that Workflow was interrupted, and only then.
Starting fresh moves the directory aside, and the move happens before anything
else writes under `.scratch/<slug>/`.

Before you put the question, read
[what each answer does to those files](references/leftover-tracker.md); the
user chooses on that.

Delete nothing on any of the three answers. The earlier Workflow's directory is
that Workflow's record, so a wrong answer here stays recoverable. Keep every
path you touch under `.scratch/` inside this loop's slug or the name you moved
the old one to.

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

On `PR: yes`, run two checks now, one that a push would work and one that `gh`
could open a PR, and print a warning naming any that failed. Judge each on its
exit code alone and ignore stderr. They warn without blocking: the Workflow
continues either way, and a broken `gh` login surfaces here instead of at
Sign-off.

Before you run them, read [the two checks](references/pr-preflight.md) for the
commands, the remote they share and why stderr lies here.

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

## Reference files

- [`references/leftover-tracker.md`](references/leftover-tracker.md): what
  continuing, starting fresh and changing the slug each do to an existing
  `.scratch/<slug>/`.
- [`references/pr-preflight.md`](references/pr-preflight.md): the two commands
  behind the `PR: yes` checks, the remote they share, and why their stderr is
  ignored.
