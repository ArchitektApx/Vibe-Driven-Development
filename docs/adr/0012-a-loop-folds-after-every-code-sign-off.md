# A Loop folds after every code Sign-off

The Coder commits plainly: one commit per Ticket in round 1, plain fix commits
after, never a rewrite of an earlier round, so each later round is reviewed on
its own diff. At every code Sign-off, including one after User findings
reopened the Loop, the VDD tool folds the branch without asking: each fix moves
into the commit that wrote the lines it changes, and a fix with no such commit,
or one that would conflict, stays on top as its own commit. The branch moves
only when the result equals what was signed off and the branch was never
pushed; otherwise it stays as signed. Signed commits stay signed. The fold uses
`git merge-tree --write-tree --merge-base`, so VDD needs git 2.40 or newer.

## Considered options

**One fold, at the first code Sign-off.** Rejected once User findings could
reopen a Loop: the later fixes stayed on top, and the reopened round was
reviewed over the whole loop.

**The Coder folds its fixes each round.** Rejected: each fold rewrote commits
the Code-Reviewer had read, so later rounds were reviewed over the whole
branch, and a stopped rebase left the Coder resolving conflicts from prose.

**Every commit routed through the tool.** Rejected: it grew a rule per slip
and still needed the fold.

**A conflict sent to the Coder or the user.** Rejected: a fix that would
conflict loses nothing as its own commit on top.

**A fallback for git older than 2.40.** Rejected: a second fold with its own
failure modes for few machines; Setup asks for a newer git.
