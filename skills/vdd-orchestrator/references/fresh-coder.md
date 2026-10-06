# A fresh Coder

You read this file when `LOOP.md` says `Fresh Coder: over <n>`, or when the
user asks for a fresh Coder.

The user can ask for a fresh Coder at any round, whatever the `Fresh Coder:`
line says. On that request, the next Coder round is a fresh spawn, with the
same Spawn prompt and that round's number.

Under `Fresh Coder: over <n>`, on every Coder return, read the context size
your Harness reports for the finished subagent, where your Harness file says
it sits. Under the limit, resume. Over it, the next Coder round is a fresh
spawn, with the same Spawn prompt and that round's number; the Coder's state
is on disk as `FIXES.md` and the commits. Round 1 has no earlier return to
read a size from, so it gets no check.

The spawn line of a fresh Coder ends with the size that sent it there:
`Spawning Coder, <model>, round <n>, fresh at <size>.`, or `fresh on request`
when the user asked for it.

With no size readable, tell the user once that the check cannot run and that
they can ask for a fresh Coder at any round. Resume as usual until they do.
