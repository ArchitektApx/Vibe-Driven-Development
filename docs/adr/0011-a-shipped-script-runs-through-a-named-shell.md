# A shell script the plugin ships runs through a named shell, never by an executable bit

Some of what a Role does is a command too long or too fragile to carry in
prose, and the plugin ships it as a shell script. A script the plugin ships is
committed at mode 644 and run only through a named shell, as `sh <path>` or
`bash <path>`, and on native Windows as `powershell.exe -NoProfile
-ExecutionPolicy Bypass -File <path>`, whoever runs it: a Role in its Session,
or a command the user adds to their Harness's settings. `doorbell-wait.sh`,
the Doorbell wait the Planner and the Orchestrator run on a Harness that
rings through the Doorbell file, is one such script. Run that way, the
command line the Harness sees is short enough for a hook that checks shell
commands to pass and for the user to read in an approval prompt, and the
process list shows the Doorbell file, the Role and the count the wait was
given.

**On native Windows a shipped script runs as its `.ps1`.** Each script ships a
PowerShell form beside its `.sh`, written for Windows PowerShell 5.1 and
PowerShell 7 alike, and on native Windows that form runs, through the
PowerShell line above, on every Harness and from every shell, Git Bash
included, even where `sh` resolves. Every `.sh` in a Windows plugin cache is
checked out with CRLF line endings, so `sh` fails on it at the first line
ending, and no `.gitattributes` ships to change that: on Windows no `.sh`
runs, and PowerShell runs a `.ps1` with CRLF. `powershell.exe` is the name
because every Windows client has it, where a command naming `pwsh` fails on a
machine with 5.1 only. A Role tells native Windows from macOS and Linux by
the platform its Harness reports, and WSL reports Linux. A command a Role
types into its own Session rather than a script it runs, such as the ring or
Setup's install check, takes the form of the shell it runs in: the POSIX form
in Git Bash, the PowerShell form in PowerShell.

**The repository ships one copy of each script, in `vdd-setup`.** Setup copies
each one into the shared directory, `${XDG_DATA_HOME:-$HOME/.local/share}/vdd/`,
or `%LOCALAPPDATA%\vdd\` on native Windows, and that copy is what every Role
runs, by its plain absolute path. One copy
holds because nothing a Role runs depends on which skill directories a user
installed: the README tells a skills-CLI user to take every `vdd-*` skill,
Setup among them; Setup runs at Start-Loop's first step, so the directory is
filled before any Role waits; and a script missing there falls back to hand
relay like any script that cannot run. ADR 0010's rejected "one shared
directory of Reference files" still stands, because it concerns Reference
files a Role reads, which ship inside the skill, and not a runtime copy Setup
installs. ADR 0012 owns the install.

**A shipped script is not replaced by one the agent writes.** ADR 0010 lets the
agent improvise the means when its tools disagree with a Harness file, because a
Harness file describes a means and a description goes stale between releases. A
shipped script describes nothing: it is the means, reviewed and released with
the plugin. When it cannot run, because a hook blocks it, it is missing or it
exits non-zero, the Role says so and falls back to the path that needs no
script, which for the Doorbell wait is hand relay: the user pastes the Doorbell
line the other Session printed. The Role never writes, edits or `chmod`s a
script, never copies one except for Setup's install copy, and never runs the
script's work as inline shell. A model that has written a script for itself
keeps using it for every later call, and that script is code nobody reviewed,
running in the user's shell.

**The guardrail sits in the Reference file that calls the script.** ADR 0010
keeps a guardrail in the skill file, because the reader who needs it follows
no situational pointer. On the Harnesses that use the Doorbell wait, the
Harness file sends the Role to `doorbell-file.md` on every ring, so that
Reference file is behind no situational pointer: every Role that runs the wait
has just read it. The command that fails also comes from that file, so the
rule against replacing the script sits beside the command it governs. In
`SKILL.md` the rule would name a script that a Role on any other Harness never
runs, wording that ADR 0010's Harness criterion moves out of the skill file.

## Considered options

**The wait as an inline `sh -c` command in the Reference file.** Rejected. A
hook that checks shell commands blocked it on Cursor, since the wait assigns a
command substitution inside a loop body and runs a `[ ... ]` test inside a
compound command. Once blocked, the Planner wrote its own wait script in the
tracker directory, `.scratch/<feature-slug>/`, made it executable and used it
for every later wait.

**A copy of the script made into `.scratch/<feature-slug>/` at runtime.**
Rejected. It is an extra step the model can get wrong, and it has the same
shape as the script the Planner improvised: a file in the tracker directory
that the agent put there.

**An executable bit, so the script runs by its path alone.** Rejected. A file
committed at mode 755 reaches every installer's machine as a file any process
there can execute directly. Run through a named shell, the script needs no
bit, and the command line names the shell that runs it.

**`pwsh` as the named shell on Windows.** Rejected. PowerShell 7 is an
install of its own, and a Windows machine with Windows PowerShell 5.1 alone
would fail on every call.

**A `.gitattributes` that checks the `.sh` files out with LF on Windows.**
Rejected. It would let `sh` run them in Git Bash, but Codex on Windows gives a
Role PowerShell and never Git Bash, and the `.ps1` runs from both shells.

**A copy in each skill that runs a script.** The repository ships one copy,
in `vdd-setup`, because Setup fills the shared directory before any Role runs
a script, for the reasons above.

## Consequences

A change to a script is made once, in `vdd-setup`, and reaches a user's
machine at the next Setup run, which finds the installed copy differs and
replaces it. A change to a script's behaviour is made in its `.sh` and its
`.ps1` together. CI checks what this decision rests on: `verify.yml` rejects
any file committed at mode 755, runs `sh -n` on every `.sh` file under
`skills/`, parses every `.ps1` there and rejects the tokens Windows PowerShell
5.1 cannot parse, and rejects a non-ASCII byte in either. `AGENTS.md` lists
each of these under Invariants.

A change to a shipped script is verified by running it as a Role would, as
`docs/agents/VERIFICATION.md` says, in addition to the reading every other
change gets.
