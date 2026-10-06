# What stays in a skill file

A skill file loads whole whenever its Role runs, so it holds the instructions
every use of the Role follows. Text read only on a failure or a rare branch,
the mechanics one Harness or one platform needs and another does not, and
templates the Role fills in live in Reference files in the skill's own
`references/` directory.

`SKILL.md` links each Reference file directly, from the step that reads it,
and no Reference file is reached only through another. A model may read a
file it found two links deep only in part, so a Harness file names a file
`SKILL.md` links rather than linking it itself.

A Role reads at most one Harness file, chosen once at the start of its
Session. Generic has no Harness file: the neutral text in `SKILL.md` is its
complete path, so a Role on a Harness this repository has never heard of still
has a whole skill. A Harness changes between releases, so a Role trusts its
live tools over its Harness file where the two disagree.

Mechanics that differ by platform, macOS and Linux on one side and native
Windows on the other, live in a pair of complete files, and the Role reads the
one for its platform. A guardrail that governs both platforms appears whole in
each file of the pair.

Each skill ships its own Reference files, because the skills CLI installs each
skill directory separately and a user may install a subset. A passage two
skills need is repeated in both.

## Considered options

**Leaving the skill files whole.** Rejected: every Session pays for the
repairs, the rare branches and the mechanics of Harnesses it does not run in,
and the happy path is harder to follow with them inline.

**One file carrying both platforms.** Rejected: every run reads the other
platform's commands, up to about 40% of a Doorbell file.

**Subdirectories under `references/`.** Rejected: the Role reaches every file
by a link, so a directory tree groups the files only for a human.
