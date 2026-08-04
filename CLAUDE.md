# Working in this repository

This repository is developed with its own workflow. Use the VDD Roles on
changes to it, the same way a user would on their own project:
`/vdd:vdd-planner` writes `PLAN.md`, a separate session reviews it, and so on.
Proportionality applies, a typo fix does not need four sessions; anything that
changes how a Role behaves does.

The Planner's grilling step is what produced the two files below, and they are
committed for the same reason any project keeps them:

- `CONTEXT.md` is the glossary. Use its terms exactly when editing the skills,
  so the five `SKILL.md` files keep one vocabulary.
- `docs/adr/` records decisions that are hard to reverse and surprising without
  context. Read `0001` before proposing that the Roles be orchestrated
  automatically; that has been tried and rejected.

The repository is prose only. There is no build, no tests, no CI. Verification
means reading the skill files as an agent would read them cold.
