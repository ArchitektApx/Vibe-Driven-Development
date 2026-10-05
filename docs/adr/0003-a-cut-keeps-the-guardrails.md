# A cut keeps the guardrails

The skills are prose a model follows in every Session, so a no-op, a sentence
that changes no behaviour, costs tokens and dilutes the sentences that do, and
a change may cut it. A guardrail is different: a sentence that prevents a
behaviour a competent agent could plausibly get wrong in this Workflow, often
added after one did. It leaves only when the behaviour it prevents can no
longer happen, or when another sentence the same reader reads before acting
now prevents it.

A guardrail that works looks unnecessary, because the failure it prevents
never shows. Whether a sentence is one is therefore settled from the reason it
was added, found in the commit or the ADR that added it, and not from how it
reads. Whether a cut changed behaviour is settled by running the Role rather
than by reading the diff, because whether a sentence is a no-op depends on the
model that reads it.

A guardrail sits where every reader who could break it reads it before
acting: in `SKILL.md`, or in a Reference file the Role reads every time it
does what the guardrail governs. A pointer that fires only on a situation is
not enough, because the reader who needs the guardrail believes the situation
does not apply to them.

## Considered options

**Rewording any rule and deleting none.** Rejected: the prose could only
grow, and every removal needed a recorded decision of its own.
