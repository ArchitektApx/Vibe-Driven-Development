---
name: vdd-setup
description: Environment check for the Vibe Driven Development workflow.
---

# VDD Setup

Verify this repository and session are ready for a Vibe Driven Development
loop, fix what you can, and report the rest.

This check is machine-level and repository-level. It knows nothing about a
particular feature; `vdd-start-loop` handles per-loop state.

The checks run in the VDD tool, `scripts/vdd.py` in the directory this skill
was loaded from, which your Harness named when it loaded the skill. Run it as
`python3 "<skill directory>/scripts/vdd.py"` on macOS and Linux, and as
`py -3 "<skill directory>\scripts\vdd.py"` on native Windows, with the path
written out in full. Every command shows its usage and options with `--help`.
If `python3` or `py -3` is not found, tell the user VDD needs Python 3.9
or newer, and stop.

If a sandbox refuses a command and your tools offer a way to rerun it outside
the sandbox, rerun it once that way; otherwise say which command was refused
and stop.

1. **Name the Harness this Session runs in.** If the user named one, use
   theirs. Run the tool with `setup --help` to learn the command and the
   names `--harness` takes.

2. **Read your own skill list.** Note which of the names `setup --help`
   lists your skill list shows, as it shows them. A `code-review` counts
   only when its description names the two axes "Standards" and "Spec", or
   when it carries the `mattpocock-skills:` prefix: another skill can carry
   the same bare name. Read `domain-modeling`'s description for whether it
   names `GLOSSARY.md`. This step runs no command.

3. **Run `setup` without `--write`, and do what each `Next:` line says**
   until it says Setup is done: the questions to ask, the planned changes
   shown to the user (showing them is the consent step, so ask no separate
   question), the same command with `--write`, then the short status report.
   Relay every `Tell the user verbatim` line unchanged.
