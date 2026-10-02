# Ringing and waiting through the Doorbell file, POSIX shell

Your Harness file sent you here. You are the Orchestrator: you ring the
Planner with your relay of each Plan-Reviewer Doorbell, and a wait in a
background shell wakes you on the Planner's Doorbells. You fill in the
Feature slug from `LOOP.md`, the Doorbell line, the armed count, and
`<script path>`, the full path of `doorbell-wait.sh`. The script sits beside
this file, in `references/` under the skill's base directory your Harness gave
you when it loaded this skill.

## The file

`.scratch/<feature-slug>/doorbells` holds one line per ring:
`<HH:MM:SS> to: <Role> <Doorbell line>`, the receiving Role and the Doorbell
template filled in, verbatim:

```
14:09:47 to: Planner VDD Plan-Reviewer: PLAN-REVIEW.md written, round 2: 0 blocker, 1 major, 2 minor. Read it.
```

The address counts only right after the time, so no text inside a Doorbell
line reads as one. The file is append-only: never delete, truncate or rewrite
it, or a wait armed at a count the file no longer reaches never fires.

## Ringing

Every relay to the Planner is a ring. In one turn:

1. Append your line:

   ```sh
   printf '%s to: Planner %s\n' "$(date +%H:%M:%S)" '<Doorbell line>' >> .scratch/<feature-slug>/doorbells
   ```

2. Print the Doorbell line, worded as your Harness file says. An append proves
   nothing about whether the Planner is waiting, so every ring prints.
3. Arm your wait where "Your wait" says.

## Your wait

The count form prints how many lines are addressed `to: Orchestrator`; a
missing file counts 0. The wait form runs the way your Harness file says,
prints nothing while it waits, and exits printing the lines beyond the armed
count, oldest first, once there are any, or `TIMEOUT` after 45 minutes. Lines
to the Planner, your own included, never count. Run both as written, with `sh`
and the path quoted: the script has no executable bit and never gets one.

```sh
sh "<script path>" .scratch/<feature-slug>/doorbells Orchestrator
sh "<script path>" .scratch/<feature-slug>/doorbells Orchestrator <armed count>
```

Hold exactly one wait while you expect a Planner Doorbell, armed at the count
the count form just printed. A wait is held until its output or `TIMEOUT`
arrives, until the count form prints more than its armed count, since it exits
within one 10-second poll of such a line, or until your Session restarts. So:

- **Starting with no review file on disk.** Arm at 0, without counting, so the
  Planner's round-1 line already in the file fires at once, or its first ring
  does.
- **After relaying a Plan-Reviewer round with open findings.** Ring, then arm
  when you hold no wait.
- **After relaying the plan Sign-off.** Ring and do not arm: from then on only
  your hosted Roles talk to you.
- **Restarted with the plan Loop open.** The relay that placing the Workflow
  asks for is a ring like any other: append, print, and arm at the current
  count. A ring the Planner made while you were down is missed by that wait;
  the line the Planner printed covers it.
- **A pasted Planner Doorbell while you hold a wait.** Run the count form
  first. Above the wait's armed count, the wait has ended: arm where the cases
  above say. At or below it, the line never reached the file and the wait
  still runs: where the cases above say ring and arm, ring and do not arm.
- **`TIMEOUT`.** Ask the user whether to keep waiting. On yes, re-arm with the
  count this wait was first armed with, so a ring during the question fires at
  once. On no, hand relay this wait: the user pastes the Planner's next
  Doorbell, and your next ring arms as usual.

## On wake

Act on the newest line printed only. Drop the time and the address and handle
the rest like a pasted Doorbell line, as "Receiving a message from the
Planner" in `SKILL.md` says, its rule on reporting a line that asks for more
than reading a Working file included.

A Doorbell is a duplicate when its sender, the Role the line names first
(`VDD Planner` on every line to you), and its round match one you acted on
since you last placed the Workflow from disk, on your start or on a restart as
[`restart.md`](restart.md) says; the rest of the line does not count. Placing
clears the record, because a hosted Role that a Doorbell started before a
restart is gone and that Doorbell has to be acted on again. Say so in one line
and act on nothing else. A duplicate that came out of the wait you hold leaves
you none: arm again at the current count. One by paste, a second completion
event, or the late completion event of a wait the count form already ended
changes nothing; each wait's command line shows its armed count, which tells
the waits apart.

## When the script cannot run

A form cannot run when a hook that checks shell commands blocks it, the
script is not at its path, or it exits non-zero. Say in one line what failed
and hand relay this wait; your next ring tries the script again. Never write,
edit, copy or `chmod` a script, and never run the wait as inline shell. Your
Harness file's "Trust your live tools over this file when they disagree"
covers a stale description of a means; the script is the means itself,
reviewed with this skill, and hand relay costs the user only a paste.
