# A Loop folds once, after the code Sign-off

The Coder commits plainly, in the repository's convention: one commit per
Ticket in round 1, its fixes as it likes in a later round, and never a
rewrite of an earlier round. A later round is reviewed on its own diff, from
the previous round's recorded end. Once the code review signs off, the VDD
tool folds the branch once: it moves each later-round fix into the loop
commit that wrote the lines it changes, keeps what has no such commit or
would conflict as a commit on top with the Coder's message, and never stops
to ask. It moves the branch only to a tree equal to the tree the
Code-Reviewer signed off; whenever it cannot, the branch stays as signed and
the Loop goes on to the PR. A repository that signs its commits keeps the
folded commits signed. The fold runs in git's object store with `git
merge-tree --write-tree --merge-base`, so VDD requires git 2.40 or newer.

## Considered options

**The Coder folds its fixes each round.** Rejected: every fold rewrote the
commits the Code-Reviewer had read, so each recorded round end went stale
and a later round could only be reviewed over the whole branch. It needed a
`Ticket NN` line in every commit message to find the owning commit, and a
rebase that stopped sent the Coder down a conflict path written in prose.

**Every commit routed through the tool.** Rejected: each pass that tried it
grew a rule per observed slip, and still needed the fold at the end.

**A conflict sent to the Coder, or to the user as `BLOCKED`.** First chosen,
then rejected once the scripted fold cases ran: a fix that would conflict
loses nothing by staying on top as its own commit, and no Role has to resolve
a fold conflict.

**A rebase in a scratch worktree, or patches on a temporary index, for a git
older than 2.40.** Rejected: each is a second fold with its own failure modes
for a shrinking set of machines, and Setup tells the user to install a newer
git instead.
