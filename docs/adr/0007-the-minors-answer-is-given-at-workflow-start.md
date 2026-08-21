# The user decides at Workflow start whether an open minor blocks Sign-off

The user answers one question at Workflow start, beside the PR question:
should an open minor hold up Sign-off. `vdd-start-loop` records the answer in
`LOOP.md` as `Minors: fix` or `Minors: leave`, and both reviewers read it
there. On `fix` a reviewer withholds Sign-off while any minor is open, for as
many rounds as that takes; on `leave` it signs off with the open minors listed
and the Loop ends.

## Considered options

**Each reviewer asking the user at its own first Sign-off with minors open.**
Rejected. No Role blocks on an answer from the user inside a Loop. A reviewer
finishes its round, writes its file and rings a Doorbell, and the user is
often in another terminal when that happens; a reviewer holding a question
open instead stalls there until the user comes back to that session. No Role
stops on a question about the work in hand once a round has begun. The stops
that do exist are environment checks and happen before a round: `vdd-coder`
asks which branch to work on when it is on neither, and `vdd-code-reviewer`
stops for `/setup-matt-pocock-skills` when `docs/agents/issue-tracker.md` is
missing. A hosted `vdd-coder` also stops on a Ticket it finds wrong or
impossible, carried by the Spawn prompt rather than by `vdd-coder`'s own
rule, which is unchanged: record the Ticket in `FIXES.md` and carry on. This
carve-out restores a path orchestration would otherwise take away rather than
granting a new one. Under the manual Workflow that Ticket already reached the
user, because they sat in the Coder's own terminal; hosting the Coder is what
would otherwise put a full review round between the user and an impossible
Ticket, having paid for a review of work that could not be done. No reviewer
gains anything from this: the Plan-Reviewer and the Code-Reviewer still judge
from the Working files alone, which is this record's reason for the rule and
the reason the rule survives, and a Coder reading this record and ADR-0001
together cannot conclude that a reviewer may ask. The rest of the asking sits
outside a Loop: `vdd-start-loop` runs the whole interview, `vdd-setup` asks
about a leftover `LOOP.md`, and the PR-Author asks its deferred question
after the Loop has ended, in a session the user is sitting in. Asking at
Sign-off would also ask the same question twice, once per Loop, and the
answer is one preference about how the user wants to work.

## Consequences

Each reviewer's Sign-off condition carries the branch: `SIGNED OFF` when no
blockers and no majors remain, and on `Minors: fix`, when no minor is `open`
either. Both Loops read the same line, so the Plan/Plan-Review Loop and the
Coder/Code-Review Loop end on the same rule.

Every finding in `PLAN-REVIEW.md` and `CODEREVIEW.md` carries a state beside
its severity, one of `open`, `fixed` or `accepted`. `accepted` is the value
that was missing: the producing Role pushed back in writing, in `FIXES.md` or
in a `## Comments` entry in `spec.md`, and the reviewer agreed. Prose telling
a reviewer to state which prior findings are resolved could not express that,
which is how a signed-off review with seven fixed findings and one accepted
pushback was counted as two open minors.

A finding keeps its number for the life of the Loop and appears in every later
round of the file with its current state. The file is replaced each round and
the list inside it is cumulative, which is what lets a `FIXES.md` section name
a finding number, lets the standoff rule compare a round against the one
before it, and lets the review file in the Tracker directory close a Loop
reading `2 minors: 1 open, 1 accepted`, which is where that count lives.

Both reviewers' Doorbells count findings in state `open` alone, so the message
says how much work is left rather than how much the reviewer wrote down. On
`Minors: fix` this makes `SIGNED OFF` and a non-zero minor count in the same
Doorbell impossible, which is the Sign-off condition and the Doorbell agreeing
by construction.

Three rules leave the Agent documents. `vdd-coder` loses the rule that a
review whose first line is `SIGNED OFF` and whose findings still list minors
is a fix round like any other, together with the sentence about two Doorbells
naming the same file that described the same mechanism. `vdd-coder` loses the
clause "and no Doorbell brings you back" from its closing sentence, because no
Doorbell follows Sign-off now. `vdd-create-pr` loses its open-minors step
whole: the definition of an open minor, the question to the user and the
Doorbell to the Coder. ADR-0004 permits all three. It protects a rule whose
subject survives a rewording, and each of these describes a mechanism this
decision removes, so re-expressing them would preserve a rule about nothing.

The cost this decision accepts is that the user answers before any finding
exists. `fix` is a commitment made blind: the user does not know yet how many
minors either reviewer will raise, or how many rounds closing them will take.
`vdd-start-loop` states that cost in the answer's own bullet, which is the
only mitigation available to a question asked this early.
