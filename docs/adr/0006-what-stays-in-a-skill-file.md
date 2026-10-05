# What stays in a skill file

A skill file loads whole whenever its Role runs, so it holds the instructions
every use of the Role follows. Text read only on a failure or a rare branch,
the mechanics one Harness needs and another does not, and templates the Role
fills in live in Reference files in the skill's own `references/` directory,
one link from `SKILL.md`.

A Role reads at most one Harness file, chosen once at the start of its
Session. Generic has no Harness file: the neutral text in `SKILL.md` is its
complete path, so a Role on a Harness this repository has never heard of still
has a whole skill. A Harness changes between releases, so a Role trusts its
live tools over its Harness file where the two disagree.

Each skill ships its own Reference files, because the skills CLI installs each
skill directory separately and a user may install a subset. A passage two
skills need is repeated in both.

## Considered options

**Leaving the skill files whole.** Rejected: every Session pays for the
repairs, the rare branches and the mechanics of Harnesses it does not run in,
and the happy path is harder to follow with them inline.
