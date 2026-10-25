"""loop fold: the rewrite of a loop's commits after each code Sign-off.

The chain is round 1's commits, or the branch as the last fold left it. Each
later commit up to the signed commit is split by hunk, and each hunk moves into
the loop commit blame says wrote its lines; what has no owner or would conflict
stays on top as its own commit. One update-ref, guarded by the signed commit,
moves the branch only when the folded tree equals the signed tree; anything
else is a skip that leaves the branch as signed. The fold is built before
its plan, on a dry run too; the ref move is the plan's compound effect.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from ... import doorbells, gitcmd, loopstate, runner
from ...loopstate import recap, records
from ...out import TELL, Failure
from .engine import ROUND_ONE, Result, absorb, remove, report, resign
from .repo import Committer, GitFailed, Repo

if TYPE_CHECKING:
    from ...harness import Harness
    from ...loopfile import Loop

INDEX_NAME = "fold-index"


class Skip(Exception):
    """A loop the fold leaves as signed, with the reason."""

    def __init__(self, reason: str) -> None:
        Exception.__init__(self, reason)
        self.reason = reason


class SigningRefused(Exception):
    """A signing call that failed inside the Harness's sandbox, which may be
    what refused it."""

    def __init__(self, call: gitcmd.Call) -> None:
        Exception.__init__(self, call.first_error())
        self.call = call


def signed_commit(state: loopstate.State) -> tuple[int, str]:
    """(round, sha) of the code round whose review signed off, or a Failure."""
    review = state.last_review("code")
    if review is None or not review.signed_off:
        where = loopstate.not_signed_off(review)
        raise Failure(
            "The code Loop is not signed off: %s, so there is nothing to fold. Nothing was written." % where,
            "Stop, and tell the user the Loop is not finished: the code review has not signed off.",
        )
    sha = state.code_mark("end", review.round)
    if not sha:
        raise Failure(
            "Code round %d signed off, but its end is not recorded, so the signed commit is unknown. Nothing was "
            "written." % review.round,
            "Tell the user the loop's state file lacks code round %d's end, and stop." % review.round,
        )
    return review.round, sha


def plan(loop: Loop, harness: Harness, write: bool, escalation_refused: bool = False) -> runner.Plan:
    """The fold's plan. write signs the folded commits, as commit.gpgSign
    asks, which only a --write does. A signing failure inside the Harness's
    sandbox is a refusal, unless escalation_refused says the rerun outside
    it was refused; anywhere else it is the skip."""
    state = runner.open_loop(loop, "loop fold")
    _, signed = signed_commit(state)
    branch = loop.branch
    # Loaded before the plan, so a records file --write would refuse
    # refuses the dry run too.
    store = records.Records.load(loop)
    recorded = state.fold_record()
    owed = doorbells.Place(loop.root, loop.slug, loop, state).position().fold_owed
    pr_step = loopstate.pr_step(loop)
    again = "Run %s" % loopstate.fold_command(loop, harness)
    if recorded is not None and not owed:
        if recorded.kind == "folded":
            found = "The loop %s is already folded: %s is at %s." % (loop.slug, branch, recorded.tip)
        else:
            found = "The fold of %s was already skipped: %s." % (loop.slug, recorded.reason)
        nothing = ["%s Nothing was written." % found]
        return runner.Plan([runner.RenderRecap(store, state, dry=nothing, unchanged=nothing, done=[
            "%s Wrote %s/%s again." % (found, loop.tracker, recap.NAME)])], pr_step, pr_step)
    repo = Repo(loop.root)
    try:
        moved = records.moved_fold(store, loop.root, branch, signed)
    except gitcmd.Refused as error:
        raise refused_inside(loop, harness, write, error.call, branch, signed)
    if moved is not None:
        # The fold's ref moved and its line was never appended: the
        # recorded tip stands, and the fold does not run again.
        tip = str(moved.data["tip"])
        return runner.Plan([
            runner.StateLines(state, [loopstate.folded_line(tip, signed)], dry=[
                "Would record the fold of %s: it is at the folded tip %s, which an earlier fold moved it to before "
                "it stopped." % (branch, tip[:7])], done=folded(loop, branch, signed, moved)),
            runner.RenderRecap(store, state),
        ], pr_step, again)
    index_path = os.path.join(loop.dir, INDEX_NAME)
    try:
        try:
            result = fold(loop, state, repo, signed, index_path, write,
                          harness.runs_sandboxed() and not escalation_refused)
        finally:
            remove(index_path)
    except Skip as skip:
        return skipped(loop, state, store, signed, skip.reason, harness)
    except gitcmd.Refused as error:
        raise refused_inside(loop, harness, write, error.call, branch, signed)
    except SigningRefused as error:
        raise gitcmd.sandbox_refusal(
            error.call, loopstate.fold_command(loop, harness, write),
            "run %s to record the fold as skipped." % loopstate.fold_command(loop, harness, escalation_refused=True),
            ["Nothing was folded or written; %s stays at the signed commit %s." % (branch, signed[:7])],
            name="signing a folded commit")
    before, chain, tip, lines = result.before, result.chain, result.tip, result.lines
    summary = "Folded %s: %d commits into %d; the folded tree equals the signed tree (%s)." % (
        branch, before, len(chain), signed[:7])
    # The record, with the tip, is written before the ref moves: a signed tip
    # cannot be computed again once the branch is at it.
    record = records.Record(records.fold_key(signed), "Commits", [summary, ""] + lines,
                            {"tip": tip, "before": before, "after": len(chain), "report": lines})
    effects: list[runner.Effect] = [runner.SaveRecords(
        store, [record], dry=["Would fold %s: %d commits into %d." % (branch, before, len(chain))] + lines)]

    def move_ref() -> list[str]:
        try:
            repo.call("update-ref", "-m", "vdd loop fold", "refs/heads/" + branch, tip, signed)
        except GitFailed as error:
            raise runner.Instead(skipped(loop, state, store, signed, git_error(error.call), harness))
        except gitcmd.Refused as error:
            raise refused_inside(loop, harness, True, error.call, branch, signed)
        return ["Moved %s from the signed commit %s to the folded tip %s." % (branch, signed[:7], tip[:7])]

    if tip != signed:
        # Kept, so a failure after the ref moved still says so.
        effects.append(runner.Step(move_ref, keep=True))
    effects += [runner.StateLines(state, [loopstate.folded_line(tip, signed)],
                                  done=folded(loop, branch, signed, record)),
                runner.RenderRecap(store, state)]
    return runner.Plan(effects, pr_step, again)


def git_error(call: gitcmd.Call) -> str:
    """A failed call as a Skip reason names it: a timed-out call's error
    line already names the call."""
    if call.timed_out is not None:
        return "a git error: %s" % call.first_error()
    return "a git error: %s: %s" % (gitcmd.call_text(call), call.first_error())


def refused_inside(loop: Loop, harness: Harness, write: bool, call: gitcmd.Call, branch: str, signed: str) -> Failure:
    return gitcmd.sandbox_refusal(
        call, loopstate.fold_command(loop, harness, write),
        "tell the user %s was refused, and stop." % gitcmd.call_text(call),
        ["Nothing was folded or written; %s stays at the signed commit %s." % (branch, signed[:7])])


def folded(loop: Loop, branch: str, signed: str, record: records.Record) -> list[str]:
    """The done lines of a recorded fold, from its record."""
    before, after = int(record.data["before"]), int(record.data["after"])
    return (["Folded %s: %d commits into %d." % (branch, before, after)]
            + [str(line) for line in record.data.get("report") or []]
            + ["The folded tree equals the tree the Code-Reviewer signed off (%s)." % signed[:7],
               "Wrote the final commits to %s/%s." % (loop.tracker, recap.NAME),
               TELL % ("Folded %s: %d commits into %d. The tree equals the signed tree; RECAP.md lists the commits."
                       % (branch, before, after))])


def fold(
    loop: Loop, state: loopstate.State, repo: Repo, signed: str, index_path: str, write: bool,
    sandboxed: bool = False,
) -> Result:
    """What the fold built, or a Skip. It moves no ref. sandboxed raises
    SigningRefused for a signing failure, which is otherwise a Skip."""
    found, text, timed_out = gitcmd.version(loop.root)
    if timed_out:
        raise Skip("a git error: %s" % timed_out)
    if found is None or gitcmd.too_old(found):
        raise Skip("git %s is older than the 2.40 the fold needs" % gitcmd.number(text) if found else
                   "git reports no version this tool can read, and the fold needs 2.40 or newer")
    try:
        return checked_fold(loop, state, repo, signed, index_path, write, sandboxed)
    except GitFailed as error:
        raise Skip(git_error(error.call))


def checked_fold(
    loop: Loop, state: loopstate.State, repo: Repo, signed: str, index_path: str, write: bool, sandboxed: bool,
) -> Result:
    base_branch = loop.base
    branch = loop.branch
    ref = "refs/heads/" + branch
    at = repo.call("rev-parse", "--verify", "--quiet", ref, ok=(0, 1)).out.strip()
    if at != signed:
        raise Skip("the branch moved after Sign-off: %s is at %s, not the signed commit %s" % (
            branch, at[:7] if at else "nothing", signed[:7]))
    upstream = repo.call("rev-parse", "--abbrev-ref", "--symbolic-full-name", branch + "@{upstream}",
                         ok=(0, 128))
    if upstream.code == 0 and upstream.out.strip():
        raise Skip("%s has an upstream, %s, so someone may have fetched it" % (branch, upstream.out.strip()))
    merge_base = repo.out("merge-base", base_branch, signed)
    # The loop starts where round 1 started: a commit on the feature branch
    # before it is the user's own and stays as it is.
    base = state.code_mark("start", 1)
    if not base:
        raise Skip("round 1's start is not recorded")
    if repo.call("merge-base", "--is-ancestor", merge_base, base, ok=(0, 1, 128)).code != 0:
        raise Skip("round 1's start %s does not descend from the base branch's merge base" % base[:7])
    if repo.out("rev-list", "--merges", "%s..%s" % (base, signed)):
        raise Skip("the loop's history holds a merge commit")
    pushed_to(repo, branch, base, signed)
    chain_end, earlier = chain_of(state, repo, base, signed)
    before = int(repo.out("rev-list", "--count", "%s..%s" % (base, signed)))
    sign = write and repo.call("config", "--bool", "commit.gpgSign", ok=(0, 1)).out.strip() == "true"
    committer = Committer(repo, sign)
    chain, sources = absorb(repo, committer, base, chain_end, signed, index_path)
    originals = [s for s in repo.out("rev-list", "--reverse", "%s..%s" % (base, signed)).split("\n") if s]
    if sign and chain != originals:
        try:
            chain = resign(repo, committer, base, chain, originals)
        except GitFailed as error:
            if sandboxed:
                raise SigningRefused(error.call)
            raise Skip("signing a folded commit failed: %s" % error.call.first_error())
    tip = chain[-1] if chain else base
    differ = repo.names("diff-tree", "-z", "-r", "--name-only", signed, tip)
    if differ:
        raise Skip("the folded tree would differ from the signed tree in: %s" % ", ".join(differ))
    lines = report(repo, chain, sources, earlier)
    return Result(before, chain, tip, lines)


def pushed_to(repo: Repo, branch: str, base: str, signed: str) -> None:
    """Raises the Skip when a remote-tracking ref of the branch holds a loop
    commit, as a push without -u leaves it. A remote's own branch of the same
    name, outside the loop's history, is not a push."""
    for remote in repo.out("remote").split():
        tracking = "refs/remotes/%s/%s" % (remote, branch)
        sha = repo.call("rev-parse", "--verify", "--quiet", tracking, ok=(0, 1)).out.strip()
        if not sha:
            continue
        in_loop = repo.call("merge-base", "--is-ancestor", sha, signed, ok=(0, 1, 128)).code == 0
        before = repo.call("merge-base", "--is-ancestor", sha, base, ok=(0, 1, 128)).code == 0
        if in_loop and not before:
            raise Skip("%s was pushed to %s, so someone may have fetched it" % (branch, remote))


