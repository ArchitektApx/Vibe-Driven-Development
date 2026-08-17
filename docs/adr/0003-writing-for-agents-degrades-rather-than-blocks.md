# A second agent-invocable Borrowed skill, and Roles that degrade without it

`writing-for-agents` joins `code-review` as a Borrowed skill an agent starts for
itself, so no Role has to ask the user to type anything for it. The Planner, the
Plan-Reviewer and the Code-Reviewer all reach for it. A Role that cannot resolve
it records the miss in the Working file it writes and carries on with what it
knows.

## Considered options

**Block, the way a missing `code-review` blocks the Code-Reviewer.** Rejected.
The two Borrowed skills carry different weight. `code-review` is a whole axis of
the Code-Reviewer's review, and a session that cannot run it is missing most of
its Working file. The levers are one check inside a review that has others, and a
Loop that runs without them still produces a Spec, a diff and a sign-off. A hard
stop would cost the user the Loop to save one section of one review.

Degrading has its own price: a check can go missing quietly. The Working file is
what pays it. Each of the three Roles writes the miss into the file it produces,
so a review with the check skipped reads as exactly that.

## Consequences

A user whose collection predates `writing-for-agents` runs the workflow on six
of the seven Borrowed skills and loses the writing pass alone. The setup skill
tells them the installed collection predates the skill, and how to update it.

The two reviewers check writing on different terms, and the asymmetry is
deliberate. The Plan-Reviewer reads documents VDD generated, which are Agent
documents in every Loop, so a condition there would evaluate true every time and
charge a judgement for that answer. The Code-Reviewer reads a user's repository,
where most branches change source code and nothing else. An unconditional check
there would spend a skill invocation per Loop to conclude nothing, and would
leave a Role holding agent-writing levers over application code. A Code-Reviewer
that says nothing about writing on a branch of TypeScript is this decision
working.
