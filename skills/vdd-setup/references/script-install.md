# Installing the shared scripts

The Planner and the Orchestrator run the plugin's shell scripts from one
directory outside the project, the shared directory. This check keeps a
current copy of each script there.

## Native Windows

On native Windows, skip this check and report in one line why: the scripts
are POSIX sh, and their PowerShell forms ship in a later release. On Codex,
skip the hook registration with it. Doorbells there print for hand relay.

## The directory and the scripts

The shared directory is `vdd/` under `XDG_DATA_HOME`, or under
`~/.local/share` when `XDG_DATA_HOME` is unset. Resolve it once:

```sh
printf '%s\n' "${XDG_DATA_HOME:-$HOME/.local/share}/vdd"
```

`<directory>` below is the absolute path that printed, and
`<skill base directory>` is the directory this skill was loaded from, which
your Harness named when it loaded the skill.

The scripts Setup installs, each shipped beside this file:

- [`doorbell-wait.sh`](doorbell-wait.sh): the Doorbell wait the Planner and
  the Orchestrator run.

## The check

A copy is current when it exists and matches the shipped file byte for byte.
For each script:

```sh
cmp "<skill base directory>/references/<script>" "<directory>/<script>"
```

`cmp` exits 0 when the copy is current. It exits non-zero when the copy
differs or is missing, and that script needs an install or an update. When
every copy is current, the check passes and you say nothing further about it.

## Install or update

First show the user what you are about to change: each script you will copy,
and the path it lands at. Showing them is the consent step. Ask no separate
opt-in question: Setup runs at the start of every loop and has nowhere to
store a decline. Where the user's permission mode raises a prompt for the
write, the user approves it there. Where it raises none, write after showing
them.

Copy each script that is not current, then check the copy:

```sh
mkdir -p "<directory>"
cp "<skill base directory>/references/<script>" "<directory>/"
cmp "<skill base directory>/references/<script>" "<directory>/<script>"
```

Copy with `cp` alone. Never read a script and write it out with a file tool,
never edit a copy, and never set an executable bit: a script the Role writes
is a script nobody reviewed (ADR 0011), and every caller runs the copy with
`sh`.

The directory is outside the project. A write there may need your Harness's
own escalation for a command, or a write outside its sandbox: run the same
commands that way, which raises the approval prompt.

## A denied prompt or a failed write

Report the scripts as not installed, name each copy that did not land, and
carry on with the other checks. Until a copy lands, the Planner and the
Orchestrator cannot run that script, and their Doorbells print for the user
to paste by hand. Nothing records the decline, so Setup offers the install
again on its next run.

## The status report

Setup's final status report names this check's state in one line: passed;
installed, when the directory held no copy of a script; updated, when an
older copy was replaced; or not installed, with the reason. Name the scripts
an install or an update copied.
