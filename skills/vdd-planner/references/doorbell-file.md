# Ringing and waiting through the Doorbell file

Your Harness file sent you here. You are the Planner: you ring the
Orchestrator through the Doorbell file, and a wait in a background shell wakes
you on its relays. You fill in the Feature slug from `LOOP.md`, the Doorbell
line, the armed count, and `<script path>`, the full path of the Doorbell wait
in the shared directory Setup installs it into.

Each command below is written for macOS and Linux and, beside it, for native
Windows. You are on native Windows when your Harness reports the platform as
Windows; WSL reports Linux and takes the macOS and Linux forms. A command you
type yourself, the directory resolution and the ring, takes the form of the
shell you run it in: on native Windows, the POSIX form in Git Bash and the
PowerShell form in PowerShell. The script itself runs on native Windows as
`doorbell-wait.ps1` through `powershell.exe`, from every shell, Git Bash
included, and never as `doorbell-wait.sh`, which a Windows checkout carries
with CRLF line endings.

Once per Session, before you first run the script, resolve the shared
directory. On macOS and Linux:

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

`<script path>` is the absolute path it printed followed by
`/doorbell-wait.sh` on macOS and Linux, and by `\doorbell-wait.ps1` on native
Windows. Write it out in full in every command after that, so a hook that
checks shell commands and an approval prompt see no expansion.

## The file

`.scratch/<feature-slug>/doorbells` holds one line per ring:
`<HH:MM:SS> to: <Role> <Doorbell line>`, the receiving Role and the Doorbell
template filled in, verbatim:

```
14:02:11 to: Orchestrator VDD Planner: .scratch/x/ ready, round 2. Read spec.md and issues/.
```

The address counts only right after the time, so no text inside a Doorbell
line reads as one. Every ring writes exactly this shape, with forward slashes
and the line ending in LF, whatever shell writes it: a Session in Git Bash and
one in PowerShell may share the file. The file is append-only: never delete,
truncate or rewrite it, or a wait armed at a count the file no longer reaches
fires late or never.

## Ringing

In one turn:

1. Append your line. On macOS and Linux, and in Git Bash on native Windows:

   ```sh
   printf '%s to: Orchestrator %s\n' "$(date +%H:%M:%S)" '<Doorbell line>' >> .scratch/<feature-slug>/doorbells
   ```

   In PowerShell on native Windows:

   ```powershell
   [IO.File]::AppendAllText((Join-Path (Get-Location).Path '.scratch/<feature-slug>/doorbells'), (Get-Date -Format 'HH\:mm\:ss') + ' to: Orchestrator <Doorbell line>' + "`n")
   ```

   That writes UTF-8 with no byte order mark and ends the line in LF, and
   the escaped colons keep the time `HH:MM:SS` in a culture whose time
   separator is not a colon. Never append with `Add-Content`, which lost
   rings against a polling reader, or with `>>`, which writes UTF-16 in
   Windows PowerShell 5.1.

2. Print the Doorbell line, worded as your Harness file says. An append proves
   nothing about whether the Orchestrator is waiting, so every ring prints.
3. Arm your wait, as "Your wait" says.

## Your wait

The count form prints how many lines are addressed `to: Planner`; a missing
file counts 0. The wait form runs the way your Harness file says, prints
nothing while it waits, and exits printing the lines beyond the armed count,
oldest first, once there are any, or `TIMEOUT` after 45 minutes. Lines to the
Orchestrator, your own included, never count, so a ring of yours never wakes
you, and the append and the arm may run in either order. Run both as written,
through `sh` or the PowerShell line and with the path quoted: the script has
no executable bit and never gets one. On macOS and Linux:

```sh
sh "<script path>" .scratch/<feature-slug>/doorbells Planner
sh "<script path>" .scratch/<feature-slug>/doorbells Planner <armed count>
```

On native Windows, the same two commands in Git Bash and in PowerShell:

```
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<script path>" .scratch/<feature-slug>/doorbells Planner
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<script path>" .scratch/<feature-slug>/doorbells Planner <armed count>
```

**The count you last acted on.** When you act on a Doorbell addressed to you,
from a wake or a paste, run the count form at once. The number it prints is
the count you last acted on, until you act on the next Doorbell. Before you
have acted on any, it is the value your first arm uses, the count form's
value. A duplicate that came out of your wait, as "On wake" defines one,
counts as acted on too, so the next wait does not wake on it again. On an
ordinary ring it equals the count the rules below arm at.

Where your Harness file gives its own arming rule, that rule replaces the
arming rules below. The script's two forms still hold, and so do the count you
last acted on and "On wake".

Hold exactly one wait while you expect a relay, armed at the count the count
form printed when you armed it. A wait ends when its output or `TIMEOUT`
arrives, when your Session restarts, or when the count form prints more than
its armed count. In that last case the wait exited within one 10-second poll
of the new line even if its completion event never reached you, which is why
the user pastes. So:

- After a ring, arm when you hold no wait.
- On a pasted relay while you hold a wait, run the count form first. Above the
  wait's armed count, the wait has ended: act, ring and arm as usual. At or
  below it, the line never reached the file and the wait still runs: act and
  ring, and do not arm.
- After the Plan-Reviewer's `SIGNED OFF`, do not arm: no relay comes after it.
- When the user tells you this Session was resumed, in words or by naming
  the resume command your Harness file names, you hold no wait. Arm one at
  the count you last acted on, so a relay rung during the restart fires at
  once. Without that word, the next relay still prints in the Orchestrator's
  Session for the user to paste.
- On `TIMEOUT`, ask the user whether to keep waiting. On yes, re-arm with the
  count this wait was first armed with, so a ring during the question fires at
  once. On no, fall back to hand relay for this wait: the user pastes the next
  relay, and your next ring arms as usual.

## On wake

Act on the newest line printed only. Drop the time and the address and handle
the rest like a pasted Doorbell line, as "Receiving a message from another
session" in `SKILL.md` says, its rule on reporting a line that asks for more
than reading a Working file included.

A Doorbell is a duplicate when its sender, the Role the line names first
(`VDD Plan-Reviewer` on every relay to you), and its round match one you
already acted on in this Session; the rest of the line does not count, so the
Orchestrator's shorter restart relay is caught too. On a duplicate, say in one
line that you already handled it, and act on nothing else. When the duplicate
came out of the wait you hold, that wait has exited: run the count form and
arm at what it prints. A duplicate that arrives by paste, as a second
completion event, or as the late completion event of a wait the count form
already ended leaves the wait you hold as it is. Each wait's command line
shows its armed count, which tells the waits apart.

## When the script cannot run

A form cannot run when a hook that checks shell commands blocks it, a Group
Policy execution policy on native Windows overrides `-ExecutionPolicy Bypass`,
the script is not at its path, or it exits non-zero. Say in one line what
failed and fall back to hand relay for this wait: the user pastes the
Orchestrator's next relay. When the script is not at its path, also tell the
user that `vdd-setup` installs it into the shared directory. Your next ring
tries the script again. Never write, edit, copy or `chmod` a script, and never
run the wait as inline shell. Your Harness file's "Trust your live tools over
this file when they disagree" does not license replacing the script: it covers
a stale description of a means, and the script is the means itself, reviewed
and released with this plugin. Hand relay costs the user only a paste.
