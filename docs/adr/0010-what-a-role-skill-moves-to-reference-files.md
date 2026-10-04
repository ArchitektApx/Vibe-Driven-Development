# A Role skill moves its cold paths and its Harness mechanics to Reference files

A skill file loads whole when its Role invokes it, so every Session pays for the
repair steps, the rare branches and the commands of every Harness it is not
running in. Two kinds of text leave the skill file for Reference files under a
`references/` directory inside its own skill directory: cold paths, read on a
failure or a rare branch, and Harness mechanics, the wording one Harness needs
and another does not. Everything else stays, the guardrails included, so a Role
on the happy path reads the skill file, at most one Harness file, and any
Reference file that Harness file sends it to.

**The cold-path criterion decides a cold move.** A section moves when it is read
on a failure or on a rare branch, and stays otherwise. Length decides nothing:
a long section a Role reads every time stays in the skill file, and a short
repair route moves.

**The Harness criterion decides a Harness move.** A sentence moves to a Harness
file when its wording would change on another Harness: a tool, a command, an
invocation syntax, a path or a precondition. A Harness file holds only what a
competent agent on that Harness could not work out from its own tool list. A
sentence that reads the same on every Harness stays in the skill file. Length
and frequency decide nothing here either. A skill neither criterion touches
ships no `references/` directory.

**A Role reads one Harness file, once.** The file for a Harness is
`references/harness-<slug>.md`, the slug being the Harness's name lowercased
with spaces turned to hyphens: `harness-claude-code.md`, `harness-codex.md`.
A start step reads it: from the Loop file's `Harness:` line in a Role that runs
inside a Workflow, and from the Harness the Session knows itself to run in,
or the user states, in `vdd-setup` and `vdd-start-loop`. Each branch point in
the body then names the mechanic in neutral words, such as "deliver it through
your Harness file's delivery mechanics".

**Generic ships no file.** Generic is the state in which no Harness file is
read, and the neutral inline text is its complete path. A skipped read and
Generic therefore behave the same, and an agent on a Harness this repository
has never heard of still has a whole skill.

**A guardrail never leaves the skill file, except for a Reference file read on
every use.** A sentence is a guardrail when it names a behaviour a competent
agent could plausibly get wrong in this Workflow, and ADR-0004 keeps its
prohibition beside the positive target. The reader who needs a guardrail is the
one who believes the situation does not apply to them, and that reader follows
no pointer. A Reference file that the Harness file sends the Role to on every
use of the mechanic a guardrail guards is behind no situational pointer, so that
guardrail may sit there, beside the command it governs (ADR 0011). A guardrail
about a Harness mechanic splits in two: the obligation stays inline in neutral
words, and the mechanics move. For a cross-Session Doorbell the obligations are
to deliver it through the Harness file's delivery mechanics; to send the
Doorbell line and nothing else; and to print the exact Doorbell for the user to
paste where nothing delivers it or delivery fails. The tool, the command and
their preconditions are what move. Moving any sentence is re-expression rather
than deletion, so the Rule inventory records each moved sentence with its
destination.

**Every Harness file ends on the drift line**, exactly: "Trust your live tools
over this file when they disagree." A Harness changes between this
repository's releases. The agent may improvise the means when its tools
disagree with the file, except where the means is a script the plugin ships:
that script is never replaced by one the agent writes (ADR 0011). The inline
obligations still bind the target, the content and the fallback.

**Each moved section leaves a pointer and an index entry.** The pointer to a
cold path sits at the branch point the section left and names the situation
that calls for the file rather than the file's subject, so a Role reads it
exactly when it applies. The index section lists every Reference file the skill
ships with a phrase each, which is what a Role in a situation no inline pointer
names reads instead. A skill that ships a Harness file also carries a
`## Harnesses` section with one bullet for every Harness that has a file in any
skill: a link to this skill's own file, or `none: the inline text is complete`.
Generic is not listed. The index is what lets `verify.yml` check reachability
with a direct link from the skill file rather than a crawl across Reference
files.

**A Harness-specific cold path stays in its cold file.** The cold Reference file
it belongs to carries one section per Harness where the route differs, and its
pointer stays situational. Harness files and cold files alike sit one link from
the skill file.

**Packaging carries the Reference files on every install route.** The skills
CLI, checked at 1.5.22, copies a skill directory recursively and excludes only
its metadata file, `.git` and the Python cache directories; an offline install
against this repository's exact layout delivered a `references/` directory
intact. The Claude Code plugin ships the whole repository, and Codex, Cursor
and Copilot CLI install the plugin's committed files from the same marketplace
file into their own caches.
The invoking agent receives the skill's base directory, so a relative link
resolves on every route.

## Considered options

**Correction: a Harness's normal mechanics move to one selected Harness file
rather than staying inline in the skill file.**

**Leaving the skill files whole.** Rejected. The eight files run to roughly
70,000 characters, about 17,500 tokens, and the Setup skill's Borrowed-skills
check alone is most of one file while a healthy machine reads none of its
repairs. The cost falls on the user's context window in every Session, and the
happy path is harder to follow with the repairs inline.

**One shared directory of Reference files that several skills point at.**
Rejected. The skills CLI copies each skill directory separately and a user may
install a subset, so a file outside the skill directory arrives on no machine
that installed only that skill. The passages repeated across the skill files
stay repeated for the same reason, and each skill ships its own Harness files.

**Moving guardrails too, on the ground that a pointer sends the reader to
them.** Rejected. A pointer fires on the situation it names, and the reader
about to take the wrong action does not know they are in that situation. A
guardrail that moved would reach every reader except the one it was written
for.

## Consequences

A change to a Role's cold path touches the skill file and a Reference file
rather than one file, and the Rule inventory has a destination column to fill.
A change to a Harness mechanic touches that Harness's file in every skill that
states it. The pointer, the index and the `## Harnesses` section all have to
move with a file, and CI fails the pull request when one is missed.

`verify.yml` checks this layout, and `AGENTS.md` lists each check under
Invariants: every relative link under the skills tree resolves to a file
that ships; every file under a skill directory is linked directly from that
skill's `SKILL.md`; and every skill that ships a Harness file has a
`## Harnesses` section with an entry for every Harness that has a file in any
skill. `agents/openai.yaml` directly inside a skill directory is exempt from the
second check: Codex reads it as the skill's policy file, and no reader reaches
it by a link. The checks also bound what the layout may hold, since a file that
no skill file points at cannot ship at all.

The check that a split routes its readers correctly is a scenario run: a fresh
subagent given a situation, with the files it reads and the conclusion it
reaches compared against what the pointer promised. The Loops that made this
decision ran them per split skill, and per Harness for the Harness files, and
recorded the outcomes in their Working files. They are not a standing
requirement in `docs/agents/VERIFICATION.md`.
