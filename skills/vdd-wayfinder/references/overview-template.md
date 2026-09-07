# <effort>: overview

<!--
Written once the map is clear. Read by the user before every loop and by each
loop's Planner as the first file of its handoff. Keep it short: the detail
of each loop lives in its NN-<slug>.md, the detail of each decision in its
ticket.
-->

## Destination

<What reaching the end of this series looks like, in the map's words. One or
two lines.>

## Loops

<!-- one row per loop, in the order they run -->

| # | Handoff | What lands |
|---|---------|------------|
| 01 | [<title>](01-<slug>.md) | <one line> |

## Gate between loops

<What must hold before the next loop's Planner starts. Usually: the previous
loop's PR is merged and its acceptance criteria passed.>

## Rules every loop inherits

<!-- one item per rule, each linking the ticket or file that holds it -->

- <constraint, convention or decision each Planner cites rather than
  rediscovers>

## Starting a loop

Give this to the loop's Planner, after `/vdd:vdd-start-loop`, with N and the
handoff filled in:

```plaintext
A wayfinding effort has settled the goal that a series of VDD loops will
reach for this repository and split the work into <M> handoffs, one per loop.

You are Loop <N> of <M>. Plan the changes described in
@.scratch/<effort>/handoffs/00-overview.md (the whole series) and
@.scratch/<effort>/handoffs/<NN>-<slug>.md (this loop). Read both and the
files they reference, so you understand the scope of this loop in depth
before you grill me.
```
