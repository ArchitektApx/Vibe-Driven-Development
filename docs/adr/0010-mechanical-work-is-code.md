# Mechanical work is code

A step with one right outcome goes into the VDD tool, not into a skill:
lookups, copies, counts, building a string or a file, and any state the
model would otherwise carry across turns. Where a step needs a fact only the
Session knows, the model passes it as an argument and code does the rest.
Judgment, the conversation with the user, consent and the Harness's own tool
calls stay with the model. Code checks a mechanical result, never the model
rereading its own work, and a step the user must take is designed away
first and relayed verbatim only where it cannot be. Prose is followed
differently by every model and run; code runs the same every time, and a
test pins it.

## Considered options

**Prose, fixed slip by slip.** Rejected: 22 of the first 23 behaviour fixes
went into prose and 4 recurred, and the Codex hook step failed 3 of 3 as
prose and passed 3 of 3 as a command taught by `--help`.
