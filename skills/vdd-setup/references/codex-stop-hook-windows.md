# The Codex `Stop` hook on native Windows

## What the hook does

A Codex Session cannot be woken by a background shell that exits, so on
Codex the Planner and the Orchestrator wait through a `Stop` hook. A Role that
expects a Doorbell writes an armed file, `armed-<thread id>` in the tracker
directory, before its turn ends. At the turn's end the hook claims that file,
runs the Doorbell wait with no model turn, and continues the Session with the
Doorbell line as its prompt. In a project whose `LOOP.md` does not say
`Harness: Codex` the hook prints nothing: the script exits once it has read
`LOOP.md`, before it reads the hook input.

The script is [`vdd-codex-stop.ps1`](vdd-codex-stop.ps1), installed into the
shared directory with `doorbell-wait.ps1` by the shared scripts check. Codex
runs hooks outside its sandbox, which is why it is a short script a user can
read in full. It does not need `jq`.

Codex on native Windows gives you PowerShell, so the commands below are
PowerShell.

## The check

Register the hook only when its copy is in the shared directory, which the
shared scripts check has just confirmed or installed. When that copy is not
there, register nothing and report "Codex `Stop` hook not installed: its
script is not in the shared directory".

The registration is present when a `Stop` hook in `~\.codex\hooks.json` or
`~\.codex\config.toml` has a `command` or a `commandWindows` that contains
`vdd-codex-stop.ps1`. This finds the candidate lines, and a missing file is
no error, which `Select-String -Path` alone would report:

```powershell
Get-Item -Path "$env:USERPROFILE\.codex\hooks.json", "$env:USERPROFILE\.codex\config.toml" -ErrorAction SilentlyContinue | Select-String -SimpleMatch -Pattern 'vdd-codex-stop.ps1'
```

Read the file around a hit to confirm it sits under `Stop`.
Leave a present registration exactly as it is, whatever its form: a user who
wrote it differently keeps it. When it is present, the check passes and you
say nothing further about it, trust included.

## The entry

When no registration is present, add an entry to
`$env:USERPROFILE\.codex\hooks.json` whose handler carries `command` and
`commandWindows`, both set to this one PowerShell string, `<directory>` being
the shared directory's Windows path that the shared scripts check resolved:

```powershell
$f='<directory>\vdd-codex-stop.ps1';if(Test-Path -LiteralPath $f){powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f}
```

In the JSON, shown here for the usual `%LOCALAPPDATA%`, every backslash in
the string is doubled. An apostrophe in the path is doubled first, inside the
single-quoted PowerShell string, before the JSON escaping:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$f='C:\\Users\\<user>\\AppData\\Local\\vdd\\vdd-codex-stop.ps1';if(Test-Path -LiteralPath $f){powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f}",
            "commandWindows": "$f='C:\\Users\\<user>\\AppData\\Local\\vdd\\vdd-codex-stop.ps1';if(Test-Path -LiteralPath $f){powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f}",
            "timeout": 2760
          }
        ]
      }
    ]
  }
}
```

Codex on Windows runs the selected string through PowerShell with
`-Command`, never through Git Bash, so the string is PowerShell that parses on
Windows PowerShell 5.1 and on PowerShell 7 alike. It exits 0 with no output
when the script is missing, where a bare `-File` on a missing path prints
usage text that Codex reports as invalid hook output at every turn end.
`command` is required even with `commandWindows` set. Never write an empty
`commandWindows`: Codex selects it on Windows and then skips the hook. Both
fields hold the same string because `commandWindows` is Codex's documented
field for a Windows command and keeps the entry correct should a later Codex
run `command` through another shell on Windows, while the copy in `command`
costs one line.

Write the command strings and the timeout exactly as shown. Codex's trust
covers a hash of the event, the matcher, the command string and the timeout,
so an entry worded differently is a different hook, and one that changes after
the user trusted it reads as modified and stops running. On Windows the hash
covers the selected `commandWindows` string. The timeout is 2760 seconds, a
minute above the wait's 45 minutes.

## Making the edit

Make the edit with your own tools, so it lands as this outcome:

- The file is `$env:USERPROFILE\.codex\hooks.json`.
- With an existing `hooks.json`, the entry is appended as a new matcher
  group at the end of `hooks.Stop`, every existing group and handler stays in
  its place and order, and every other key and value is kept. Codex keys its
  trust by group and handler index, so a group inserted ahead of the user's,
  or a handler added into one of their groups, moves their trusted hooks to
  new keys and Codex skips them until they are trusted again.
- With no `hooks.json`, the file holds only this entry.
- The file parses as JSON afterwards.

First show the user the change: the diff against the existing file, or the
whole new file. Showing it is the consent step, as in the shared scripts
check. Before you edit, read the existing file. When it does not parse as
JSON, leave it untouched and report "Codex `Stop` hook not installed:
`~/.codex/hooks.json` does not parse".

When the sandbox refuses the write, make it with escalated permissions,
outside the sandbox, which raises the approval prompt.
A denied prompt or a failed write is reported as not installed, naming the
registration as the change that did not land.

## Trust

Codex runs a new hook only once the user trusts it. When you have just added
the registration, tell the user: "Trust the hook in `/hooks`. Trusting it
there also turns it on in this running Session." When the registration was
already present, say nothing about trust: replacing the script's copy keeps
the trust, because the trust covers the registration and not the script's
contents.

## The status report

Setup's final status report names the hook's state in one line: passed;
registered, with the trust step; or not installed, with the reason.