def chain_of(state: loopstate.State, repo: Repo, base: str, signed: str) -> tuple[str, str]:
    """(the chain's end, what the chain began as): the new tip of the last
    fold that moved the branch, a later skip notwithstanding, else round 1's
    recorded end. Raises the Skip when that commit is not a sound end of the
    signed history."""
    record = state.fold_record("folded")
    if record is not None:
        tip = record.tip
        rounds = [r for r in sorted(state.reviewer_reviews("code")) if state.code_mark("end", r) == record.signed]
        earlier = "folded after round %d" % rounds[-1] if rounds else "an earlier fold"
        if repo.call("merge-base", "--is-ancestor", tip, signed, ok=(0, 1, 128)).code != 0:
            raise Skip("the earlier fold's tip %s is not in the signed history" % tip[:7])
        if repo.call("merge-base", "--is-ancestor", base, tip, ok=(0, 1, 128)).code != 0:
            raise Skip("the earlier fold's tip %s does not descend from round 1's start %s" % (tip[:7], base[:7]))
        return tip, earlier
    round_one_end = state.code_mark("end", 1)
    if not round_one_end or repo.call("merge-base", "--is-ancestor", round_one_end, signed,
                                      ok=(0, 1, 128)).code != 0:
        raise Skip("round 1's end %s is not in the signed history, as in a loop whose Coder folded each round "
                   "before VDD 0.16.0-beta.5" % (round_one_end[:7] if round_one_end else "(not recorded)"))
    if repo.call("merge-base", "--is-ancestor", base, round_one_end, ok=(0, 1)).code != 0:
        raise Skip("round 1's end %s does not descend from round 1's start %s" % (round_one_end[:7], base[:7]))
    return round_one_end, ROUND_ONE


def skipped(
    loop: Loop, state: loopstate.State, store: records.Records, signed: str, reason: str, harness: Harness,
) -> runner.Plan:
    branch = loop.branch
    record = records.Record(records.fold_key(signed), "Commits", [
        "Not folded: %s stays at the signed commit %s, because %s." % (branch, signed[:7], reason)])
    after = "The branch stays local." if loop.pr == "no" else "The loop goes on to the PR."
    done = [
        "Not folded: %s." % reason,
        "%s stays at the signed commit %s. Recorded in %s/%s." % (branch, signed[:7], loop.tracker, recap.NAME),
        TELL % ("Not folded: %s stays exactly as the Code-Reviewer signed it off (%s), because %s. %s" % (
            branch, signed[:7], reason, after)),
    ]
    dry = ["Would skip the fold: %s. %s would stay at the signed commit %s." % (reason, branch, signed[:7])]
    return runner.Plan(runner.record_step(store, state, [record], [loopstate.skipped_line(signed, reason)], dry=dry,
                                          done=done),
                       loopstate.pr_step(loop), "Run %s" % loopstate.fold_command(loop, harness))
