# Setup installs the Session-name hook on Claude Code

On Claude Code a cross-session Doorbell is addressed by Session name, and a
forgotten or mistyped rename loses it. The Session-name hook names the
Planner and the Orchestrator Sessions from the Loop file instead. It ships as
a Reference of `vdd-setup`, `session-name-hook.md`, with the script
`vdd-session-name.sh` beside it at mode 644. Setup installs it on Claude Code
as a standard check, the way it fixes `.gitignore`, with no opt-in question:
it shows the user both changes, copies the script to `~/.claude/hooks/`, and
registers it in `~/.claude/settings.json` as a `UserPromptSubmit` hook that
runs `sh "$HOME/.claude/hooks/vdd-session-name.sh"`.

Setup copies the script out of the plugin because the plugin cache path
changes with every version, so a registration pointing into it would break
on the next update. Run from `~/.claude/hooks/` through `sh`, by a command in
the user's own settings, the hook is not executed from the plugin, and the
plugin still declares no hook.

## Considered options

**A command hook in the plugin's `hooks/hooks.json`.** Rejected. Claude Code
runs a plugin hook on every prompt in every project where the plugin is
enabled, with no per-hook consent. On Windows without Git Bash it hands the
command to PowerShell, so a POSIX command fails there with a notice on every
prompt, and covering both needs two entries, each of which fails on the other
system the same way. Cursor, Copilot CLI and Codex also read a Claude-format
`hooks/hooks.json` from an installed plugin: the Cursor CLI maps
`UserPromptSubmit` to its `beforeSubmitPrompt` and sends a payload with no
`cwd`, Copilot CLI sends one with no `transcript_path`, and Codex skips the
hook until the user trusts it in `/hooks`, again after every change to it. A
hook written for Claude Code's payload would run on those Harnesses with
their own.

**A hooks module (mod) declared in `hooks.json`.** Rejected. It needs Claude
Code 2.1.287 and is in early access, and what the other Harnesses do with one
is unknown.

**An opt-in offer.** Rejected. Setup runs at the start of every loop and has
no place to store a decline, so it would ask again each time, and the user
on Codex, where each Role names its own Session, is asked nothing.

## Consequences

Setup offers the hook again after the user removes it or denies the write,
since no decline is stored.

The hook does nothing unless the Loop file says `Harness: Claude Code`,
because Cursor imports hooks from `~/.claude/settings.json` by default and
would otherwise run it on a Cursor loop.

The `Reject executable surface` step in `verify.yml` is unchanged: the script
is a file at mode 644 under `skills/`, and the plugin manifests declare no
hook. The "No executable surface" Invariant in `AGENTS.md` keeps its rule, and
its prose names the hook as the one shipped script the user's own settings
run.
ADR 0011's rule that a Role never copies a script names this install copy as
an exception.

Reopen this decision when hooks modules leave early access; when
anthropics/claude-code #25045 ships a rename a skill can call; or when an
installed hook misses a name outside T3 Code. T3 Code is a third-party app
that runs Claude Code through its SDK; VDD does not support it, and a
Session resumed there loses its registry name.
