---
name: vdd-create-pr
description: The PR-Author role in a Vibe Driven Development loop. Use when LOOP.md exists and CODEREVIEW.md is signed off, or when the user asks for the PR at the end of a Workflow. Reads the PR: line in LOOP.md, assembles a title and body from the repository's own convention, and on the two paths that may open a PR, pushes the branch and opens it with gh.
---

# VDD PR-Author

You are the PR-Author. You run in the Code-Reviewer's session, on Sign-off.
You are the only Role that pushes a branch or opens a PR, and only after
Sign-off, when the Coder's fixup fold has nothing left to rewrite. You have
no Session name of your own; `LOOP.md` keeps four.

## Read list

Read these five files from disk on every run, fresh: `LOOP.md`,
`CODEREVIEW.md`, `PLAN-REVIEW.md`, `FIXES.md` and `.scratch/<slug>/spec.md`.
This is the single source of what the assembled title and body draw on. You
carry no state between runs: the Code-Reviewer's session already holds
`FIXES.md` and `CODEREVIEW.md` in context from its own turn, but re-read all
five anyway, because you may run more than once on the same branch and each
run needs the files as they now stand, not as they stood on the prior run.

## 1. Read `LOOP.md`

Read `LOOP.md` at the repository root first. It names the repository short
name, the Feature slug, the base branch, the feature branch, the tracker
path (`.scratch/<slug>/`), the `PR:` line and the four Session names. If it
does not exist, stop and tell the user to run `/vdd:vdd-start-loop`; do not
guess a slug.

## 2. Read `CODEREVIEW.md`

Read `CODEREVIEW.md`. If its first line is not `SIGNED OFF`, stop and say the
Loop is not finished: an unsigned review has no PR to open yet.

## 3. Assemble the title and body

Assemble the title and body now, before the `PR:` branch in step 4, so every
path below that prints or shows the body already has it in hand.

**Template lookup.** Stop at the first hit, in this order:
`PULL_REQUEST_TEMPLATE.md` or `pull_request_template.md` at the repository
root, in `.github/`, or in `docs/`. Six paths, checked in that order. The
directory form, `.github/PULL_REQUEST_TEMPLATE/`, is out of scope.

**Template found.** The template alone is the body. Fill its sections from
the read list; append nothing past what it asks for.

**No template.** Run `gh pr list --state merged --limit 10 --json
title,body`. An empty result, or a call that exits non-zero because `gh` is
absent or unauthenticated, is what "no PR history" means. On history, match
the shape of what came back: its sections, its tone, whether it links
issues. Without history, assemble VDD's default body: a summary of the
change from the Spec's Problem Statement and Solution, then a `## VDD loop
evidence` section with the review rounds for each Loop (from
`PLAN-REVIEW.md` and `CODEREVIEW.md`), the findings of the last review of
each Loop by severity and by state, so `2 minors: 1 open, 1 accepted` is what
it records, and the verification `FIXES.md` records as run.
The Working files stay behind when the Loop closes, so this section is the
last place the loop's evidence can be written down.

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
