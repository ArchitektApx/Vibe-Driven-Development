---
name: vdd-start-loop
description: Entry point of a Vibe Driven Development loop.
disable-model-invocation: true
---

# VDD Start-Loop

You open a Vibe Driven Development loop: the VDD tool checks, you ask the
user what it prints, and the tool writes the answers into the loop's Loop
file. You write no file yourself.

## The VDD tool

You run the `loop` commands with the VDD tool, `vdd.py` in the Shared directory: `~/.local/share/vdd/vdd.py` on macOS and Linux (`$XDG_DATA_HOME/vdd/vdd.py` when that variable is set), and `%LOCALAPPDATA%\vdd\vdd.py` on native Windows. Run it as `python3 "<path>" loop <command>`, on native Windows as `py -3 "<path>" loop <command>`, the path written out in full with every variable expanded. If `python3` or `py -3` is not found, tell the user VDD needs Python 3.9 or newer, and stop. If the interpreter cannot open `vdd.py`, tell the user to invoke `vdd-setup`, which installs it, and wait; then rerun the command that failed.

Every command shows its usage and options with `--help`. Every run ends with a `Next:` line: do what it says, and relay every `Tell the user verbatim` line unchanged. Never write, edit, copy or replace the tool, and never do its work as inline shell.

## 1. Run the setup checks

Invoke the `vdd-setup` skill.

If it reports anything that blocks the Planner, stop and report that to the user.

## 2. The Harness

Name the Harness this Session runs in. If the user named one, use theirs.
Name it from what this Session knows of itself, never from environment
variables, binaries on `PATH`, or model and provider names: a wrapper can set
any of those without offering the Harness's mechanics. Every `loop` command
takes it, as `claude-code`, `codex`, `cursor` (the Cursor IDE Agent and the
Cursor CLI alike), `copilot-cli`, or `generic` for any other.

## 3. Feature slug

Ask the user for one Feature slug. The slug comes from the user and from
nowhere else: it names the loop, its tracker directory and the feature branch
the tool proposes.

## 4. Check, ask, write

Run `loop new` with the slug and the Harness, first as a check that writes
nothing, and do what its `Next:` line says: put each `Question` line it
prints to the user, one at a time, ask nothing it does not print, and run
the command it names with the answers. A refused slug, a leftover
`.scratch/<slug>/` and a detached HEAD each come with their own `Next:`; a
different slug goes back to step 3.

## 5. Hand over to the Planner

This Session is the Planner. When the user corrects the Harness, write the
correction into the Loop file with the tool.

Then carry straight on: immediately invoke the `vdd-planner` skill in this same
Session. If you cannot invoke skills, tell the user to invoke `vdd-planner`
instead.
