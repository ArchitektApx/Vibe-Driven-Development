# Installing the shared scripts

The Planner and the Orchestrator run the plugin's shell scripts from one
directory outside the project, the shared directory. This check keeps a
current copy of each script there.

## The directory and the scripts

On macOS and Linux the shared directory is `vdd/` under `XDG_DATA_HOME`, or
under `~/.local/share` when `XDG_DATA_HOME` is unset. On native Windows it is
`vdd\` under `%LOCALAPPDATA%`, and `XDG_DATA_HOME` is not read. You are on
native Windows when your Harness reports the platform as Windows; WSL reports
Linux and takes the macOS and Linux forms. Every command below takes the form
of the shell you run it in: on native Windows, the POSIX form in Git Bash and
the PowerShell form in PowerShell.

Resolve the directory once. On macOS and Linux:

```sh
printf '%s\n' "${XDG_DATA_HOME:-$HOME/.local/share}/vdd"
```

On native Windows, the first block for PowerShell and the second for Git Bash:

```powershell
Join-Path $env:LOCALAPPDATA 'vdd'
```

```sh
printf '%s\n' "$LOCALAPPDATA\vdd"
```

`<directory>` below is the absolute path that printed, and
`<skill base directory>` is the directory this skill was loaded from, which
your Harness named when it loaded the skill.

The scripts Setup installs on macOS and Linux, each shipped beside this file:

- [`doorbell-wait.sh`](doorbell-wait.sh): the Doorbell wait the Planner and
  the Orchestrator run.
- [`vdd-codex-stop.sh`](vdd-codex-stop.sh): the Codex `Stop` hook, which runs
  the Doorbell wait for a Codex Role from this same directory.

On native Windows it installs these instead, and never a `.sh`: a Windows
checkout carries the `.sh` files with CRLF line endings, and no Role there
runs one.

- [`doorbell-wait.ps1`](doorbell-wait.ps1): the Doorbell wait in PowerShell.
- [`vdd-codex-stop.ps1`](vdd-codex-stop.ps1): the Codex `Stop` hook in
  PowerShell, which runs `doorbell-wait.ps1` from this same directory.

## The check

A copy is current when it exists and matches the shipped file byte for byte.
For each script, on macOS and Linux and in Git Bash on native Windows:

```sh
cmp "<skill base directory>/references/<script>" "<directory>/<script>"
```

`cmp` exits 0 when the copy is current. It exits non-zero when the copy
differs or is missing, and that script needs an install or an update.

In PowerShell on native Windows:

```powershell
(Test-Path -LiteralPath '<directory>\<script>') -and ((Get-FileHash -LiteralPath '<skill base directory>\references\<script>').Hash -eq (Get-FileHash -LiteralPath '<directory>\<script>').Hash)
```

It prints `True` when the copy is current, and `False` when the copy differs
or is missing. Both forms compare bytes, so a shipped file checked out with
CRLF and its copy still match.

Both paths sit under the user's profile, so a profile such as
`C:\Users\O'Brien` puts an apostrophe inside the single quotes. Write each
apostrophe in a path as `''` here and in the install block below; a single
one ends the string, and the command fails to parse.

When every copy is current, the check passes and you say nothing further
about it.

## Install or update

First show the user what you are about to change: each script you will copy,
and the path it lands at. Showing them is the consent step. Ask no separate
opt-in question: Setup runs at the start of every loop and has nowhere to
store a decline. Where the user's permission mode raises a prompt for the
write, the user approves it there. Where it raises none, write after showing
them.

Copy each script that is not current, then check the copy. On macOS and
Linux and in Git Bash on native Windows:

```sh
mkdir -p "<directory>"
cp "<skill base directory>/references/<script>" "<directory>/"
cmp "<skill base directory>/references/<script>" "<directory>/<script>"
```

In PowerShell on native Windows:

```powershell
New-Item -ItemType Directory -Force -Path '<directory>' | Out-Null
Copy-Item -LiteralPath '<skill base directory>\references\<script>' -Destination '<directory>\<script>'
(Test-Path -LiteralPath '<directory>\<script>') -and ((Get-FileHash -LiteralPath '<skill base directory>\references\<script>').Hash -eq (Get-FileHash -LiteralPath '<directory>\<script>').Hash)
```

Copy with the shell's copy command alone, `cp` or `Copy-Item`. Never read a
script and write it out with a file tool, never edit a copy, and never set an
executable bit: a script the Role writes is a script nobody reviewed (ADR
0011), and every caller runs the copy through a named shell, `sh` or
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File`.

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
