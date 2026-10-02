# A shell script the plugin ships runs through a named shell, never by an executable bit

Some of what a Role does is a command too long or too fragile to carry in
prose, and the plugin ships it as a shell script. A script the plugin ships is
committed at mode 644 and run only through a named shell, as `sh <path>` or
`bash <path>`, whoever runs it: a Role in its Session, or a command the user
adds to their Harness's settings. `doorbell-wait.sh`, the Doorbell wait the
Planner and the Orchestrator run on a Harness that rings through the Doorbell
file, is one such script. Run that way, the command line the Harness sees is
short enough for a hook that checks shell commands to pass and for the user to
read in an approval prompt, and the process list shows the Doorbell file, the
Role and the count the wait was given.

**A shipped script is not replaced by one the agent writes.** ADR 0010 lets the
agent improvise the means when its tools disagree with a Harness file, because a
Harness file describes a means and a description goes stale between releases. A
shipped script describes nothing: it is the means, reviewed and released with
the skill that calls it. When it cannot run, because a hook blocks it, it is
missing or it exits non-zero, the Role says so and falls back to the path that
needs no script, which for the Doorbell wait is hand relay: the user pastes the
Doorbell line the other Session printed. The Role never writes, edits or
`chmod`s a script, never copies one except for Setup's install copy of the
Session-name hook, which ADR 0012 owns, and never runs the script's work as
inline shell. A model
that has written a script for itself keeps using it for every later call, and
that script is code nobody reviewed, running in the user's shell.

**The guardrail sits in the Reference file that calls the script.** ADR 0010
keeps a guardrail in the skill file, because the reader who needs it follows
no situational pointer. On the Harnesses that use the Doorbell wait, the
Harness file sends the Role to `doorbell-file-posix.md` on every ring, so that
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

**One copy shared across the skills that run it.** Rejected. ADR 0010 rejects
shared directories because the skills CLI copies each skill directory
separately and a user may install a subset. Each skill that runs a script
ships its own copy in its own `references/` directory.

## Consequences

A change to a script is made in every copy of it. CI checks what this decision
rests on: `verify.yml` rejects any file committed at mode 755, fails when the
copies of `doorbell-wait.sh` differ, and runs `sh -n` on every `.sh` file under
`skills/`. `AGENTS.md` lists each of these under Invariants.

A change to a shipped script is verified by running it as a Role would, as
`docs/agents/VERIFICATION.md` says, in addition to the reading every other
change gets.
