---
title: <title>
tldr: <one sentence, copied into index.md>
status: idea
created: <YYYY-MM-DD>
last-updated: <YYYY-MM-DD>
importance: <xsmall | small | medium | large | xlarge | unknown>
size: <xsmall | small | medium | large | xlarge | unknown>
fog: <xsmall | small | medium | large | xlarge | unknown>
depends-on:
  - <idea file name>
benefits-from:
  - <idea file name>
related:
  - <idea file name>
---

<!--
Frontmatter fields:

- status:
  one of the following values:
  idea         written down, not yet discussed
  discussed    talked through, open questions listed, no direction yet
  shaped       direction chosen and written under Decision, not yet committed
               to build; the usual state after one good conversation
  decided      go or no-go recorded under Decision, with a date
  in-progress  a loop or PR is carrying it out
  done         shipped, Decision links to the PR or ADR
  dropped      no-go, Decision says why; the file stays, its row moves to
               the Closed ideas table in index.md

- importance, size and fog each take one of: xsmall, small, medium, large,
xlarge or unknown.
  - Importance is how much we want it.
  - Size is how much work we expect.
  - Fog is how much research, thinking and discussion stands between us and
  knowing it works, dead-end chance included.

- relations:
  these are either empty or a list of other idea files based on their category:
  `depends-on` are others ideas that block this idea.
  `benefits-from` are other ideas that would make this one easier or better.
  `related` are other ideas that overlap or compete, neither blocking nor helping.

  The inverse (enables, helps) appears in the other file's
  [Related Ideas](#related-ideas) section, not in frontmatter.
-->

# <title>

## Key Metrics

Importance: <one sentence why>
Size: <one sentence why>
Fog: <what we do not know yet, whether it could be a dead end, and the cheapest step(s) that would clear it, size an idea once its fog clears>

## Summary

<What the idea is about?>

## Proposal

<What we would change or build. Write "None yet, problem only." if unclear>

## Pro

- <one benefit per list item>

## Con

- <one cost, risk or drawback per list item>

## Open Questions

- <one question per list item; when settled, write the answer below the question
  and keep the question>

## Evidence

- <One finding per list item: what research or testing showed, dated, with the method in one line so it can be rerun. Scripts, data and longer write-ups go under `research/<slug>/`; link them from here.>

## Prior Art

<Internal: past attempts, experiments, branches, commits, prompts, other
repositories. External: repository links, website links, articles, tools, skills, etc.>

## Related Ideas

- depends on [<idea>](<idea>.md): <what decision or result this needs>
- benefits from [<idea>](<idea>.md): <how it would help>
- enables [<idea>](<idea>.md): <what waits on this one>
- related [<idea>](<idea>.md): <how they overlap or compete>

## Decision

<Empty until shaped. Shaped: the direction and the date. Decided: go, no-go
or merged into <idea>, the reason, the date, and a link to the loop, ADR or
PR that carried it out. Always end with "Reopen when: ..." so the idea is not
relitigated without new evidence.>

## Next Steps

- [ ] <smallest step that moves status forward>
