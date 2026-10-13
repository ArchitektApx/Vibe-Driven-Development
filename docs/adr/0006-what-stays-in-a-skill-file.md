# What stays in a skill file

A skill file loads whole whenever its Role runs, so it holds the instructions
every use of the Role follows. Text read only on a failure or a rare branch,
the calls one Harness needs and another does not, and templates the Role
fills in live in Reference files in the skill's own `references/` directory.

Mechanics that differ by platform live in the VDD tool, and a skill names the
interpreter for each platform once. Lookups that differ by Harness, such as
the stores a Harness reads, its repair routes, its launch line and how it
waits, live in the tool too, keyed by the Harness the Role names on each
call. A Harness file holds what is left: the calls the model makes with its
Harness's own tools, and judgment that differs by Harness.

`SKILL.md` links each Reference file directly, from the step that reads it,
and no Reference file is reached only through another. A model may read a
file it found two links deep only in part, so a Harness file names a file
`SKILL.md` links rather than linking it itself.

A Role reads at most one Harness file, chosen once at the start of its
Session. Generic has a Harness file like the others, so `SKILL.md` keeps no
Generic branch, and a Role on a Harness this repository has never heard of
still has a whole skill. A Harness changes between releases, so a Role trusts
its live tools over its Harness file where the two disagree.

Each skill ships its own Reference files, because the skills CLI installs each
skill directory separately and a user may install a subset. A passage two
skills need is repeated in both.

## Considered options

**Leaving the skill files whole.** Rejected: every Session pays for the
repairs, the rare branches and the mechanics of Harnesses it does not run in,
and the happy path is harder to follow with them inline.

**Platform mechanics in a pair of complete files per platform.** Rejected:
the pairs cost 1,298 lines, each guardrail appeared whole in both files of a
pair, and the model still typed every shell command, which is where the
slips were.

**One file carrying both platforms.** Rejected: every run reads the other
platform's commands, up to about 40% of a Doorbell file.

**The neutral text in `SKILL.md` as Generic's complete path.** Rejected: it
kept a Generic branch in every skill with Harness files, read on every
Harness.

**Subdirectories under `references/`.** Rejected: the Role reaches every file
by a link, so a directory tree groups the files only for a human.
