# Reviewing the Agent documents in the diff

`review start` listed the Agent documents in the range. The lines they added or changed are the whole object
of the step. Source files in the same diff stay out of it, and so do the Agent document lines the range
left alone: agent-writing levers read over application code produce findings
the Coder cannot act on, and levers read over untouched lines produce findings
this branch did not earn.

Name the lever a finding breaks in the term `writing-for-agents` uses for it.
That Borrowed skill ships with the collection and is the single source of truth
for the levers, so read them there. Severity follows consequence, on the same
scale as every other finding: a defect that leaves a step ambiguous is a major,
sprawl that costs tokens without changing behaviour is a minor.

Step 3's findings are numbered with the rest, under `## New findings`. When
`writing-for-agents` does not resolve, step 3 ends on its Checks line,
`writing-for-agents: did not resolve`.
