# Verifying a change to this repository

There is no build and no tests. A change is verified by reading, and these are
the checks a reviewer applies, in this order. CI adds only the well-formedness
checks listed under Invariants in `AGENTS.md`.

## Cold read

Read each changed skill file as an agent reads it: alone, from the frontmatter
down, with nothing of the editing session in context. A passage that only makes
sense to someone who followed the conversation fails here.

## Vocabulary

Every term is the one `CONTEXT.md` defines, and none from its `_Avoid_` lines.
A word the glossary lacks is a proposal for the glossary, not a coinage in one
skill file.

## Rules

ADR 0004 holds: a writing pass re-expresses a rule and never deletes one. A
sentence is a guardrail when it names a behaviour a competent agent could
plausibly get wrong in this workflow, and a guardrail keeps its prohibition
beside the positive target. Everything else is a candidate no-op, written up as
a proposal rather than removed. Where the test is balanced, git history or an
ADR showing the sentence was added for a reason settles it as a guardrail.

The evidence is the Rule inventory and the Lever log, both defined in
`CONTEXT.md`: the inventory catches a deleted rule, the log catches a change
made on taste. Both are written into the Working file of the Role that made the
pass and stop there. A pull request body here carries nothing about the
Workflow that produced it, which ADR 0012 decided, so no pass routes them
onward into one.

## Tells

`writing-for-agents` covers the defects that change how an agent behaves. What
it leaves behind is phrasing that reads like a machine wrote it, and the six
tells below are all of it. The list is closed: a seventh replaces one of these
rather than joining them.

1. Em dashes. Use a comma, a colon or a full stop.
2. The "not just X, but Y" cadence, and its relatives ("it is not only A, it is
   also B"). State the half you mean.
3. Triads of adjectives or verbs used for rhythm. Keep the one word that
   carries the meaning.
4. Openers that restate the heading or the question. Answer in the first
   sentence.
5. Hedging modifiers: simply, just, basically, really, actually. State the
   claim plainly.
6. Closing paragraphs that summarise the section above them. End on the last
   point.
