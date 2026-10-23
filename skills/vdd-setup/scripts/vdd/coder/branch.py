"""The Coder's git work on the feature branch: the head, uncommitted and
untracked files, the branch switch decided read-only and then applied,
and the untracked-file snapshot a round starts with."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import gitcmd
from ..out import Failure, Output

if TYPE_CHECKING:
    from .coder import Round


def git(root: str, *argv: str) -> gitcmd.Call:
    """The finished gitcmd.Call of a git command run in root; refuses when git
    cannot run."""
    call = gitcmd.answered(gitcmd.git(root, *argv))
    if call.code is None:
        raise Failure("git could not run: %s" % call.first_error(),
                      "Tell the user git is needed for the Coder's round, and stop.")
    return call


def head(root: str) -> str:
    call = git(root, "rev-parse", "HEAD")
    sha = call.out.strip()
    if not call.ok or not sha:
        raise Failure("This repository has no commit, so the round has no start.",
                      "Tell the user the repository needs a first commit on the base branch, and stop.")
    return sha


def branch_exists(root: str, branch: str) -> bool:
    return git(root, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch).ok


def dirty(root: str) -> list[str]:
    """The tracked files with uncommitted changes."""
    call = git(root, "diff", "--name-only", "HEAD")
    if not call.ok:
        raise Failure("git diff failed: %s" % call.err.strip(), "Tell the user git diff fails in this repository, and stop.")
    return [line.strip() for line in call.out.strip().split("\n") if line.strip()]


def untracked(root: str) -> list[str]:
    """The work tree's untracked, not ignored files, from git's NUL-separated
    list. A path that holds a line break is left out: a snapshot keeps one
    path per line."""
    call = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if not call.ok:
        raise Failure("git ls-files failed: %s" % call.err.strip(),
                      "Tell the user git ls-files fails in this repository, and stop.")
    return [name for name in call.out.split("\0") if name and "\n" not in name]


def decide_branch(round_: Round) -> str | None:
    """The branch switch the round needs, read-only: None on the feature
    branch, "switch" to an existing one, "create" from the base branch. Refuses
    on any other branch, naming both."""
    root = round_.loop.root
    current = gitcmd.current_branch(root)
    if current == round_.branch:
        return None
    if current != round_.base:
        raise Failure(
            "The checked-out branch is %s: neither the base branch %s nor the feature branch %s. Nothing was "
            "written." % (current or "none (a detached HEAD)", round_.base, round_.branch),
            "Return QUESTION: I am on %s, neither the base branch %s nor the feature branch %s. Which branch "
            "do I work on?" % (current or "a detached HEAD", round_.base, round_.branch),
        )
    return "switch" if branch_exists(root, round_.branch) else "create"


def to_branch(round_: Round, out: Output, write: bool = True) -> bool:
    """Put the Coder on the feature branch, or refuse naming both branches.
    Without write, switch nothing and return whether a switch is owed."""
    decision = decide_branch(round_)
    if decision is None:
        out.line("On the feature branch %s." % round_.branch)
        return False
    if not write:
        if decision == "switch":
            out.line("Would switch to the feature branch %s." % round_.branch)
        else:
            out.line("Would create the feature branch %s from %s and switch to it." % (round_.branch, round_.base))
        return True
    apply_branch(round_, decision, out)
    return False


def apply_branch(round_: Round, decision: str, out: Output) -> None:
    """Switch to the feature branch as decide_branch decided."""
    root = round_.loop.root
    if decision == "switch":
        call = git(root, "checkout", "-q", round_.branch)
        verb = "Switched to the feature branch %s." % round_.branch
    else:
        call = git(root, "checkout", "-q", "-b", round_.branch)
        verb = "Created the feature branch %s from %s and switched to it." % (round_.branch, round_.base)
    if not call.ok:
        error = call.err.strip()
        if call.refused:
            raise gitcmd.sandbox_refusal(
                call, round_.command("start"),
                "tell the user git could not check out the feature branch %s, and stop." % round_.branch,
                ["git could not switch to %s." % round_.branch], "git checkout %s" % round_.branch)
        raise Failure(
            "git could not switch to %s: %s" % (round_.branch, error),
            "Tell the user git could not check out the feature branch %s, and stop." % round_.branch,
        )
    out.done(verb)


def new_untracked(round_: Round) -> list[str]:
    """The untracked, not ignored files the round's start did not record. A
    round with no snapshot (started on an older version) has none."""
    before = round_.snapshot()
    if before is None:
        return []
    known = set(before)
    known.add(round_.path(round_.snapshot_name()))
    return [name for name in untracked(round_.loop.root) if name not in known]


def start_gone(round_: Round) -> str | None:
    """The refusal for a round whose recorded start is no longer in HEAD's
    history, or None. The fold after the code Sign-off reads every round's
    recorded end; an amend, rebase or reset of an earlier round's commit
    loses it (ticket 71)."""
    start = round_.state.code_mark("start", round_.number)
    if not start:
        return None
    if git(round_.loop.root, "merge-base", "--is-ancestor", start, "HEAD").ok:
        return None
    return ("Round %d started at %s, and that commit is no longer in %s's history: an earlier commit was amended, "
            "rebased or reset. Bring the earlier commits back with `git reset --soft %s`, which keeps your "
            "changes, then commit the change as a new commit." % (round_.number, start, round_.branch, start))
