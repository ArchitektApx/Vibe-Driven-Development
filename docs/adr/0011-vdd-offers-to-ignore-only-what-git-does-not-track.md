# VDD offers to ignore only what git does not already track

The environment check asks, once per repository, whether Agent configuration
and Domain docs belong in the user's history. It offers ignore for a path only
when git does not already track that path. A tracked path predates VDD or was
committed on purpose, and an ignore line would not hide it anyway, because git
keeps tracking a file after it appears in the ignore file.

Where a group's every path is already tracked, the check asks nothing at all.
It writes the group's tracked marker and prints one sentence naming those paths
and the command that untracks them. VDD prints that command and never runs it.

## Considered options

**Running the untracking command for the user, so an ignore answer takes
effect on the paths that need it most.** Rejected. `git rm --cached` stages a
deletion, and a committed deletion removes the file from every clone, which is
further than an environment check reaches. The user may be mid-branch when the
check runs; a check that touches the index turns a read-only readiness pass
into a change to the work in hand. Naming the command costs the user one
paste and leaves the decision where it belongs.

**Asking anyway and writing the ignore lines regardless, so the two groups
answer the same question everywhere.** Rejected. The answer would change
nothing for a tracked path, so the question would be asking the user to choose
between two identical outcomes. A question whose answers do not differ teaches
the user that the check's questions are noise.

## Consequences

A repository that committed these files before VDD asked is never asked. This
is the common shape for anyone upgrading VDD rather than starting fresh, and
the untrack sentence is the only channel that reaches them. It fires in the run
that writes the group's marker and in no run after it, so a repository that
tracks these files on purpose reads the advice once and is not nagged by a
choice it has already made.

No file is ever removed from history by an environment check. A check that
edits `.gitignore` and prints advice cannot look like data loss, which is what
lets it run unattended at the start of every Workflow.

The ignore lines for paths that do not exist yet are written blind, because
most of these paths are absent when the check runs: the agent docs wait on the
collection setup, and the glossary and the records wait on the grilling, which
runs during the Planner's turn after the check has already finished. A question
that waited for the files to exist would first fire on the Workflow after the
one that created them, which is one Workflow too late to be worth asking.

The instructions file is the one path the blind write cannot cover, because VDD
cannot know which of the two names the collection setup will create and writing
both would ignore a file the user may write by hand later. Its line is deferred
to the first run that finds it present and untracked with the group's marker
recording ignore.
