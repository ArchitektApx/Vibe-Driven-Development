# A fold that stops on a conflict

Resolve the conflict in the file, stage it, and continue with
`git rebase --continue`.

When that same rebase stops a second time, abandon the fold:

1. `git rebase --abort`, which restores the fixup commits as they stood.
2. `git reset --soft <round-start sha>`, which collapses the round back into
   the index. That sha is the one this round's section of `FIXES.md` recorded
   before its first fixup commit.
3. Commit once, in the repository's convention, naming that round's findings.

The reset collapses everything the round committed, which includes a commit it
made for a fix no Ticket owned, so that change lands in the appended commit
too.
