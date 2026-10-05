# Ringing and waiting through the Doorbell file on native Windows

You are the Planner on native Windows, in PowerShell or in Git Bash. You ring
the Orchestrator through the Doorbell file, and a wait wakes you on its
relays. You fill in the Feature slug from `LOOP.md`, the Doorbell line, the
armed count, and `<script path>`.

A command you type yourself, the directory resolution and the ring, takes the
form of the shell you run it in: the POSIX form in Git Bash, the PowerShell
form in PowerShell. The script runs as `doorbell-wait.ps1` through
`powershell.exe` from every shell, Git Bash included, and never as
`doorbell-wait.sh`, which a Windows checkout carries with CRLF line endings.

Once per Session, before you first run the script, resolve the shared
directory Setup installs it into. In PowerShell:

```powershell
Join-Path $env:LOCALAPPDATA 'vdd'
```

In Git Bash:

```sh
printf '%s\n' "$LOCALAPPDATA\vdd"
```

`<script path>` is the path it printed followed by `\doorbell-wait.ps1`. Write
it out in full in every command after that, so a hook that checks shell
commands and an approval prompt see no expansion.

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

1. Append your line. In Git Bash:

   ```sh
   printf '%s to: Orchestrator %s\n' "$(date +%H:%M:%S)" '<Doorbell line>' >> .scratch/<feature-slug>/doorbells
   ```

   In PowerShell:

   ```powershell
   [IO.File]::AppendAllText((Join-Path (Get-Location).Path '.scratch/<feature-slug>/doorbells'), (Get-Date -Format 'HH\:mm\:ss') + ' to: Orchestrator <Doorbell line>' + "`n")
   ```

   That writes UTF-8 with no byte order mark and ends the line in LF, and
   the escaped colons keep the time `HH:MM:SS` in a culture whose time
   separator is not a colon. Never append with `Add-Content`, which loses
   rings against a polling reader, or with `>>`, which writes UTF-16 in
   Windows PowerShell 5.1.

2. Print the Doorbell line, worded as your Harness file says. An append proves
   nothing about whether the Orchestrator is waiting, so every ring prints.
3. Arm your wait, as "Your wait" says, at the count you last acted on: the
   count command's value right after you acted on the last Doorbell
   addressed to you, never the round number.

## The two commands

The script takes the Doorbell file and your Role, and for a wait the armed
count as a third argument. It takes no flags. Run it through `powershell.exe`
with the path quoted, exactly as written, in Git Bash and in PowerShell alike.

The count command prints how many lines are addressed `to: Planner`. A
missing file counts 0.

```
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<script path>" .scratch/<feature-slug>/doorbells Planner
```

The wait command runs the way your Harness file says. It prints nothing while
it waits, then exits printing the lines beyond `<armed count>`, oldest first,
or `TIMEOUT` after 45 minutes.

```
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<script path>" .scratch/<feature-slug>/doorbells Planner <armed count>
```

Lines to the Orchestrator, your own included, never count, so a ring of yours
never wakes you, and the append and the arm may run in either order.

## Your wait

**The count you last acted on.** When you act on a Doorbell addressed to you,
from a wake or a paste, run the count command at once. The number it prints
is the count you last acted on, until you act on the next Doorbell. Before
you have acted on any, your first arm uses the count command's value. A
duplicate that came out of your wait, as "On wake" defines one, counts as
acted on too, so the next wait does not wake on it again.

Where your Harness file gives its own arming rule, that rule replaces the
rules below. The two commands, the count you last acted on and "On wake"
still hold.

Hold exactly one wait while you expect a relay, armed at the count the count
command printed when you armed it. A wait ends when its output or `TIMEOUT`
arrives, when your Session restarts, or when the count command prints more
than its armed count: the wait then exited within one 10-second poll of the
new line, even if its completion event never reached you. So:

- After a ring, arm when you hold no wait.
- On a pasted relay while you hold a wait, run the count command first. Above
  the wait's armed count, the wait has ended: act, ring and arm as usual. At
  or below it, the line never reached the file and the wait still runs: act
  and ring, and do not arm.
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
came out of the wait you hold, that wait has exited: run the count command and
arm at what it prints. A duplicate that arrives by paste, as a second
completion event, or as the late completion event of a wait the count command
already ended leaves the wait you hold as it is. Each wait's command line
shows its armed count, which tells the waits apart.

## When the script cannot run

A command cannot run when a hook that checks shell commands blocks it, a
Group Policy execution policy overrides `-ExecutionPolicy Bypass`, the script
is not at its path, or it exits non-zero. Say in one line what failed and
fall back to hand relay for this wait: the user pastes the Orchestrator's next
relay. When the script is not at its path, also tell the user that
`vdd-setup` installs it into the shared directory. Your next ring tries the
script again. Never write, edit, copy or `chmod` a script, and never run the
wait as inline shell. Your Harness file's "Trust your live tools over this
file when they disagree" covers a stale description of a means, never the
script, which is the means itself, reviewed and released with this plugin.
Hand relay costs the user only a paste.
