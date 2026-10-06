# The Codex `Stop` hook on macOS and Linux

## What the hook does

A Codex Session cannot be woken by a background shell that exits, so on
Codex the Planner and the Orchestrator wait through a `Stop` hook. A Role that
expects a Doorbell writes an armed file, `armed-<thread id>` in the tracker
directory, before its turn ends. At the turn's end the hook claims that file,
runs the Doorbell wait with no model turn, and continues the Session with the
Doorbell line as its prompt. In a project whose `LOOP.md` does not say
`Harness: Codex` the hook prints nothing: the script exits on shell builtins
alone.

The script is [`vdd-codex-stop.sh`](vdd-codex-stop.sh), installed into the
shared directory with `doorbell-wait.sh` by the shared scripts check. Codex
runs hooks outside its sandbox, which is why it is a short script a user can
read in full. It does not need `jq`. WSL counts as Linux.

## The check

Register the hook only when its copy is in the shared directory, which the
shared scripts check has just confirmed or installed. When that copy is not
there, register nothing and report "Codex `Stop` hook not installed: its
script is not in the shared directory".

The registration is present when a `Stop` hook command in
`~/.codex/hooks.json` or in `~/.codex/config.toml` contains
`vdd-codex-stop.sh`. `grep -n vdd-codex-stop.sh` on the two files finds the
candidate lines; read the file around a hit to confirm it sits under `Stop`.

Leave a present registration exactly as it is, whatever its form: a user who
wrote it differently keeps it. When it is present, the check passes and you
say nothing further about it, trust included.

## The entry

When no registration is present, add this entry to `~/.codex/hooks.json`,
`<directory>` being the shared directory's absolute path that the shared
scripts check resolved:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "sh \"<directory>/vdd-codex-stop.sh\" || true",
            "timeout": 2760
          }
        ]
      }
    ]
  }
}
```

The handler carries `command` and no other command field.

Write the command string and the timeout exactly as shown. Codex's trust
covers a hash of the event, the matcher, the command string and the timeout,
so an entry worded differently is a different hook, and one that changes after
the user trusted it reads as modified and stops running. The timeout is 2760
seconds, a minute above the wait's 45 minutes.

## Making the edit

Make the edit with your own tools, so it lands as this outcome:

- The file is `~/.codex/hooks.json`.
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
