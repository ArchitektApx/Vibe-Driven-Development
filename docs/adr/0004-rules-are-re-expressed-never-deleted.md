# Rules in this repository's Agent documents are re-expressed, never deleted

The Agent documents this repository ships were passed through
`writing-for-agents` in one Loop, and that pass was allowed to reword a rule and
never to drop one. A rule leaving these files is a design decision, made in its
own Loop with a reviewer who saw it go. Three rules govern any later pass: a
rule may be re-expressed and never deleted, a sentence is a guardrail when it
names a behaviour a competent agent could plausibly get wrong in this workflow,
and vocabulary comes from `CONTEXT.md`.

The guardrail test decides which negations stay. A reviewer editing the Spec, a
Role guessing a Feature slug, a Session appending to a review file instead of
replacing it: each is a plausible failure, so the sentence that forbids it is a
guardrail and keeps its prohibition beside the positive target. Everything else
is a candidate no-op, and a candidate no-op is written up as a proposal rather
than removed. Where the test is genuinely balanced, git history or an ADR
showing the sentence was added for a reason settles it as a guardrail;
provenance is the tie-breaker rather than the test, because most of these files
arrived in two large commits.

Vocabulary comes from the glossary. A word a pass reaches for is a term
`CONTEXT.md` defines, so a word coined in one skill file and unknown to the
others never enters; a new word is a proposal, and the glossary is where it
lands if it is accepted.

## Considered options

**Packaging carries a Reference file beside its skill file, so the split this
record left open is the one ADR-0010 owns.** The skills CLI copies a skill
directory recursively, the plugin ships the whole repository, and `verify.yml`
now checks every markdown file under the skills tree.

**A pass applying every lever as written, including no-op pruning and negation
removal.** Rejected. `writing-for-agents` is written for an author holding one
document and able to run it afterwards, and its no-op test is explicitly
model-relative: two readers who disagree settle it by running the document. This
repository ships prose to other people's machines and has no way to run
anything, so the same test in the same hands becomes a judgement with nothing
behind it. The negation count is what makes this concrete. The eleven documents
carried 176 negations at the start of this Loop, most of them one sentence
apart from a Role boundary, and a pass authorised to delete would have taken
`Never adopt a second slug`, `Never re-run /to-spec` and `Never delete anything
mid-loop` on the same reading that took the genuine no-ops. The bounded pass
costs a proposal list and keeps every rule; the unbounded one saves the list and
risks the rules.

## Consequences

Every pass writes two artefacts into the Working file of the Role that made it,
the Rule inventory and the Lever log, both defined in `CONTEXT.md`. They check
opposite failures: the inventory catches a deleted rule, the log catches a
change made on taste. Neither catches the other, and a pass without both is a
pass nobody can review.

The Loop that established this policy deferred the following. This list is what
survives of it, because `FIXES.md` is a Working file, gitignored, and reaches no
clone.

**Document splits the sprawl lever pointed at.** The Borrowed-skills check is
most of `skills/vdd-setup/SKILL.md`, from the top of the numbered list down to
the tracker check. The split that earns it moves the search roots, the `find`
loop and its rationale, the Resolvable probe list and the three-way
`code-review` reading into a Reference file, leaving the three states and the
per-Role costs in `SKILL.md`. ADR-0010 owns that layout, the criterion that
decides each move and the boundary the move may not cross.

**Passages repeated across the Role skill files.** Five passages appear
identically in four skill files each: the `LOOP.md` reading paragraph, the four
Role commands paragraph, the `Receiving a message from another session` section,
the sentence that no agent can rename a session, and the sentence that a
Doorbell says which file to read and nothing more. Two more repeat without being
on that list: `Never put reasoning, findings or file contents in the message`,
which is a negation with an available positive form, and the hand-off
scaffolding that introduces the naming lines and the Doorbell. All of them are
duplication by the lever's own definition and deliberate by construction, since
a skill file loads alone and pointing several at one paragraph means shipping
another file.

The Orchestrator Loop took up two of the seven: the four Role commands
paragraph and the sentence that no agent can rename a session both left the
Plan-Reviewer, the Coder and the Code-Reviewer, because the mechanism they
described, a session the user starts and renames by hand, is gone from those
three Roles under a hosted Workflow. The other five stand as they were.

**Glossary sentences kept because nothing else owns them.** `CONTEXT.md`'s Loop
file entry runs to three sentences to keep `One Loop per repository at a time`,
which no skill file states. Its User-invoked entry runs to three to keep the
Claude Code and Codex invocation keys, of which `vdd-setup` owns only the Claude
Code one. Both are over the Borrowed format's two-sentence limit and both stay
until the rule they carry has an owner elsewhere.

**Words the pass wanted to coin.** None. Every leading word the documents
needed was already a glossary term.

**Rules proposed for deletion.** One. `vdd-setup`'s gitignore check listed
`PLAN.md` and said it stayed on the list for one release, for users holding a
`PLAN.md` from a 0.2.0 loop; this Loop shipped 0.5.0. The relevance lever found
it and the line was stale rather than wrong. The Loop that moved the review
files into the tracker directory dropped `PLAN.md` from that list and from the
stale-working-file check, and Setup now removes the entry from a user's
`.gitignore`.

**An ADR opening past the Borrowed format's bound.** ADR-0002's opening
paragraph is four sentences against a bound of three. A three-sentence opening
that keeps every claim is recorded in that Loop's `FIXES.md` under Ticket 10.
The bound is structure rather than prose, so the pass left the paragraph alone.
ADR-0001 and ADR-0003 meet the bound at three sentences each, which corrects the
Spec that drove the Loop.

The moves that Loop closed off are deferred work rather than policy, and a
later Loop can take them up. Adding a file is the one ADR-0010 took up; writing
across documents and freezing the repeated passages are still open. They are
consequences of running twelve disjoint
Tickets at once, where each Ticket owns one document and copies of one paragraph
would otherwise drift apart in ways nobody chose. Freezing those passages
permanently is the opposite of why they were frozen.
