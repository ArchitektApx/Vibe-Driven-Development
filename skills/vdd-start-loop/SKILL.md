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
Planner's turn. The one exception is step 5, where you move an existing tracker
directory aside on the user's word.

Work through the steps in order, each one on the answers the ones before it
produced. A `LOOP.md` written before the checks pass sends later sessions down a
broken path.

## 1. Run the setup checks

Invoke the `vdd-setup` skill. If you cannot invoke skills at all, work through
its checks by hand.

If it reports anything that blocks the Planner, stop and report that to the
user. `LOOP.md` is written once the checks pass and not before. The Planner is
the next session to run, so a Planner blocker blocks the loop.

## 2. The Harness

Name the Harness this Session runs in. If the user named one, use theirs. If
this skill's Harnesses index links a file for it, read it now, once. Any other
Harness is Generic, and the inline text is complete. Write it to the Loop
file's `Harness:` line.

The line takes one of five values: `Claude Code`, `Codex`, `Cursor`,
`Copilot CLI` or `Generic`. Name the Harness from what this Session knows of
itself, never from environment variables, binaries on `PATH`, or model and
provider names: a wrapper can set any of those without offering the Harness's
mechanics.

## 3. Repository short name

Propose the basename of `git rev-parse --show-toplevel`. The user confirms it
or gives a shorter one. Ask once. This name prefixes every Session name, so it
keeps names unique across the projects on this machine, and a long one is
longer to type.

## 4. Feature slug

Ask the user for one kebab-case Feature slug, matching
`[a-z0-9]+(-[a-z0-9]+)*`. Reject anything else, say why, and ask again. The
slug comes from the user and from nowhere else: it names the tracker directory
and sits in the middle of both Session names, so the user owns it.

## 5. Leftover state from an earlier loop

`vdd-setup` already asked about a leftover `LOOP.md`. Check whether
`.scratch/<slug>/` exists. If it does not, carry on.

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

## 6. Branches

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

## 7. The Minors question

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

## 8. The PR question

Ask the user once, now that the branches are settled, whether VDD should open
the PR at the end of the Workflow. Present four answers, in this order, with
the second as the one that defers the decision:

- Open it. Writes `PR: yes`.
- Ask at Sign-off. Writes `PR: ask at sign-off`.
- Manual. Writes `PR: manual`; VDD prints the body and you open the PR.
- No PR. Writes `PR: no`; the branch stays local and no body is printed.

The line the user's answer produces is what the Orchestrator and the
PR-Author read later, so this is the only place the question is asked; on
`PR: ask at sign-off` the PR-Author asks again at Sign-off, and on the other
three answers it does not.

On `PR: yes`, read [the two checks](references/pr-preflight.md) and run them
now, one that a push would work and one that `gh` could open a PR, and print
a warning naming any that failed. Judge each on its
exit code alone and ignore stderr. They warn without blocking: the Workflow
continues either way, and a broken `gh` login surfaces here instead of at
Sign-off.

## 9. The Fresh Coder question

Ask the user once whether the Orchestrator should spawn the Coder fresh when
its context grows past a limit. Present these two answers, in this order:

- A limit. Writes `Fresh Coder: over <n>`, with the number the user names.
  Offer a number only where your Harness file gives one.
- Never. Writes `Fresh Coder: never`.

Where your Harness file says to skip this question, follow it instead.

## 10. Write `LOOP.md`

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
Fresh Coder: <answer>
Harness: <Claude Code, Codex, Cursor, Copilot CLI or Generic>

Sessions:
- Planner: <short>-<slug>-Planner
- Orchestrator: <short>-<slug>-Orchestrator
```

The file holds these lines and stops.

## 11. Hand over to the Planner

This Session is the Planner, and a Doorbell sent by Session name reaches it
only under the Planner Session name. Now that `LOOP.md` is written, and before
the closing summary, name this Session `<short>-<slug>-Planner` wherever your
Harness file names a way to name it. Where that way fails, end the closing
summary with the line the user types in this Session to name it by hand, the
real values filled in: `/rename <short>-<slug>-Planner`. Where your Harness
file names no way, and on Generic, name nothing: that Harness sends nothing to
a Session name, and `LOOP.md` still records both Session names.

Print a closing summary of the Loop file you wrote. It names the Harness, and
says the user corrects it by saying so now, before the Planner starts. On a
correction, read the Harness file the index links for the corrected Harness,
if any, and redo step 9 where the corrected Harness handles it differently:
the question skipped on one Harness is asked on another, and the number
offered changes. Rewrite `LOOP.md` with the corrected `Harness:` line and that
answer, and print this step again.

Then carry straight on: immediately invoke the `vdd-planner` skill in this same
Session. If you cannot invoke skills, tell the user to invoke `vdd-planner`
instead.

## Harnesses

- Claude Code: [`references/harness-claude-code.md`](references/harness-claude-code.md)
- Codex: [`references/harness-codex.md`](references/harness-codex.md)
- Cursor: [`references/harness-cursor.md`](references/harness-cursor.md)
- Copilot CLI: [`references/harness-copilot-cli.md`](references/harness-copilot-cli.md)

## Reference files

- [`references/leftover-tracker.md`](references/leftover-tracker.md): what
  continuing, starting fresh and changing the slug each do to an existing
  `.scratch/<slug>/`.
- [`references/pr-preflight.md`](references/pr-preflight.md): the two commands
  behind the `PR: yes` checks, the remote they share, and why their stderr is
  ignored.
- [`references/harness-claude-code.md`](references/harness-claude-code.md),
  [`references/harness-codex.md`](references/harness-codex.md),
  [`references/harness-cursor.md`](references/harness-cursor.md) and
  [`references/harness-copilot-cli.md`](references/harness-copilot-cli.md): the
  typed skill names, the Fresh Coder offer, and how this Session is named on
  each Harness.
