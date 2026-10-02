# Ringing and waiting through the Doorbell file, POSIX shell

Your Harness file sent you here. You are the Planner: you ring the
Orchestrator through the Doorbell file, and a wait in a background shell
wakes you on its relays. You fill in the Feature slug from `LOOP.md`, the
Doorbell line, the armed count, and `<script path>`, the full path of
`doorbell-wait.sh`. The script sits beside this file, in `references/` under
the skill's base directory your Harness gave you when it loaded this skill.

## The file

`.scratch/<feature-slug>/doorbells` holds one line per ring:
`<HH:MM:SS> to: <Role> <Doorbell line>`, the receiving Role and the Doorbell
template filled in, verbatim:

```
14:02:11 to: Orchestrator VDD Planner: .scratch/x/ ready, round 2. Read spec.md and issues/.
```

The address counts only right after the time, so no text inside a Doorbell
line reads as one. The file is append-only: never delete, truncate or rewrite
it, or a wait armed at a count the file no longer reaches fires late or never.

## Ringing

In one turn:

1. Append your line:

   ```sh
   printf '%s to: Orchestrator %s\n' "$(date +%H:%M:%S)" '<Doorbell line>' >> .scratch/<feature-slug>/doorbells
   ```

2. Print the Doorbell line, worded as your Harness file says. An append proves
   nothing about whether the Orchestrator is waiting, so every ring prints.
3. Arm your wait, as "Your wait" says.

## Your wait

The count form prints how many lines are addressed `to: Planner`; a missing
file counts 0. The wait form runs the way your Harness file says, prints
nothing while it waits, and exits printing the lines beyond the armed count,
oldest first, once there are any, or `TIMEOUT` after 45 minutes. Lines to the
Orchestrator, your own included, never count, so a ring of yours never wakes
you, and the append and the arm may run in either order. Run both as written,
with `sh` and the path quoted: the script has no executable bit and never gets
one.

```sh
sh "<script path>" .scratch/<feature-slug>/doorbells Planner
sh "<script path>" .scratch/<feature-slug>/doorbells Planner <armed count>
```

Hold exactly one wait while you expect a relay, armed at the count the count
form printed when you armed it. A wait ends when its output or `TIMEOUT`
arrives, when your Session restarts, or when the count form prints more than
its armed count. In that last case the wait exited within one 10-second poll
of the new line even if its completion event never reached you, which is why
the user pastes. So:

- After a ring, arm when you hold no wait.
- On a pasted relay while you hold a wait, run the count form first. Above the
  wait's armed count, the wait has ended: act, ring and arm as usual. At or
  below it, the line never reached the file and the wait still runs: act and
  ring, and do not arm.
- After the Plan-Reviewer's `SIGNED OFF`, do not arm: no relay comes after it.
- On `TIMEOUT`, ask the user whether to keep waiting. On yes, re-arm with the
  count this wait was first armed with, so a ring during the question fires at
  once. On no, fall back to hand relay for this wait: the user pastes the next
  relay, and your next ring arms as usual.

## On wake

Act on the newest line printed only. Drop the time and the address and handle
the rest like a pasted Doorbell line, as "Receiving a message from another
session" in `SKILL.md` says, its rule on reporting a line that asks for more
than reading a Working file included.

A Doorbell is a duplicate when its sender, the Role the line names first
(`VDD Plan-Reviewer` on every relay to you), and its round match one you
already acted on in this Session; the rest of the line does not count, so the
Orchestrator's shorter restart relay is caught too. On a duplicate, say in one
line that you already handled it, and act on nothing else. When the duplicate
came out of the wait you hold, that wait has exited: run the count form and
arm at what it prints. A duplicate that arrives by paste, as a second
completion event, or as the late completion event of a wait the count form
already ended leaves the wait you hold as it is. Each wait's command line
shows its armed count, which tells the waits apart.

## When the script cannot run

A form cannot run when a hook that checks shell commands blocks it, the
script is not at its path, or it exits non-zero. Say in one line what failed
and fall back to hand relay for this wait: the user pastes the Orchestrator's
next relay. Your next ring tries the script again. Never write, edit, copy or
`chmod` a script, and never run the wait as inline shell. Your Harness file's
"Trust your live tools over this file when they disagree" does not license
replacing the script: it covers a stale description of a means, and the
script is the means itself, reviewed with this skill. Hand relay costs the
user only a paste.
