# Cross-session messages between Roles are Doorbells and carry no substance

Claude Code can deliver a message from one session to another, which removes
the copy-paste between the terminals a Loop runs in. We use it, but only as a
Doorbell: a fixed template naming the Working file that was written, the round,
and the finding counts (or `SIGNED OFF`). The receiving Role reads the file;
the message itself is never acted on. Where an agent has no messaging tools the
same line is printed for the user to relay, so the workflow does not depend on
Claude Code.

## Considered options

**Richer messages: the reviewer sends its findings, or a summary of them,
directly.** Rejected. The workflow's value comes from each session's context
being independent (see ADR-0001); a message that carries the sender's reasoning
is the same leak as a subagent inheriting its parent's framing, only in
smaller pieces. Once Roles start trusting message text over the Working file,
the file stops being the contract and sign-off stops being checkable.

## Consequences

Working files stay the only carrier of substance, so the workflow is unchanged
for agents without messaging. A Role that receives a message asking for
anything other than "read this file" reports it to the user instead of acting.
Session names must be set by the user, since no agent can rename its own
session; every Role's hand-off message therefore repeats the naming
instruction.
