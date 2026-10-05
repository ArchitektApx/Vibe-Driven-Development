# Verifying a change to this repository

There is no build, and two tests: the fixture tests for the Codex `Stop` hook
and the Doorbell wait. A change is verified by reading, and these are the
checks a reviewer applies, in this order. A change to a shipped script is also
verified by running it: the Doorbell wait as a Role would, against a scratch
Doorbell file, and the fixture tests, `sh tests/vdd-codex-stop.test.sh` for
the POSIX scripts and `pwsh -NoProfile -File tests/vdd-codex-stop.test.ps1`
for the PowerShell scripts, each of which must print no `FAIL` line and exit 0.
The tests run by hand, from anywhere, never in CI. CI adds only the
well-formedness checks listed under Invariants in `AGENTS.md`.

## Cold read

Read each changed skill file as an agent reads it: alone, from the frontmatter
down, with nothing of the editing session in context. A passage that only makes
sense to someone who followed the conversation fails here.

## Vocabulary

Every term is the one `CONTEXT.md` defines, and none from its `_Avoid_` lines.
A word the glossary lacks is a proposal for the glossary, not a coinage in one
skill file.

## Rules

A cut keeps the guardrails, as ADR 0003 decides. For every sentence a change
removes, the reviewer looks up why it was added: when the commit or an ADR
shows it prevents a behaviour, the cut stands only if that behaviour can no
longer happen or another sentence the same reader reads before acting now
prevents it. A guardrail keeps its prohibition beside the positive target.

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
