# Respawning a hosted Role

You read this file when `loop show` prints anything but `Fresh Coder: never`,
or when the user asks for a respawn.

A respawn spawns a Role anew for its next round, in place of a resume, with
the same Spawn prompt and that round's number. The Role's state is on disk:
its Working files and the commits.

## The `Fresh Coder:` line

Before each Coder round after the first:

- `every round`: respawn the Coder.
- `over <n>k`: on every Coder return, read the context size your Harness
  reports for the finished subagent, where your Harness file says it sits.
  Respawn the Coder for the next round when the size passed `<n>` thousand
  tokens, and resume it otherwise.
- `never`: resume the Coder.

Under `over <n>k` with no size reaching you, tell the user once that the check
cannot run and that they can ask for a respawn at any round, then resume as
under `never`.

## The user's request

The user can ask for any hosted Role to be respawned, whatever the line says:

- the Plan-Reviewer when the Planner's next Doorbell arrives;
- the Coder at its next round;
- the Code-Reviewer at its next round.

The request holds until that spawn. A respawn the user chooses in answer to a
`BLOCKED` is a request, and it spawns the Role now for the round it did not
finish.

## What stays a resume

Whatever the line says, these resume the same subagent:

- the answer to a `QUESTION`;
- the one resume that restates the return contract;
- the user's answer to a `BLOCKED`, where the user chooses resume.

## The spawn line

A respawn's spawn line ends with its reason:

- `Spawning Coder, <model>, round <n>, respawn every round.`
- `Spawning Coder, <model>, round <n>, respawn at <size>.`
- `Spawning <Role>, <model>, round <n>, respawn on request.`

A first spawn and a spawn after a restart are not respawns and keep the plain
line.
