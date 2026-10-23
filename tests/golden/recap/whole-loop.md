# Recap: demo

Written by the VDD tool only. No Role reads it during the loop.

Branch: demo from main.
Plan Loop: 2 rounds, signed off in round 2.
Code Loop: 3 rounds, signed off in round 3; folded.

| Loop | Round | New findings | Closed | Open after | Checks |
|---|---|---|---|---|---|
| plan | 1 | 2 | 0 | 0 blocker, 1 major, 1 minor | writing-for-agents ran |
| plan | 2 | 0 | 2 | SIGNED OFF | writing-for-agents ran |
| code | 1 | 1 | 0 | 0 blocker, 1 major, 0 minor | code-review ran; writing-for-agents no Agent document in this round's diff |
| code | 2 | 0 | 1 | SIGNED OFF | code-review ran; writing-for-agents no Agent document in this round's diff |
| code | 2, user | 2 | 0 | 0 blocker, 1 major, 1 minor | none |
| code | 3 | 0 | 2 | SIGNED OFF | code-review ran; writing-for-agents no Agent document in this round's diff |

## Tickets

### Ticket 01: 01-one.md

Files: `a.txt`
Change: wrote a.
Verified: the test passed.

### Ticket 02: 02-two.md

Files: `a.txt`
Change: wrote a.
Verified: the test passed.

## Plan findings

### 1. major, fixed in round 2: Implementation Decisions

Problem: The Spec does not say how amounts are written.

Resolution: the Spec names two decimals.

### 2. minor, fixed in round 2: Ticket 02

Problem: Ticket 02 leaves `summary` out.

Resolution: Ticket 02 names `summary`.

## Code findings

### 1. major, fixed in round 2: a.txt:1

Problem: The value is wrong.

Resolution: a.txt holds b.

### 2. major, raised by the user after round 2, fixed in round 3: docs/a.md:3

Problem: The heading names the wrong command.

Resolution: the heading names it.

### 3. minor, raised by the user after round 2, accepted in round 3: src/b.py:9

Problem: The helper's name says less than it does.

Resolution: the name stays.

## Commits

Folded demo: 2 commits into 1; the folded tree equals the signed tree (<sha>).

  <sha> feat: a
      <sha> feat: a (round 1)
    + <sha> fix: the value: a.txt

Folded demo: 2 commits into 2; the folded tree equals the signed tree (<sha>).

  <sha> feat: a
      <sha> feat: a (folded after round 2)
  <sha> fix: the user's findings
      <sha> fix: the user's findings, its own commit: no commit of the loop wrote its lines

## Not carried

- Code round 1: the report's style nit on a.txt: not a defect
