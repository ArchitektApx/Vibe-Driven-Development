# Setup searches only the stores the Harness reads

Setup's Present search on each Harness covers only the skill stores and the
plugin cache that Harness reads. A Borrowed skill found only in another
Harness's store is Not Present on this Harness, because this Harness never
loads it. On Copilot CLI, a collection in `~/.claude/skills` is Not Present,
since Copilot CLI has not read that store since 1.0.36. On Claude Code, a
collection in `~/.agents/skills` with no link in a Claude Code store is Not
Present.

Generic searches the union of every Harness's roots, because nobody knows
which stores a Generic Harness reads, and the union loses nothing a Generic
Setup found before.

Cursor searches no `.claude` or `.codex` store. The Cursor IDE reads those
only through its third-party import, which the user can turn off, and Setup
does not read that toggle: no shell can tell the IDE's Agent from the Cursor
CLI, and the CLI ignores the toggle.

A Borrowed skill this Session can run passes the check even when the search
found it in no searched store, and the report says so in one line. A Harness
reads stores the search leaves out, such as Claude Code's enterprise store or
a directory Copilot CLI is told about in `COPILOT_SKILLS_DIRS`, and a skill
the user can run is not a failure. On Cursor the line adds that the store is
likely Claude Code's or Codex's, read through the third-party import, so the
user knows the pass ends when the toggle goes off.

The roots live in the Setup Harness files, written as `~/...` and `./...`
paths that hold on macOS and on Windows, each with the variable that
relocates it named in words. A search form spells the roots and the
relocations for its own shell, and `present-search-posix.md` is the `sh`
form. Keeping the roots in the Harness files means a form for another shell
reads the same lists rather than carrying its own.

## Considered options

**Every root searched on every Harness.** Corrected: a hit in a store this
Harness does not read is a skill this Harness never loads, so it counts as
Not Present here, and the repair goes to a store this Harness reads.

**`repairs.md` split into one file per Harness.** Rejected. It saves about
1.5k tokens, only on a failure, and ADR 0010 keeps a Harness-specific cold
path in its cold file. `repairs.md` has one section per Harness instead.

**Reading Cursor's third-party toggle.** Rejected, for the reason above: the
answer would hold for the IDE's Agent and be wrong for the CLI, and no shell
can tell which one is running.

## Consequences

The search runs `find -L`. A skills-CLI install for Claude Code puts the real
copy in `~/.agents/skills/<name>/` and a symlink at `~/.claude/skills/<name>`,
and Claude Code does not search `~/.agents/skills`, so a `find` that does not
follow symlinked directories would report that working install as Not
Present. With `-L` a dangling symlink still lists nothing and reads as
absent.

Claude Code can scrub variables from the environment of the shell it runs a
Role's commands in. When `CLAUDE_CONFIG_DIR` does not reach that shell, the
search reads the literal `~/.claude` path, and this gap is accepted.

The repairs are keyed by Harness, then by store, so each Harness gets its own
plugin commands: `codex plugin add`, `copilot plugin enable` and a reinstall
in the Cursor IDE's plugin UI, where Cursor has no command-line route.
