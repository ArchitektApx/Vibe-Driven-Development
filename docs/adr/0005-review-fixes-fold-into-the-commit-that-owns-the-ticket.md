# A review round's fixes fold into the commit that owns the Ticket

The Coder commits one `fixup!` per finding against the commit that owns that
finding's Ticket, then runs one autosquash rebase before it hands off. The
branch therefore reads as one commit per Ticket plus any commit no Ticket owned,
however many review rounds it took. The Coder writes HEAD as it stood when each
round began into `FIXES.md`, so the Code-Reviewer can still diff from the state
it read after the rebase rewrote the commits.

## Considered options

**Appending each round's fixes as their own commit.** What every release up to
0.5.0 shipped, and what the Loop before this one left on its branch: thirteen
commits, one per Ticket, and a fourteenth on top repairing them. Rejected
because a branch that fixes its own unpushed commits one commit later reads as
noise to anyone who opens the history afterwards, and because it contradicted
the Code-Reviewer's sign-off sentence, which told the user the commits already
existed one per Ticket.

It bought one thing the fold gives up. "What changed since the round I
reviewed" was free under appending, because the later commits were the answer.
The fold replaces that with a sha the Coder records once per round in its
Working file, which costs a line of `FIXES.md` per round and survives the
rewrite.

## Consequences

Folding costs two things that appending does not. A fix touching lines a later
Ticket changed stops the rebase on a conflict. Where commits are signed, the
rebase signs every commit it re-creates, so a signing failure leaves the rebase
stopped part-way rather than producing an unsigned commit.

Two fallbacks keep the branch out of a state the Coder cannot leave. A branch
that has an upstream is appended to rather than rewritten, because history
someone may have fetched is not the Coder's to rewrite; the Coder tests for one
instead of asking the user. A conflict that survives one resolution ends in
`git rebase --abort` and a single appended commit for that round, with the
conflict and the abort recorded in `FIXES.md`.

The Code-Reviewer is unaffected. It diffs the whole branch against the base
branch and recomputes that each round, so a rewritten branch gives it the same
answer as before.
