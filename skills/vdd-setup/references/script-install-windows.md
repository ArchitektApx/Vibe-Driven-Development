# Installing the shared scripts on native Windows

The Planner and the Orchestrator run the plugin's shell scripts from one
directory outside the project, the shared directory. This check keeps a
current copy of each script there. Every command below takes the form of the
shell you run it in: the POSIX form in Git Bash, the PowerShell form in
PowerShell.

The shared directory sits outside the project, so your Harness may refuse a
command below or confine it to a sandbox. A refused command does not end this
check: run the same command again with your Harness's own escalation, a run
outside its sandbox or the request that raises an approval prompt. Only when
that is refused too, or your Harness offers no escalation, report the scripts
as not installed, as "A denied prompt or a failed write" says.

## The directory and the scripts

The shared directory is `vdd\` under `%LOCALAPPDATA%`; `XDG_DATA_HOME` is not
read. Resolve it once, in PowerShell:

```powershell
Join-Path $env:LOCALAPPDATA 'vdd'
```

In Git Bash:

```sh
printf '%s\n' "$LOCALAPPDATA\vdd"
```

`<directory>` below is the absolute path that printed, and
`<skill base directory>` is the directory this skill was loaded from, which
your Harness named when it loaded the skill.

The scripts, each shipped beside this file. Never install a `.sh` here: a
Windows checkout carries the `.sh` files with CRLF line endings, and no Role
on Windows runs one.

- [`doorbell-wait.ps1`](doorbell-wait.ps1): the Doorbell wait the Planner and
  the Orchestrator run.
- [`vdd-codex-stop.ps1`](vdd-codex-stop.ps1): the Codex `Stop` hook, which
  runs `doorbell-wait.ps1` from this same directory.

## The check

A copy is current when it exists and matches the shipped file byte for byte.
For each script, in Git Bash:

```sh
cmp "<skill base directory>/references/<script>" "<directory>/<script>"
```

`cmp` exits 0 when the copy is current, and non-zero when the copy differs or
is missing. In PowerShell:

```powershell
(Test-Path -LiteralPath '<directory>\<script>') -and ((Get-FileHash -LiteralPath '<skill base directory>\references\<script>').Hash -eq (Get-FileHash -LiteralPath '<directory>\<script>').Hash)
```

It prints `True` when the copy is current, and `False` when the copy differs
or is missing. Either way a copy that is not current needs an install or an
update. Both forms compare bytes, so a shipped file checked out with CRLF and
its copy still match.

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

Copy each script that is not current, then check the copy. In Git Bash:

```sh
mkdir -p "<directory>"
cp "<skill base directory>/references/<script>" "<directory>/"
cmp "<skill base directory>/references/<script>" "<directory>/<script>"
```

In PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path '<directory>' | Out-Null
Copy-Item -LiteralPath '<skill base directory>\references\<script>' -Destination '<directory>\<script>'
(Test-Path -LiteralPath '<directory>\<script>') -and ((Get-FileHash -LiteralPath '<skill base directory>\references\<script>').Hash -eq (Get-FileHash -LiteralPath '<directory>\<script>').Hash)
```

Copy with `cp` or `Copy-Item` alone. Never read a script and write it out
with a file tool, never edit a copy, and never set an executable bit: a
script the Role writes is a script nobody reviewed, and every caller runs the
copy through `powershell.exe -NoProfile -ExecutionPolicy Bypass -File`.

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
