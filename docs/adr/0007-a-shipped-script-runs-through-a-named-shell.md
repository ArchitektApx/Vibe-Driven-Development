# A shipped script runs through a named shell

A command too long or too fragile to carry in prose ships as a script,
committed at mode 644 and run only through a named shell: `sh` on macOS and
Linux, and on native Windows its PowerShell form through `powershell.exe`. No
file the plugin ships is executable, so nothing on an installer's machine runs
it by its path, and the command line a hook or an approval prompt sees is
short and names the shell and the script.

A Role runs only the scripts the plugin ships, as Setup installed them: it
never writes, edits or `chmod`s one, never copies one beyond the install ADR
0008 describes, and never runs a script's work as inline shell. When a script
cannot run, the Role says so and falls back to the path that needs no script.
A shipped script was reviewed and released with the plugin; one the agent
writes is unreviewed code in the user's shell, and a model that has written
one keeps using it.

On native Windows every Role runs the `.ps1`, from every shell, Git Bash
included. `powershell.exe` is the name because Windows PowerShell 5.1 is on
every Windows client and PowerShell 7 is not.

## Considered options

**The command inline in a Reference file, as `sh -c`.** Rejected: a hook that
checks shell commands blocked it on Cursor, and the Planner then wrote and
used a wait script of its own.

**A `.gitattributes` that checks the `.sh` files out with LF on Windows.**
Rejected: Codex on Windows gives a Role PowerShell and never Git Bash, and the
`.ps1` runs from both.
