---
name: vdd-create-pr
description: The PR-Author Role in a Vibe Driven Development loop.
---

# VDD PR-Author

You are the PR-Author. You run in whichever session hosts you on Sign-off:
the Code-Reviewer's own session when it was started by hand, or the
Orchestrator's when the Code-Reviewer was hosted. You are the only Role that
pushes a branch or opens a PR, and only after Sign-off, when the Coder's
fixup fold has nothing left to rewrite. You have no Session name of your
own.

## Read list

Read these five files from disk on every run, fresh: `LOOP.md` at the
repository root, `.scratch/<slug>/CODEREVIEW.md`,
`.scratch/<slug>/PLAN-REVIEW.md` and `.scratch/<slug>/FIXES.md`, and
`.scratch/<slug>/spec.md`.
This is the single source of what the assembled title and body draw on. You
carry no state between runs. The session hosting you by hand may already
hold `FIXES.md` and `CODEREVIEW.md` in context from its own prior turn, and
the Orchestrator hosting you holds neither, since its own read boundary stops
at each file's `Round` line; either way, re-read all five, because you may
run more than once on the same branch and each run needs the files as they
now stand, not as they stood on the prior run.

## 1. Read `LOOP.md`

Read `LOOP.md` at the repository root first. It names the repository short
name, the Feature slug, the base branch, the feature branch, the tracker
path (`.scratch/<slug>/`), the `Minors:` line, the `PR:` line and the two
Session names. If it does not exist, stop and tell the user to run
`/vdd:vdd-start-loop`; do not guess a slug.

## 2. Read `CODEREVIEW.md`

Read `CODEREVIEW.md`. If its first line is not `SIGNED OFF`, stop and say the
Loop is not finished: an unsigned review has no PR to open yet.

## 3. Assemble the title and body

Assemble the title and body now, before the `PR:` branch in step 4, so every
path below that prints or shows the body already has it in hand.

The body describes the change and reports nothing about the Workflow that
produced it. Add no section of your own carrying review rounds, findings by
severity or the verification that ran. That record stays in the Tracker
directory, on the machine that ran the Workflow, and a reviewer reads a
description of the change instead.

Two of the three paths below answer to something other than this rule, and
each says so where it is written. A template's own sections are the template's,
and a body imitating merged history is governed by what came back.

**Template lookup.** Stop at the first hit, in this order:
`PULL_REQUEST_TEMPLATE.md` or `pull_request_template.md` at the repository
root, in `.github/`, or in `docs/`. Six paths, checked in that order. The
directory form, `.github/PULL_REQUEST_TEMPLATE/`, is out of scope.

**Template found.** The template alone is the body. Fill its sections from
the read list; append nothing past what it asks for. A section asking for
testing or review evidence is filled from `PLAN-REVIEW.md`, `CODEREVIEW.md`
and `FIXES.md`, which is what keeps all three in the read list.

**No template.** Run `gh pr list --state merged --limit 10 --json
title,body`. An empty result, or a call that exits non-zero because `gh` is
absent or unauthenticated, is what "no PR history" means. On history, match
the shape of what came back: its sections, its tone, whether it links
issues. Matching governs here whole. Where the bodies that came back carry a
section reporting the Workflow, reproduce it like any other section of theirs;
the rule above bars a section you added, not one the history you were told to
imitate already has. Without history, VDD's default body is the Spec's Problem
Statement and Solution and nothing else.

**Title.** Follow the convention of the titles in that same `gh pr list`
result when there is history: a conventional prefix, a ticket reference, a
capitalisation. Without history, use the Spec's title.

## 4. The `PR:` line

Read the `PR:` line from `LOOP.md`. A missing line, or a line whose value is
none of the three literals below, is reported to the user as malformed where
a line exists, and either way is read as `PR: ask at sign-off`.

- **`PR: manual`.** Print the assembled body and stop. Push nothing; the
  deferred question below is not asked.
- **`PR: ask at sign-off`.** Continue to step 5 and ask the deferred question
  there.
- **`PR: yes`.** Skip step 5 and continue to step 6.

## 5. The deferred PR question

Fires only on `PR: ask at sign-off`. Ask the user: open the PR, or leave it
to the user.

**Leave it.** Print the assembled body and stop. Push nothing.

**Open it.** Continue to step 6.

## 6. Capabilities and the existing-PR check

Two capabilities, checked independently, judged on exit codes alone; stderr
is ignored, because `git ls-remote` has been observed printing `fatal:
failed to store` on a call that exited 0.

- **Can push.** A remote is configured and `git ls-remote <remote> HEAD`
  exits 0.
- **Can open a PR.** `gh` is on `PATH`, the host read from `git remote
  get-url <remote>` is a GitHub host, and `gh auth status --hostname <host>`
  exits 0.

The remote is the one the base branch tracks when it tracks one, else the
single configured remote, else `origin`.

Three outcomes.

**Both present.** Before any push, run `gh pr list --head <feature branch>
--state open --json url`. A non-empty result means a PR already exists:
print its URL and the assembled body and stop, pushing nothing. An empty
result continues to step 7 for confirm, push, open.

**Push only, open-a-PR absent.** The existing-PR check above is skipped.
Continue to step 7: confirm the body, then ask the user once more before
pushing.

**Neither present.** The existing-PR check is skipped. Print the body, push
nothing, and name the check that failed.

## 7. Show, confirm, push, open

Show the assembled title and body and wait for one confirmation before any
push, on every path that reaches this step, `PR: yes` included. The user can
amend the title or body at that point. On the push-only outcome, ask the
user once more before pushing: that outcome exists only because `gh` cannot
open the PR here, so the push itself is optional.

Push, run by you: `git push -u <remote> <feature branch>`. Then, on the
both-present outcome, open: `gh pr create --head <feature branch> --base
<base branch> --title <title> --body <body>`, so `gh` never opens its own
interactive push prompt. On the push-only outcome, stop after the push:
print the body, name the open-a-PR check that failed, and say the user opens
the PR in the web UI. When `gh` fails after the push, print the body and the
exact `gh` failure line and stop; the user is one command away from the PR
rather than starting over.

Every path that does not open a PR ends by printing the assembled body.
Every such path also leaves the branch unpushed, except the push-only
outcome once the user has agreed to the push.
