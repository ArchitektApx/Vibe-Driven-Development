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
it, or a wait armed at a count the file no longer reaches never fires.

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
Orchestrator, your own included, never count. Run both as written, with `sh`
and the path quoted: the script has no executable bit and never gets one.

```sh
sh "<script path>" .scratch/<feature-slug>/doorbells Planner
sh "<script path>" .scratch/<feature-slug>/doorbells Planner <armed count>
```

Hold exactly one wait while you expect a relay, armed at the count the count
form just printed. A wait is held until its output or `TIMEOUT` arrives, until
the count form prints more than its armed count, since it exits within one
10-second poll of such a line, or until your Session restarts. So:

- After a ring, arm when you hold no wait.
- On a pasted relay while you hold a wait, run the count form first. Above the
  wait's armed count, the wait has ended: act, ring and arm as usual. At or
  below it, the line never reached the file and the wait still runs: act and
  ring, and do not arm.
- After the Plan-Reviewer's `SIGNED OFF`, do not arm: no relay comes after it.
- On `TIMEOUT`, ask the user whether to keep waiting. On yes, re-arm with the
  count this wait was first armed with, so a ring during the question fires at
  once. On no, hand relay this wait: the user pastes the next relay, and your
  next ring arms as usual.

## On wake

Act on the newest line printed only. Drop the time and the address and handle
the rest like a pasted Doorbell line, as "Receiving a message from another
session" in `SKILL.md` says, its rule on reporting a line that asks for more
than reading a Working file included.

A Doorbell is a duplicate when its sender, the Role the line names first
(`VDD Plan-Reviewer` on every relay to you), and its round match one you
already acted on in this Session; the rest of the line does not count, so the
Orchestrator's shorter restart relay is caught too. Say so in one line and act
on nothing else. A duplicate that came out of the wait you hold leaves you
none: arm again at the current count. One by paste, a second completion event,
or the late completion event of a wait the count form already ended changes
nothing; each wait's command line shows its armed count, which tells the waits
apart.

## When the script cannot run

A form cannot run when a hook that checks shell commands blocks it, the
script is not at its path, or it exits non-zero. Say in one line what failed
and hand relay this wait; your next ring tries the script again. Never write,
edit, copy or `chmod` a script, and never run the wait as inline shell. Your
Harness file's "Trust your live tools over this file when they disagree"
covers a stale description of a means; the script is the means itself,
reviewed with this skill, and hand relay costs the user only a paste.
