# A Role skill keeps its happy path in the skill file and its cold paths in Reference files

A skill file loads whole when its Role invokes it, so every Session pays for the
repair steps and the rare branches whether or not it reaches them. A Role skill
that has cold paths keeps them in Reference files under a `references/`
directory inside its own skill directory, and leaves a pointer at each branch
point plus an index section naming what the skill ships. A Role on the happy
path reads the skill file alone.

**The cold-path criterion decides every move.** A section moves when it is read
on a failure or on a rare branch, and stays otherwise. Length decides nothing:
a long section a Role reads every time stays in the skill file, and a short
repair route moves. A skill the criterion leaves untouched ships no
`references/` directory.

**A guardrail never leaves the skill file.** A sentence is a guardrail when it
names a behaviour a competent agent could plausibly get wrong in this Workflow,
and ADR-0004 keeps its prohibition beside the positive target. The reader who
needs a guardrail is the one who believes the situation does not apply to them,
and that reader follows no pointer. What may move is mechanics, diagnosis
detail, repair steps and rationale. Moving a section is re-expression rather
than deletion, so the Rule inventory records each moved sentence with its
destination.

**Each moved section leaves a one-line pointer and an index entry.** The
pointer sits at the branch point the section left and names the situation that
calls for the file rather than the file's subject, so a Role reads it exactly
when it applies. The index section lists every Reference file the skill ships
with a phrase each, which is what a Role in a situation no inline pointer names
reads instead. The index is also what lets `verify.yml` check reachability with
a direct link from the skill file rather than a crawl across Reference files.

**Packaging carries the Reference files on both install routes.** The skills
CLI, checked at 1.5.22, copies a skill directory recursively and excludes only
its metadata file, `.git` and the Python cache directories; an offline install
against this repository's exact layout delivered a `references/` directory
intact. The Claude Code plugin ships the whole repository. The invoking agent
receives the skill's base directory, so a relative link resolves either way.

## Considered options

**Leaving the skill files whole.** Rejected. The eight files run to roughly
70,000 characters, about 17,500 tokens, and the Setup skill's Borrowed-skills
check alone is most of one file while a healthy machine reads none of its
repairs. The cost falls on the user's context window in every Session, and the
happy path is harder to follow with the repairs inline.

**One shared directory of Reference files that several skills point at.**
Rejected. The skills CLI copies each skill directory separately and a user may
install a subset, so a file outside the skill directory arrives on no machine
that installed only that skill. The five passages repeated across the skill
files stay repeated for the same reason.

**Moving guardrails too, on the ground that a pointer sends the reader to
them.** Rejected. A pointer fires on the situation it names, and the reader
about to take the wrong action does not know they are in that situation. A
guardrail that moved would reach every reader except the one it was written
for.

## Consequences

A change to a Role's cold path touches the skill file and a Reference file
rather than one file, and the Rule inventory has a destination column to fill.
The pointer and the index both have to move with the section, and CI fails the
pull request when either is missed.

`verify.yml` gained two steps, both listed under Invariants in `AGENTS.md`:
every relative link under the skills tree resolves to a file that ships, and
every file under a skill directory is linked directly from that skill's
`SKILL.md`. They also bound what the layout may hold, since a file that no
skill file points at cannot ship at all.

The check that a split routes its readers correctly is a scenario run: a fresh
subagent given a situation, with the files it reads and the conclusion it
reaches compared against what the pointer promised. The Loop that made this
decision ran them per split skill and recorded the outcomes in its Working
file. They are not a standing requirement in `docs/agents/VERIFICATION.md`.
