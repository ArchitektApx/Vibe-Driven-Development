# Setup installs the shared scripts, and on Codex registers the Stop hook

On every Harness but Generic the Planner and the Orchestrator ring each other
through the Doorbell file, and they run two shell scripts the plugin ships:
`doorbell-wait.sh`, the Doorbell wait, and on Codex `vdd-codex-stop.sh`, the
`Stop` hook that runs the wait for a Session a background shell cannot wake.
Each has a PowerShell form for native Windows, `doorbell-wait.ps1` and
`vdd-codex-stop.ps1`. Each ships once, as a Reference of `vdd-setup`, at
mode 644. Setup copies the `.sh` pair into the shared directory,
`${XDG_DATA_HOME:-$HOME/.local/share}/vdd/`, and on native Windows the `.ps1`
pair, never a `.sh`, into `%LOCALAPPDATA%\vdd\`, on every Harness but
Generic, as a standard check with no opt-in question: it compares each copy
with the shipped file byte for byte, by `cmp` or by `Get-FileHash`, shows the
user what it will copy, and copies with `cp` or `Copy-Item`. A Role resolves
the directory once per Session and runs the wait by its plain absolute path,
so a hook that checks shell commands and an approval prompt see no expansion.

Setup copies the scripts out of the plugin because the plugin's install path
changes with every version and differs per Harness, so a command pointing into
it would break on the next update. The directory follows `XDG_DATA_HOME`
because the copies are application data the user may keep elsewhere. On
native Windows it sits under `%LOCALAPPDATA%`, where Windows keeps per-user
application data, because a Windows user does not know `XDG_DATA_HOME`. Run
from there through a named shell, by a Role or by a command in the user's own
settings, a script is not executed from the plugin, and the plugin still
declares no hook.

On Codex, Setup also registers the hook in `~/.codex/hooks.json` as a `Stop`
handler running `sh "<directory>/vdd-codex-stop.sh" || true` with a timeout
of 2760 seconds, after showing the user the diff, and only when the hook's
copy is in the shared directory. The `|| true` is there because Codex reads a
`Stop` hook that exits 2 with stderr as a block, repeated without limit, and
dash exits 2 on a missing script, so a registration that outlives its script
would loop every Codex Session. A registration already present in `hooks.json` or
`config.toml` is left exactly as it is. Codex's trust covers a hash of the
event, the matcher, the command string and the timeout, not the script's
contents, so the entry is written exactly, and a later Setup run that replaces
the script's copy keeps the trust. Setup tells the user to trust the hook in
`/hooks` only when it has just added the registration, because that trust
write also turns the hook on in the running Session. The entry is appended as
a new matcher group at the end of `hooks.Stop`, leaving every existing group
and handler in its place and order, because Codex keys its trust by group and
handler index and a moved hook loses its trust.

On native Windows the handler carries `command` and `commandWindows`, both set
to `$f='<directory>\vdd-codex-stop.ps1';if(Test-Path -LiteralPath $f){powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f}`.
Codex runs the selected string through PowerShell with `-Command` there,
Windows PowerShell 5.1 where PowerShell 7 is absent, so the string uses no
`||`, which 5.1 cannot parse. The `Test-Path` guard keeps a registration that
outlives its script silent, where `-File` on a missing path prints usage text
that Codex reports as invalid hook output at every turn end. `command` is
required in any entry, and Codex 0.160.0 runs it through the same PowerShell
when `commandWindows` is absent; `commandWindows` is Codex's documented field
for a Windows command and keeps the entry correct should a later Codex run
`command` through another shell on Windows. Writing the same string into both
costs one line. On Windows the trust hash covers the
selected `commandWindows` string, so the new entry is trusted once in
`/hooks`, as on macOS and Linux. Setup adds no `commandWindows` to an
existing macOS or Linux entry, and on Windows finds a present registration by
`vdd-codex-stop.ps1` in either field.

The hook is plain POSIX `sh` with no `jq`, and its PowerShell form needs no
`jq` either: Codex runs hooks outside its sandbox, so the user should be able
to read every line that runs there, and on the turn ends of every project
that is not a Codex loop the `sh` form exits on shell builtins alone.

## Considered options

**Correction: on native Windows Setup installs the PowerShell forms of both
scripts and registers the hook, rather than skipping the install and the
registration there.**

**`XDG_DATA_HOME` on native Windows too.** Rejected. Windows users do not know
the variable, and `%LOCALAPPDATA%` is where Windows keeps per-user application
data.

**A hook declared in the plugin's `hooks/hooks.json`.** Rejected. A plugin
hook runs on every turn in every project where the plugin is enabled, with no
per-hook consent, and Cursor, Copilot CLI and Claude Code also read a
Claude-format `hooks/hooks.json` from an installed plugin, each sending its
own payload. It would also break the "No executable surface" Invariant.

**The Codex hook copied to `~/.codex/hooks/`.** Rejected. The hook runs the
wait from its own directory, so the two scripts sit side by side in the one
directory every Harness uses, and Setup keeps one install rather than two.

**`jq` to read the hook input.** Rejected. Measured on macOS, one `sed`
reads `session_id` in about 3 ms against about 5.7 ms for `jq`, and the fast
path that decides the cost starts no process at all, so `jq` would only add a
dependency.

**An opt-in offer.** Rejected. Setup runs at the start of every loop and has
no place to store a decline, so it would ask again each time. Showing the
change is the consent step, and the user's permission mode raises any prompt
the write needs.

**The Session-name hook.** Setup installs none and leaves an installed copy
and its registration alone, because no Doorbell goes to a Session by name.

## Consequences

Setup offers the install again after the user denies the write, since no
decline is stored. Until a copy lands, that Harness's Doorbells print for the
user to paste.

The hook does nothing unless the Loop file says `Harness: Codex`, and it claims
only the armed file named after its own Session, so a Planner and an
Orchestrator in two Codex Sessions of one project never wait on each other's
behalf.

A change to the hook entry is made in both of its strings, the `sh` one and
the PowerShell one, since each is written byte for byte and trusted by its
hash.

The `Reject executable surface` step in `verify.yml` is unchanged: the scripts
are files at mode 644 under `skills/`, the plugin manifests declare no hook,
and no `hooks.json` is committed. The "No executable surface" Invariant in
`AGENTS.md` names the shared directory install. ADR 0011's rule that a Role
never copies a script names this install copy as the exception.
