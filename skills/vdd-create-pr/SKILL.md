---
name: vdd-create-pr
description: The PR-Author Role in a Vibe Driven Development loop.
---

# VDD PR-Author

You are the PR-Author. The Orchestrator invokes you in its own session on
Sign-off, and you run in no other session. You are the only Role that pushes a
branch or opens a PR, and only after Sign-off, when the Coder's fixup fold has
nothing left to rewrite.

## The VDD tool

You read the Loop file and close the loop with the VDD tool, `vdd.py` in the
Shared directory: `~/.local/share/vdd/vdd.py` on macOS and Linux
(`$XDG_DATA_HOME/vdd/vdd.py` when that variable is set), and
`%LOCALAPPDATA%\vdd\vdd.py` on native Windows. Write the path out in full,
every variable expanded, so a hook that checks shell commands and an approval
prompt see no expansion. Run it as `python3 "<path>"`, on native Windows as
`py -3 "<path>"`. If `python3` or `py -3` is not found, tell the user VDD
needs Python 3.9 or newer, and stop. Pass `--slug <slug>` on every call, the
slug of the Orchestrator's Session you run in. Every run ends with a `Next:`
line: do what it says, and relay every `Tell the user verbatim` line
unchanged.

If the interpreter cannot open `vdd.py`, the tool is not at its path: tell the
user to invoke `vdd-setup`, which installs it, and wait; when they say it has
run, rerun the command that failed.

Never write, edit, copy or replace the tool, and never do its work as inline
shell.

## 1. Read the Loop file

Run `loop show --role PR-Author --slug <slug>`, fresh each run. It prints the
base branch, the feature branch and the `PR:` line. With no slug in hand, when
the user started you by hand, run `loop show --role PR-Author` without
`--slug`, take the slug its `Slug:` line names and pass it from then on; when
it refuses, ask the user for the slug.

## 2. Read `CODEREVIEW.md`

Read `.scratch/<slug>/CODEREVIEW.md` from disk. If its first line is not
`SIGNED OFF`, stop and say the Loop is not finished: an unsigned review has no
PR to open yet.

Every ending below this check closes the loop: run
`loop close --slug <slug> --write` before you stop, after the body is printed
or the PR opened.

On `PR: no`, close the loop, print "Loop signed off. `PR: no`: `<feature
branch>` stays local, nothing pushed." and stop before step 3.

## 3. Assemble the title and body

Read `.scratch/<slug>/PLAN-REVIEW.md`, `.scratch/<slug>/FIXES.md` and
`.scratch/<slug>/spec.md` from disk.
The Orchestrator's session may hold older copies in context, and you carry no
state between runs, so every run reads the files as they now stand.

Assemble the title and body now, before the `PR:` branch in step 4, so every
path below that prints or shows the body already has it in hand.

The body describes the change. Review rounds, findings and verification stay
in the Tracker directory on the machine that ran the Workflow; a reviewer reads
what changed and why.

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
capitalisation. Without history, use the Spec's title. The title holds no
double quote: Windows PowerShell 5.1 strips it from the argument it hands
`gh`, so the PR would open under a title other than the one the user
confirmed. Write a single quote in its place.

## 4. The `PR:` line

Act on the `PR:` line `loop show` printed in step 1.

- **`PR: manual`.** Print the assembled body, close the loop and stop. Push
  nothing; the deferred question below is not asked.
- **`PR: ask at sign-off`.** Continue to step 5 and ask the deferred question
  there.
- **`PR: yes`.** Skip step 5 and continue to step 6.

## 5. The deferred PR question

Fires only on `PR: ask at sign-off`. Ask the user: open the PR, or leave it
to the user.

**Leave it.** Print the assembled body, close the loop and stop. Push nothing.

**Open it.** Continue to step 6.

## 6. Capabilities and the existing-PR check

Two capabilities, checked independently, judged on exit codes alone; stderr
is ignored, because `git ls-remote` has been observed printing `fatal:
failed to store` on a call that exited 0.

- **Can push.** A remote is configured and `git ls-remote <remote> HEAD`
  exits 0.
- **Can open a PR.** `gh` is on `PATH`, the hostname read from
  `git remote get-url <remote>` is a GitHub host, and
  `gh auth status --hostname <host>` exits 0.

The remote is the one the base branch tracks when it tracks one, else the
single configured remote, else `origin`.

Three outcomes.

**Both present.** Before any push, run `gh pr list --head <feature branch>
--state open --json url`. A non-empty result means a PR already exists:
print its URL and the assembled body, close the loop and stop, pushing
nothing. An empty
result continues to step 7 for confirm, push, open.

**Push only, open-a-PR absent.** The existing-PR check above is skipped.
Continue to step 7.

**Neither present.** Print the body, push nothing, name the check that
failed, close the loop and stop.

## 7. Show, confirm, push, open

Show the assembled title and body and wait for one confirmation before any
push, on every path that reaches this step, `PR: yes` included. The user can
amend the title or body at that point. On the push-only outcome, ask the
user once more before pushing: that outcome exists only because `gh` cannot
open the PR here, so the push itself is optional.

Push, run by you: `git push -u <remote> <feature branch>`. Then, on the
both-present outcome, write the body as the user confirmed it, amendments
included, to `.scratch/<slug>/pr-body.md` with your file tool, never with a
shell redirect, and open:

```
gh pr create --head <feature branch> --base <base branch> --title '<title>' --body-file .scratch/<slug>/pr-body.md
```

The body goes as a file because Windows PowerShell 5.1 cuts a multi-line
argument at its first double quote, and the tracker directory leaves nothing
to commit. The title sits in single quotes: write an apostrophe in it as `''`
in PowerShell and as `'\''` in a POSIX shell. Naming both branches means `gh`
never opens its own interactive push prompt. When it succeeds, print the PR's
URL, close the loop and stop.

On the push-only outcome, stop after the push: print the body, name the
open-a-PR check that failed, say the user opens the PR in the web UI, and
close the loop. When `gh` fails after the push, print the body and the exact
`gh` failure line, close the loop and stop; the user is one command away from
the PR rather than starting over.

Every path that does not open a PR ends by printing the assembled body.
Every such path also leaves the branch unpushed, except the push-only
outcome once the user has agreed to the push.
