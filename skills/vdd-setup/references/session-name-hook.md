# The Session-name hook

## What the hook does

The Session-name hook is a `UserPromptSubmit` hook. On each prompt in a
project whose `LOOP.md` says `Harness: Claude Code`, it names the Session
after the Planner or the Orchestrator Session name that `LOOP.md` records:
the Session that ran Start-Loop becomes the Planner, the Session that ran the
Orchestrator becomes the Orchestrator, and a Session that lost one of those
names gets it back. In any other project it exits at once and prints
nothing.

It reads the hook input, `LOOP.md`, this Session's transcript and the
session registry. It writes nothing but its output, a `sessionTitle`.

The script ships beside this file as
[`vdd-session-name.sh`](vdd-session-name.sh), at mode 644.

## Requirement: `jq`

The hook needs `jq` on the `PATH` Claude Code runs hooks with. That `PATH`
can lack Homebrew's directory when Claude Code starts from an IDE or a
desktop app, so check where `jq` lives:

```sh
command -v jq
```

- No output: report "Session-name hook not installed: it needs `jq`", and
  carry on with the other checks.
- A path in `/usr/bin` or `/bin`: the registration below runs the hook with
  `sh` alone.
- A path in any other directory, such as `/opt/homebrew/bin/jq`: the
  registration you add carries a `PATH` prefix for that directory, so the
  hook finds the same `jq`:
  `PATH="/opt/homebrew/bin:$PATH" sh "$HOME/.claude/hooks/vdd-session-name.sh"`.

## Minimum Claude Code version

Claude Code 2.1.94 is the first version that honours
`hookSpecificOutput.sessionTitle` from a `UserPromptSubmit` hook. On an older
version the hook runs and its title is ignored.

## The check

`<skill base directory>` is the directory this skill was loaded from, which
Claude Code names when it loads the skill.

The copy is current when `~/.claude/hooks/vdd-session-name.sh` exists and its
version line equals the shipped script's:

```sh
grep -x '# vdd-session-name v[0-9]*' ~/.claude/hooks/vdd-session-name.sh
grep -x '# vdd-session-name v[0-9]*' <skill base directory>/references/vdd-session-name.sh
```

A missing copy, a copy with no version line (an early trial copy has none),
or a different line means install or update.

The registration is present when any `UserPromptSubmit` hook command in
`~/.claude/settings.json` contains `vdd-session-name.sh`:

```sh
jq -e 'any(.hooks.UserPromptSubmit[]?.hooks[]?;
           (.command? // "" | tostring) | contains("vdd-session-name.sh"))' \
  ~/.claude/settings.json
```

Exit 0 means present. Leave a present registration exactly as it is,
whatever its form: a user who runs the hook with `bash` or with a `PATH`
prefix of their own keeps it. A missing `settings.json` means no
registration. When `jq empty ~/.claude/settings.json` fails, the file does
not parse: leave it untouched, and report "Session-name hook not installed:
`~/.claude/settings.json` does not parse".

When the copy is current and the registration is present, the check passes
and you say nothing further about it.

## Install or update

First show the user what you are about to change:

- when the copy is not current, the copy of the shipped script to
  `~/.claude/hooks/vdd-session-name.sh`;
- when no registration is present, the `UserPromptSubmit` entry added to
  `~/.claude/settings.json`, with its command:
  `sh "$HOME/.claude/hooks/vdd-session-name.sh"`, or with the `PATH` prefix
  from the `jq` section where it applies.

Showing them is the consent step. Ask no separate opt-in question: Setup
runs at the start of every loop and has nowhere to store a decline. Where the
user's permission mode raises a prompt for a write, the user approves it
there. Where it raises none, write after showing them.

When the copy is not current, make it with these commands, and check it:

```sh
mkdir -p ~/.claude/hooks
cp <skill base directory>/references/vdd-session-name.sh ~/.claude/hooks/
cmp <skill base directory>/references/vdd-session-name.sh ~/.claude/hooks/vdd-session-name.sh
```

`cmp` exits 0 when the copy matches. Never read the script and write it out
with a file tool, and never edit the copy or set its executable bit: a
script the Role writes is a script nobody reviewed (ADR 0011), and the
registration runs it with `sh`.

Add the registration only when none is present. `<command>` is the command
shown to the user, in single quotes. With an existing `settings.json`, add
the entry beside any hooks already there:

```sh
jq --arg cmd '<command>' \
  '.hooks.UserPromptSubmit = ((.hooks.UserPromptSubmit // [])
     + [{hooks: [{type: "command", command: $cmd}]}])' \
  ~/.claude/settings.json > ~/.claude/settings.json.vdd-new &&
  mv ~/.claude/settings.json.vdd-new ~/.claude/settings.json
```

`jq` keeps every key and value and rewrites only the whitespace. With no
`settings.json`, create one holding only the `hooks` entry:

```sh
jq -n --arg cmd '<command>' \
  '{hooks: {UserPromptSubmit: [{hooks: [{type: "command", command: $cmd}]}]}}' \
  > ~/.claude/settings.json
```

Check the result with `jq . ~/.claude/settings.json`.

Writes under `~/.claude/` are protected paths in Claude Code. Manual and
`acceptEdits` mode prompt for them, auto mode sends them to its classifier,
`dontAsk` denies them, and bypass permissions allows them without asking. A
sandboxed shell command can be denied writing there too; run the same
command outside the sandbox, which raises the permission prompt.

## A denied prompt or a failed write

Report the hook as not installed, name the change that did not land (the
copy, the registration, or both), and carry on with the other checks.
Nothing records the decline, so Setup offers the hook again on its next run.

## This Session

Claude Code's file watcher picks up a hook added to `~/.claude/settings.json`
while a Session runs, so the hook is active in this Session from the user's
next prompt. Report it as installed and active in this Session. When a
Session the hook should have named stays unnamed, the user names it by hand
with `/rename`; the Orchestrator prints that line when it cannot find the
Planner's Session name.

## Removal

On the user's request, delete `~/.claude/hooks/vdd-session-name.sh` and
remove its entry from `~/.claude/settings.json`, after showing both changes,
under the same permission prompt:

```sh
rm ~/.claude/hooks/vdd-session-name.sh
jq '.hooks.UserPromptSubmit |= ((. // [])
      | map(.hooks |= map(select((.command? // "" | tostring)
                                  | contains("vdd-session-name.sh") | not)))
      | map(select(.hooks | length > 0)))' \
  ~/.claude/settings.json > ~/.claude/settings.json.vdd-new &&
  mv ~/.claude/settings.json.vdd-new ~/.claude/settings.json
```

Tell the user that Setup installs the hook again on its next run.

## The status report

Setup's final status report names the hook's state in one line: passed;
installed, and active in this Session, when there was no copy or no
registration before; updated, when an older copy was replaced; or not
installed, with the reason.
