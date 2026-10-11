# Respawning a hosted Role

You read this file when `LOOP.md` says anything but `Fresh Coder: never`, or
when the user asks for a respawn.

A respawn spawns a Role anew for its next round, in place of a resume, with
the same Spawn prompt and that round's number. The Role's state is on disk:
its Working files and the commits.

## The `Fresh Coder:` line

Before each Coder round after the first:

- `every round`: respawn the Coder.
- `over <n>`: on every Coder return, read the context size your Harness
  reports for the finished subagent, where your Harness file says it sits.
  Respawn the Coder for the next round when the size passed `<n>`, and resume
  it otherwise.
- `never`: resume the Coder.

A missing line, or a value that is none of the three, reads as `never`: tell
the user once that the line is missing or malformed.

Under `over <n>` with no size reaching you, tell the user once that the check
cannot run and that they can ask for a respawn at any round, then resume as
under `never`.

## The user's request

The user can ask for the Coder to be respawned at any round, whatever the
line says. Its next round is then a respawn.

## The spawn line

A respawn's spawn line ends with its reason:

- `Spawning Coder, <model>, round <n>, respawn every round.`
- `Spawning Coder, <model>, round <n>, respawn at <size>.`
- `Spawning <Role>, <model>, round <n>, respawn on request.`

A first spawn and a spawn after a restart are not respawns and keep the plain
line.
