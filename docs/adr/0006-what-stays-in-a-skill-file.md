# What stays in a skill file

A skill file loads whole each time its Role runs, so it holds only what every
run follows. Rare branches, failure handling and what differs by Harness live
in Reference files that `SKILL.md` links directly, never through another
file, because a model may read a file it reached two links deep only in part.
Mechanics that differ by platform or Harness live in the VDD tool (ADR 0010).
A Role reads at most one Harness file and trusts its live tools over it when
they disagree, since Harnesses change between releases. Each skill ships its
own Reference files, because a user may install a subset of the skills.

## Considered options

**Whole skill files.** Rejected: every Session pays for branches and
Harnesses it never runs, and the usual path is harder to follow.

**A file pair per platform.** Rejected: the pairs cost 1,298 lines, held
every guardrail twice, and the model still typed each shell command, which
is where the slips were.
