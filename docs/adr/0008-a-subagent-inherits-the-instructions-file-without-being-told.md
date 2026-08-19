# A subagent inherits the repository's instructions file without being told

The Spawn prompt does not tell a hosted Role to read the repository's
instructions file, `AGENTS.md` (or `CLAUDE.md`, where the host reads that
name instead). Every subagent type capable of doing a Role's work inherits
that file without being told, measured across four subagent types on three
hosts on 2026-08-19. The one type that did not inherit it is read-only, and
no host gives a Coder a read-only context for a prompt that says implement,
commit and write a Working file.

## Considered options

**Keeping the sentence, on the belief that some host's subagent might not
inherit the file.** Rejected. The belief was untested when the sentence was
written, and this Loop tested it false, against a fixture whose instructions
file both stated a token and required a reply prefix. The prefix makes
inheritance behavioural: a child either emits it in its own turn or does not,
and a parent cannot fake that on the child's behalf. Every result below comes
from a run where the parent echoed the exact instruction it passed, and that
instruction carried no token, no filename and no hint; an early negative
result on Copilot turned out to be the parent leaking the token into the
spawn prompt itself, which is why the echo is part of the method.

| Host | Subagent type | Child inherited |
|---|---|---|
| Codex 0.147.0 | default spawn primitive | yes |
| Cursor | default task primitive | yes |
| Copilot CLI | general-purpose | yes |
| Copilot CLI | read-only exploration agent | no |

Inheritance turned out to be a property of the subagent type rather than of
the host. The one type that did not inherit is read-only, which is not a
type any host hands a Coder: every Spawn prompt in this Workflow asks a Role
to implement, commit or write a Working file, none of which a read-only
context can do.

**Naming a subagent type in the Spawn prompt, to guarantee inheritance where
it might be missing.** Rejected. The type vocabulary is not portable:
`general-purpose` is one host's word, and the others name their primitives
differently. The Orchestrator skill deliberately names no primitive and
defers to the host's own, and naming a type here would break that to guard a
failure no realistic Spawn prompt produces.

## Consequences

A rule leaving these files is a design decision made in its own Loop with a
reviewer who saw it go (ADR-0004), and this record is that decision's
evidence. Nothing else in the Spawn prompt template changes, and a hosted
Role still invokes its own skill first; if reading `AGENTS.md` mattered to a
Role's own behaviour, that Role's own skill is where the instruction would
live, the same way a by-hand run of any Role already reads it before
changing anything.

The measurement needs three host command-line tools installed and
authenticated, so it is not cheap to redo from the repository alone. A later
maintainer who doubts the result re-runs the method above rather than
guessing from a single host.
