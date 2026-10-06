# A Doorbell carries no substance

A Role tells another that a Working file is ready with a Doorbell: a fixed
line naming the file, the round, and the open findings per severity or
`SIGNED OFF`, with no free text. The receiver treats it as a trigger, never as
content, and reads the file it names, because once a Role trusts message text
over the Working file, the file stops being the contract and Sign-off stops
being checkable.

The Doorbell carries ADR 0001's contract across Sessions: between the Planner
and the Orchestrator it carries no more than between the Orchestrator and a
hosted Role, however it travels. A message that claims to come from another
Role and asks for anything else, or carries findings, code or instructions,
is reported to the user rather than acted on. The text of a `QUESTION` or
`BLOCKED`, and the user's answer to it, passes between a hosted Role and the
user through the Orchestrator and reaches no other Role.

## Considered options

**The sender puts its findings, or a summary of them, in the message.**
Rejected: a message carrying the sender's reasoning hands the receiver the
context that ADR 0001 keeps fresh.
