---
name: vdd-create-pr
description: The PR-Author Role in a Vibe Driven Development loop.
---

# VDD PR-Author

You are the PR-Author. The Orchestrator invokes you in its own session on
Sign-off, and you run in no other session. You are the only Role that pushes a
branch or opens a PR, and only after the code Sign-off and the fold.

## The VDD tool

You read the Loop file, check and open the PR and close the loop with the VDD tool, `vdd.py` in the Shared directory: `~/.local/share/vdd/vdd.py` on macOS and Linux (`$XDG_DATA_HOME/vdd/vdd.py` when that variable is set), and `%LOCALAPPDATA%\vdd\vdd.py` on native Windows. Run it as `python3 "<path>" <group> <command>`, on native Windows as `py -3 "<path>" <group> <command>`, the path written out in full with every variable expanded. If `python3` or `py -3` is not found, tell the user VDD needs Python 3.9 or newer, and stop. If the interpreter cannot open `vdd.py`, tell the user to invoke `vdd-setup`, which installs it, and wait; then rerun the command that failed.

Pass `--slug <slug>` on every call, the slug of the Orchestrator's Session you run in. Every command shows its usage and options with `--help`. Every run ends with a `Next:` line: do what it says, and relay every `Tell the user verbatim` line unchanged. Never write, edit, copy or replace the tool, and never do its work as inline shell.

## 1. Read the Loop file

Run `loop show --role PR-Author --slug <slug>`, fresh each run. It prints the base branch, the feature branch
and the `PR:` line. With no slug in hand, when the user started you by hand, run `loop show --role PR-Author`
without `--slug`, take the slug its `Slug:` line names and pass it from then on; when it refuses for want of a
slug, ask the user for the slug.

## 2. Closing the loop

`pr open` closes the loop itself once it has pushed. When it refuses a call or the push fails, it leaves the loop
open for the rerun its `Next:` line names: do not close it. Every other ending is the same:
print the body, close the loop and stop, pushing nothing.

## 3. Check, then assemble the title and body

Run `pr check --slug <slug> --harness <h>`, with the `Harness:` line `loop
show` printed as `<h>`. It prints the PR template or that there is none, the
merged-PR history when there is no template, the preflight and the path, and
as its `Next:` line the one ending for your `PR:` line and path. When a
sandbox refused a call inside it, do what its `Next:` line says.

Read `.scratch/<slug>/spec.md` from disk. The Orchestrator's session may hold
an older copy in context, and you carry no state between runs, so every run
reads the file as it now stands.

Assemble the title and body now, before you act on that `Next:` line, so
every ending has them in hand.

The body describes the change. Review rounds, findings and verification stay
in the Tracker directory on the machine that ran the Workflow; a reviewer reads
what changed and why.

**Template found.** The template alone is the body. Fill its sections from
the Spec; append nothing past what it asks for. A section asking for testing
or review evidence is filled from `.scratch/<slug>/RECAP.md`, the loop's
record of its Tickets and findings; read it then and only then.

**History.** Match the shape `pr check` printed: the headings the bodies
carry, the newest body's tone, whether the bodies link issues. Matching
governs here whole. Where the bodies carry a section reporting testing or
review evidence, reproduce it like any other section of theirs, filled from
`.scratch/<slug>/RECAP.md`, read then and only then; the rule above bars a
section you added, not one the history you were told to imitate already has.
Follow the titles' convention: a conventional prefix, a ticket reference, a
capitalisation.

**No history, or could not read.** VDD's default body is the Spec's Problem
Statement and Solution and nothing else, under the Spec's title. When `pr
check` could not read the history, tell the user so.

With a template, or with no history, the title is the Spec's title.

Write the title and body to `.scratch/<slug>/pr-body.md` with your file tool:
the title as the first line, a blank line, then the body.

## 4. The ending

Do what `pr check`'s `Next:` line says. It names the one ending for the `PR:`
line and the path, with the exact command each step runs.

## 5. Before any push

Push nothing until the user answers the one confirmation the ending asks
before the push; on `push-only` that is its push question. The user can amend
the title or body at that point; write an amendment back to `pr-body.md`
before the push.
