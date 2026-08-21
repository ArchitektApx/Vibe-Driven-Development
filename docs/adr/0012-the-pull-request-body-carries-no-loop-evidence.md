# The pull request body carries no Loop evidence

A pull request body describes the change and says nothing about the Workflow
that produced it. The PR-Author assembles no section of review rounds, findings
by severity or verification run, and on the path with no pull request template
and no merged history to imitate the body is the Spec's Problem Statement and
Solution.

Every document in this repository that required or routed that evidence into a
body stops doing so. Four rules go, and this record authorises all four: the
evidence step in `skills/vdd-create-pr/SKILL.md`, the section of
`docs/agents/LANDING-A-CHANGE.md` requiring a body to carry round counts,
findings by severity and the verification run, the clause in `AGENTS.md`
pointing at that section, and the routing in `docs/agents/VERIFICATION.md` that
sends the Rule inventory and the Lever log onward into a body.

A fifth site changes without a rule leaving it.
`docs/adr/0007-the-minors-answer-is-given-at-workflow-start.md` closed its
consequences on a clause about what the pull request body reports, and that
clause is rewritten in place to name the review file in the Tracker directory
as where the count lives. A record states the decision that holds now, so it is
brought current rather than cut.

## Considered options

**Keeping a shortened evidence line, so a reviewer can still see that a review
happened.** Rejected. The line would say a review ran without saying what it
found, which is a claim the reviewer cannot check and does not need. A reviewer
judges the diff. Round counts describe how the author worked, and a body is not
where a reader looks for that.

**Committing the Tracker directory so the evidence reaches history by another
route.** Rejected. The Tracker directory is scratch space for handoff between
sessions; committing it would put every draft of a Spec and every superseded
review round into the user's history to preserve a summary nobody asked for.

## Consequences

Nothing about a Workflow reaches history. The Tracker directory is gitignored,
so the record survives on the machine that ran the Workflow and in no clone.
That is the surprising part of this decision, and it is what makes the record
worth writing down.

What makes it acceptable is that the review files now sit one directory per
Feature slug. Before that move they lived at the repository root and the next
Workflow overwrote them, so the body was the only place a Loop's record could
survive at all. It is not any more.

ADR-0004 holds that a writing pass re-expresses a rule and never deletes one,
and permits a deletion made as a design decision in its own Loop with a
reviewer who saw it go. This record is that decision, and it authorises the
four rules named above. A reviewer reading one of those deletions reads it
against this record rather than as a violation.

The Rule inventory and the Lever log stay where they are written, in the
Working file of the Role that made the pass, and stop there.

The imitate-history path is left as it is. Bodies already merged in a
repository carry the section, so a PR-Author matching the shape of recent
history keeps copying it for a while. That fades as bodies without it
accumulate, and the fade is accepted rather than fixed with a rule that would
have the PR-Author overrule the history it was told to imitate.
