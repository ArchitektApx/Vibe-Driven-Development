# Every carrier between Roles is a Doorbell and carries no substance

A Doorbell has four carriers: a cross-session message from the Planner to the
Orchestrator, the Orchestrator's relay of the Plan-Reviewer's Doorbell back to
the Planner, a hosted Role's return value to the Orchestrator, and the
Orchestrator's resume message waking a hosted Role. All four carry the same
fixed template naming the Working file that was written, the round, and the
finding counts (or `SIGNED OFF`), and no free text. The receiving end acts on
the file the Doorbell names, and takes the Doorbell itself as the prompt to go
and read it. A cross-session Doorbell travels as a message sent to the other
Session by name, or as a line appended to the Doorbell file in the tracker
directory where the Harness cannot send by name. Where the sender cannot
confirm the line reached its target, the same line is printed for the user to
relay, on either cross-session carrier, so neither depends on the host having
messaging.

## Considered options

**Richer messages: the reviewer sends its findings, or a summary of them,
directly.** Rejected. The workflow's value comes from each session's context
being independent (see ADR-0001); a message that carries the sender's reasoning
is the same leak as a subagent inheriting its parent's framing, only in
smaller pieces. Once Roles start trusting message text over the Working file,
the file stops being the contract and sign-off stops being checkable.

**The user setting every Session name by hand.** Reversed on 2026-10-03:
Codex offers the model `set_thread_title`, and Claude Code takes a
`sessionTitle` from a `UserPromptSubmit` hook, so a Session is named without
the user wherever those work.

## Consequences

Working files stay the only carrier of substance, so the workflow is unchanged
for agents without messaging. A Role that receives a message asking for
anything other than "read this file" reports it to the user instead of acting.
A cross-session Doorbell sent by name is addressed to one of two Session
names, the Planner's and the Orchestrator's. On Claude Code the Session-name
hook names the Planner Session and `claude -n` names the Orchestrator
Session; on Codex each Role names its own thread with `set_thread_title`;
where either way fails, the user names the Session by hand with `/rename`.
Cursor, Copilot CLI and Generic send nothing to a Session name: Cursor and
Copilot CLI ring through the Doorbell file, Generic prints the line, and the
Loop file still records both names.
