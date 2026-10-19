---
name: vdd-start-loop
description: Entry point of a Vibe Driven Development loop.
disable-model-invocation: true
---

# VDD Start-Loop

You open a Vibe Driven Development loop: the VDD tool checks, you ask the
user what it prints, and the tool writes the answers into the loop's Loop
file. You write no file yourself.

Work through the steps in order, each one on the answers the ones before it
produced.

## The VDD tool

You run the `loop` commands with the VDD tool, `vdd.py` in the Shared
directory: `~/.local/share/vdd/vdd.py` on macOS and Linux
(`$XDG_DATA_HOME/vdd/vdd.py` when that variable is set), and
`%LOCALAPPDATA%\vdd\vdd.py` on native Windows. Setup's `--write` in step 1
installs it there. Write the path out in full, every variable expanded, so a
hook that checks shell commands and an approval prompt see no expansion. Run
it as `python3 "<path>"`, on native Windows as `py -3 "<path>"`. If `python3`
or `py -3` is not found, tell the user VDD needs Python 3.9 or newer, and
stop. `loop --help` teaches the commands. Every run ends with a `Next:`
line: do what it says, and relay every `Tell the user verbatim` line
unchanged.

If the interpreter cannot open `vdd.py`, the tool is not at its path: tell the
user to invoke `vdd-setup`, which installs it, and wait; when they say it has
run, rerun the command that failed.

Never write, edit, copy or replace the tool, and never do its work as inline
shell or with your file tools.

## 1. Run the setup checks

Invoke the `vdd-setup` skill. If you cannot invoke skills at all, work through
its checks by hand.

If it reports anything that blocks the Planner, stop and report that to the
user. The Planner is the next session to run, so a Planner blocker blocks the
loop.

## 2. The Harness

Name the Harness this Session runs in. If the user named one, use theirs.
Name it from what this Session knows of itself, never from environment
variables, binaries on `PATH`, or model and provider names: a wrapper can set
any of those without offering the Harness's mechanics. Pass it as `--harness`
on every `loop` command: `claude-code`, `codex`, `cursor` (the Cursor IDE
Agent and the Cursor CLI alike), `copilot-cli`, or `generic` for any other.

## 3. Feature slug

Ask the user for one Feature slug. The slug comes from the user and from
nowhere else: it names the loop, its tracker directory and the feature branch
the tool proposes.

## 4. Check

Run `loop new --slug <slug> --harness <h>`, without `--write`. It checks the
slug, reads the base branch and proposes the feature branch, and changes
nothing. When it refuses the slug, ask the user for another and run it again.

## 5. Ask

Put each `Question` line it prints to the user, one at a time and in the
order printed, with the answers as the line gives them. Ask nothing it does
not print. When its `Next:` line asks for something else, the base branch on
a detached HEAD for one, ask the user for it and run step 4 again with that
answer.

When it reports a leftover `.scratch/<slug>/`, read
[the answers for a leftover tracker directory](references/leftover-tracker.md)
and put its question first. Then, as its `Next:` line says: on continue, run
step 4 again with `--leftover continue`; on start fresh, run `loop aside
--slug <slug> --write`, then step 4 again; on a different slug, go back to
step 3. Continue on an open loop ends Start-Loop: do what its `Next:` line
says.

## 6. Write

Run the command its `Next:` line names, with the user's answers in place of
each `<answer>` and every other option as printed, and `--write`. It writes
the Loop file and opens the loop.

## 7. Hand over to the Planner

This Session is the Planner. Print a closing summary of the Loop file the
tool wrote. It names the slug and says the Orchestrator's launch line will
carry it. It names the Harness, and says the user corrects it by saying so
now, before the Planner starts. It also says the user can ask the
Orchestrator to respawn any hosted Role at any round. On a correction, run
`loop set --slug <slug> --harness-line "<Claude Code, Codex, Cursor, Copilot
CLI or Generic>" --harness <corrected h> --write`, and print this step again.

Then carry straight on: immediately invoke the `vdd-planner` skill in this same
Session. If you cannot invoke skills, tell the user to invoke `vdd-planner`
instead.
