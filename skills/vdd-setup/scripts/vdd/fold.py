"""loop fold: the one rewrite of a loop's commits, after the code Sign-off.

The loop's commits run from round 1's recorded start up to the signed
commit, the recorded end of the code round whose review signed off. A commit
before round 1's start, on the base branch or on the feature branch before
the loop, is never rewritten and owns nothing. Round 1's commits, up to
round 1's recorded end, are the chain. Each commit after round 1's end is
absorbed in order: every changed hunk is blamed against the history as folded
so far and moved into the loop commit that wrote those lines. Lines no loop commit wrote go to the latest
loop commit that changed the same file; a new file joins the commit's single
target; an insertion is owned by the lines around it; a deleted file goes to
the owner of its last lines. What has no owner, or would conflict with a
later commit, stays in a commit on top with the Coder's message, author and
date, and a later fix to its lines folds into it.

All of it runs in git's object store: blame, merge-tree --write-tree
--merge-base, commit-tree, and a temporary index under .scratch/<slug>/ for a
split. One update-ref, guarded by the signed commit, moves the branch, and
only when the folded tree equals the signed tree. Every case it cannot fold
is a skip, and a skip leaves the branch exactly as signed. The fold never
stops to ask.
"""

import os
import re

from . import gitcmd, loopstate, places, recap, signoff
from .out import Failure, Output, and_list

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
BLAME = re.compile(r"^([0-9a-f]{40}) \d+ \d+")
LINES = re.compile(rb"[^\n]*\n|[^\n]+$")
INDEX_NAME = "fold-index"
ROUND_ONE = "round 1"
NO_OWNER = "no commit of the loop wrote its lines"
CONFLICT = "folding it would conflict"


class GitFailed(Exception):
    """A git call that failed for any other reason."""

    def __init__(self, call):
        Exception.__init__(self, call.first_error())
        self.call = call


class Skip(Exception):
    """A loop the fold leaves as signed, with the reason."""

    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason


def quote_path_off():
    """core.quotePath=false through git's environment config, after any the
    user set: every name list reads a non-ASCII path as itself, not C-quoted,
    and argv stays as the call names it."""
    try:
        count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    except ValueError:
        count = 0
    return {"GIT_CONFIG_COUNT": str(count + 1), "GIT_CONFIG_KEY_%d" % count: "core.quotePath",
            "GIT_CONFIG_VALUE_%d" % count: "false"}


QUOTE_PATH = quote_path_off()


def command_text(call):
    return " ".join(["git"] + call.argv[1:3])


class Repo:
    """git in the repository root, every call checked."""

    def __init__(self, root):
        self.root = root

    def call(self, *argv, **kwargs):
        ok = kwargs.pop("ok", (0,))
        env = dict(QUOTE_PATH)
        env.update(kwargs.pop("env", None) or {})
        result = gitcmd.git(self.root, *argv, env=env, **kwargs)
        if result.code in ok:
            return result
        if result.refused:
            raise gitcmd.Refused(result)
        raise GitFailed(result)

    def out(self, *argv, **kwargs):
        return self.call(*argv, **kwargs).out.strip()

    def data(self, *argv):
        return self.call(*argv).data

    def tree(self, rev):
        return self.out("rev-parse", rev + "^{tree}")

    def parent(self, sha):
        return self.out("rev-parse", sha + "^")

    def names(self, *argv):
        """A NUL-separated name list: a path with a quote or a backslash
        stays C-quoted in a line list despite core.quotePath=false."""
        return [name for name in self.call(*argv).out.split("\0") if name]

    def files(self, sha):
        return set(self.names("diff-tree", "-z", "--no-commit-id", "--name-only", "-r", "--no-renames", sha))

    def exists(self, rev, path):
        return self.call("cat-file", "-e", "%s:%s" % (rev, path), ok=(0, 1, 128)).code == 0

    def subject(self, sha):
        return self.out("log", "-1", "--format=%s", sha)

    def short(self, sha):
        return sha[:7]


class Committer:
    """Makes commits with an original commit's author, date and message,
    signed when the repository signs its commits."""

    def __init__(self, repo, sign):
        self.repo = repo
        self.sign = sign
        self.env = {}
        if repo.call("var", "GIT_COMMITTER_IDENT", ok=(0, 1, 128)).code != 0:
            self.env = None  # set per commit from the original's committer

    def make(self, tree, parent, like, sign=False):
        """A commit of tree on parent like the commit like. Unsigned, it is
        like itself when its tree and parent are already these, so an
        unchanged commit keeps its sha, committer date and signature."""
        raw = self.repo.data("cat-file", "commit", like)
        head, _, message = raw.partition(b"\n\n")
        fields = head.split(b"\n")
        parents = [line[len(b"parent "):].decode("ascii") for line in fields if line.startswith(b"parent ")]
        if not (sign and self.sign) and fields[0] == b"tree " + tree.encode("ascii") and parents == [parent]:
            return like
        env = {}
        for line in fields:
            text = line.decode("utf-8", "replace")
            for kind in ("author", "committer"):
                if text.startswith(kind + " "):
                    match = re.match(r"^\S+ (.*) <(.*)> (\S+ \S+)$", text)
                    if not match:
                        continue
                    if kind == "author":
                        env.update(GIT_AUTHOR_NAME=match.group(1), GIT_AUTHOR_EMAIL=match.group(2),
                                   GIT_AUTHOR_DATE=match.group(3))
                    elif self.env is None:
                        env.update(GIT_COMMITTER_NAME=match.group(1), GIT_COMMITTER_EMAIL=match.group(2))
        argv = ["commit-tree", tree, "-p", parent, "-F", "-"]
        if sign and self.sign:
            argv.insert(1, "-S")
        return self.repo.out(*argv, data=message, env=env)


def split_lines(data):
    return LINES.findall(data)


class Split:
    """A later-round commit's change, split by the commit of the folded
    history that wrote the lines it changes.

    tip is the folded history's last commit, whose tree equals the commit's
    parent's tree; chain is that history, oldest first. An owner is an index
    into chain, or None: no commit of the loop wrote the lines."""

    def __init__(self, repo, chain, tip, commit, index_path):
        self.repo = repo
        self.chain = chain
        self.tip = tip
        self.commit = commit
        self.index_path = index_path
        self.positions = dict((sha, i) for i, sha in enumerate(chain))
        self.touched_cache = {}
        self.hunks = {}
        self.whole = {}
        self.text = {}
        self.mode = {}
        added = set()
        for name in repo.names("diff", "-z", "--name-only", "--no-renames", tip, commit):
            has_old = repo.exists(tip, name)
            has_new = repo.exists(commit, name)
            old = repo.data("show", "%s:%s" % (tip, name)) if has_old else b""
            new = repo.data("show", "%s:%s" % (commit, name)) if has_new else None
            listed = repo.out("ls-tree", commit if has_new else tip, "--", name)
            self.mode[name] = listed.split(" ")[0] if listed else "100644"
            old_lines = split_lines(old)
            self.text[name] = (old_lines, new)
            if not has_old:
                self.whole[name] = None
                added.add(name)
                continue
            if not has_new:
                owner = self.latest(self.blame(name, 1, len(old_lines))) if old_lines else None
                self.whole[name] = owner if owner is not None else self.file_owner(name)
                continue
            hunks = []
            # The fold's own settings: a diff.interHunkContext would merge two
            # owners' hunks, and a textconv would change the line numbers.
            diff = repo.out("diff", "-U0", "--inter-hunk-context=0", "--no-textconv", "--no-color", "--no-ext-diff",
                            "--no-renames", tip, commit, "--", name)
            for line in diff.split("\n"):
                match = HUNK.match(line)
                if not match:
                    continue
                a = int(match.group(1))
                b = int(match.group(2)) if match.group(2) is not None else 1
                c = int(match.group(3))
                d = int(match.group(4)) if match.group(4) is not None else 1
                if b:
                    owner = self.latest(self.blame(name, a, a + b - 1))
                else:
                    # An insertion after line a: the lines around it decide.
                    near = [x for x in (a, a + 1) if 1 <= x <= len(old_lines)]
                    owner = self.latest(self.blame(name, min(near), max(near))) if near else None
                hunks.append((a, b, c, d, owner if owner is not None else self.file_owner(name)))
            if hunks:
                self.hunks[name] = hunks
            else:
                # A mode change or a binary file: the whole file.
                self.whole[name] = self.file_owner(name)
        owners = set(h[4] for hs in self.hunks.values() for h in hs) | set(self.whole.values())
        real = sorted(o for o in owners if o is not None)
        if len(real) == 1:
            # A new file joins the commit's single target.
            for name in added:
                self.whole[name] = real[0]

    def touched(self, i):
        if i not in self.touched_cache:
            self.touched_cache[i] = self.repo.files(self.chain[i])
        return self.touched_cache[i]

    def file_owner(self, name):
        """Lines no loop commit wrote: the latest loop commit that changed the
        file, else None."""
        found = [i for i in range(len(self.chain)) if name in self.touched(i)]
        return found[-1] if found else None

    def blame(self, name, start, end):
        owners = []
        # An empty --ignore-revs-file clears the revisions any
        # blame.ignoreRevsFile names, which would move lines to other commits.
        argv = ("blame", "--no-textconv", "--ignore-revs-file=", "--porcelain", "-L", "%d,%d" % (start, end),
                self.tip, "--", name)
        try:
            text = self.repo.out(*argv)
        except GitFailed as error:
            # A blame.ignoreRevsFile naming a missing file fails every blame,
            # and no setting clears it. Set where it usually is, in the global
            # or system config, it is left out.
            if "could not open object name list" not in error.call.err:
                raise
            text = self.repo.out(*argv, env={"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull})
        for line in text.split("\n"):
            match = BLAME.match(line)
            if match:
                owners.append(self.positions.get(match.group(1)))
        return owners

    @staticmethod
    def latest(owners):
        known = [o for o in owners if o is not None]
        return max(known) if known else None

    def owners(self):
        """owner -> sorted files, owner an index into chain or None."""
        found = {}
        for name, hunks in self.hunks.items():
            for hunk in hunks:
                found.setdefault(hunk[4], set()).add(name)
        for name, owner in self.whole.items():
            found.setdefault(owner, set()).add(name)
        return dict((owner, sorted(names)) for owner, names in found.items())

    def tree_with(self, included):
        """The tip's tree with the changes of the owners in included
        applied, written through a temporary index."""
        env = {"GIT_INDEX_FILE": self.index_path}
        try:
            self.repo.call("read-tree", self.tip, env=env)
            for name, hunks in self.hunks.items():
                if not any(h[4] in included for h in hunks):
                    continue
                old, new_data = self.text[name]
                new = split_lines(new_data)
                parts = []
                position = 0
                for a, b, c, d, owner in hunks:
                    start = a - 1 if b else a
                    parts += old[position:start]
                    parts += new[c - 1:c - 1 + d] if owner in included else old[start:start + b]
                    position = start + b
                parts += old[position:]
                self.put(name, b"".join(parts), env)
            for name, owner in self.whole.items():
                if owner not in included:
                    continue
                data = self.text[name][1]
                if data is None:
                    self.repo.call("update-index", "--force-remove", "--", name, env=env)
                else:
                    self.put(name, data, env)
            return self.repo.out("write-tree", env=env)
        finally:
            remove(self.index_path)

    def put(self, name, data, env):
        blob = self.repo.out("hash-object", "-w", "--stdin", data=data)
        self.repo.call("update-index", "--add", "--cacheinfo", "%s,%s,%s" % (self.mode[name], blob, name), env=env)


def remove(path):
    for candidate in (path, path + ".lock"):
        if os.path.lexists(candidate):
            try:
                os.remove(candidate)
            except OSError:
                pass


def merge_tree(repo, base, ours, theirs):
    """The tree of theirs' change (base to theirs) applied to ours, or None on
    a conflict."""
    result = repo.call("merge-tree", "--write-tree", "--no-messages", "--merge-base=" + base, ours, theirs,
                       ok=(0, 1))
    if result.code == 1:
        return None
    return result.out.split("\n")[0].strip()


def replay(repo, committer, chain, start, parent):
    """chain[start:] replayed onto parent: the new commits, or None on a
    conflict."""
    made = []
    for sha in chain[start:]:
        tree = merge_tree(repo, repo.parent(sha), parent, sha)
        if tree is None:
            return None
        parent = committer.make(tree, parent, sha)
        made.append(parent)
    return made


def absorb(repo, committer, base, round_one_end, signed, index_path):
    """(chain, sources): the folded history oldest first, and for each of its
    commits the (original sha, files or None for the whole commit, why it
    stayed) it was built from."""
    chain = [s for s in repo.out("rev-list", "--reverse", "%s..%s" % (base, round_one_end)).split("\n") if s]
    sources = [[(sha, None, ROUND_ONE)] for sha in chain]
    later = [s for s in repo.out("rev-list", "--reverse", "%s..%s" % (round_one_end, signed)).split("\n") if s]
    for commit in later:
        tip = chain[-1] if chain else base
        split = Split(repo, chain, tip, commit, index_path)
        owners = split.owners()
        done = set()
        for i in sorted(o for o in owners if o is not None):
            want = split.tree_with(done | {i})
            fix = committer.make(want, chain[-1], commit)
            tree = merge_tree(repo, chain[-1], chain[i], fix)
            folded = None
            if tree is not None:
                head = committer.make(tree, repo.parent(chain[i]), chain[i])
                rest = replay(repo, committer, chain, i + 1, head)
                if rest is not None and repo.tree((rest or [head])[-1]) == want:
                    folded = chain[:i] + [head] + rest
            if folded is None:
                continue  # it would conflict: these lines stay on top
            chain = folded
            done.add(i)
            sources[i].append((commit, owners[i], None))
        if repo.tree(chain[-1] if chain else base) != repo.tree(commit):
            left = set(owners) - done
            stay = sorted(set(name for owner in left for name in owners[owner]))
            why = NO_OWNER if left == {None} else CONFLICT
            chain.append(committer.make(repo.tree(commit), chain[-1] if chain else base, commit))
            sources.append([(commit, stay if done else None, why)])
    return chain, sources


def resign(repo, committer, base, chain, originals):
    """The chain with every commit the absorb made made again, signed: the
    absorb's own commits are unsigned. A leading commit the fold kept as it
    was stays."""
    kept = 0
    while kept < len(chain) and kept < len(originals) and chain[kept] == originals[kept]:
        kept += 1
    result = chain[:kept]
    parent = chain[kept - 1] if kept else base
    for sha in chain[kept:]:
        parent = committer.make(repo.tree(sha), parent, sha, sign=True)
        result.append(parent)
    return result


def report(repo, chain, sources):
    lines = []
    for sha, source in zip(chain, sources):
        lines.append("  %s %s" % (repo.short(sha), repo.subject(sha)))
        for original, files, why in source:
            what = "%s %s" % (repo.short(original), repo.subject(original))
            if why == ROUND_ONE:
                lines.append("      %s (round 1)" % what)
            elif why:
                part = "" if files is None else ": %s" % and_list(files)
                lines.append("      %s%s, its own commit: %s" % (what, part, why))
            else:
                lines.append("    + %s: %s" % (what, and_list(files)))
    return lines


# --- the command ---

def fold_command(loop, harness, write=True):
    return "%s loop fold --slug %s --harness %s%s" % (places.command(), loop.slug, harness.name,
                                                       " --write" if write else "")


def signed_commit(state):
    """(round, sha) of the code round whose review signed off, or a Failure."""
    review = state.last_review("code")
    if review is None or not review.signed_off:
        where = "no code review is recorded" if review is None else "code round %d's review left findings open" % (
            review.round)
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


def run(loop, harness, write):
    state = loopstate.open_loop(loop, "loop fold")
    _, signed = signed_commit(state)
    out = Output()
    branch, _ = loop.setting("Feature branch")
    recorded = state.fold_outcome()
    if recorded is not None:
        if recorded[0] == "folded":
            out.line("The loop %s is already folded: %s is at %s. Nothing was written." % (
                loop.slug, branch, recorded[1]))
        else:
            out.line("The fold of %s was already skipped: %s. Nothing was written." % (loop.slug, recorded[2]))
        return out.finish(signoff.pr_step(loop))
    repo = Repo(loop.root)
    index_path = os.path.join(loop.dir, INDEX_NAME)
    try:
        try:
            result = fold(loop, state, repo, signed, index_path, write)
        finally:
            remove(index_path)
    except Skip as skip:
        return skipped(loop, state, out, signed, skip.reason, write, harness)
    except gitcmd.Refused as error:
        raise Failure(
            ["A sandbox refused %s inside the tool: %s" % (command_text(error.call), error.call.first_error()),
             "Nothing was folded or written; %s stays at the signed commit %s." % (branch, signed[:7])],
            "Rerun %s outside the sandbox, the way your Harness grants that; when that is refused too, tell the "
            "user %s was refused, and stop." % (fold_command(loop, harness, write), command_text(error.call)),
        )
    before, chain, sources, tip, lines = result
    if not write:
        out.line("Would fold %s: %d commits into %d." % (branch, before, len(chain)))
        for line in lines:
            out.line(line)
        return out.finish("Run %s" % fold_command(loop, harness))
    state.append("fold folded %s signed %s" % (tip, signed))
    summary = "Folded %s: %d commits into %d; the folded tree equals the signed tree (%s)." % (
        branch, before, len(chain), signed[:7])
    recap.write(loop, state, {"Commits": [summary, ""] + lines})
    out.line("Folded %s: %d commits into %d." % (branch, before, len(chain)))
    for line in lines:
        out.line(line)
    out.line("The folded tree equals the tree the Code-Reviewer signed off (%s)." % signed[:7])
    out.line("Wrote the final commits to %s/%s." % (loop.tracker, recap.NAME))
    out.tell("Folded %s: %d commits into %d. The tree equals the signed tree; RECAP.md lists the commits."
             % (branch, before, len(chain)))
    return out.finish(signoff.pr_step(loop))


def fold(loop, state, repo, signed, index_path, write):
    """(commits before, final chain, sources, new tip, report lines), or a
    Skip. Moves the branch only with write."""
    found, text = gitcmd.version(loop.root)
    if found is None or gitcmd.too_old(found):
        raise Skip("git %s is older than the 2.40 the fold needs" % gitcmd.number(text) if found else
                   "git reports no version this tool can read, and the fold needs 2.40 or newer")
    try:
        return checked_fold(loop, state, repo, signed, index_path, write)
    except GitFailed as error:
        raise Skip("a git error: %s: %s" % (command_text(error.call), error.call.first_error()))


def checked_fold(loop, state, repo, signed, index_path, write):
    base_branch, _ = loop.setting("Base branch")
    branch, _ = loop.setting("Feature branch")
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
    round_one_end = state.code_mark("end", 1)
    if not round_one_end or repo.call("merge-base", "--is-ancestor", round_one_end, signed,
                                      ok=(0, 1, 128)).code != 0:
        raise Skip("round 1's end %s is not in the signed history, as in a loop whose Coder folded each round "
                   "before VDD 0.16.0-beta.5" % (round_one_end[:7] if round_one_end else "(not recorded)"))
    if repo.call("merge-base", "--is-ancestor", base, round_one_end, ok=(0, 1)).code != 0:
        raise Skip("round 1's end %s does not descend from round 1's start %s" % (round_one_end[:7], base[:7]))
    before = int(repo.out("rev-list", "--count", "%s..%s" % (base, signed)))
    sign = write and repo.call("config", "--bool", "commit.gpgSign", ok=(0, 1)).out.strip() == "true"
    committer = Committer(repo, sign)
    chain, sources = absorb(repo, committer, base, round_one_end, signed, index_path)
    originals = [s for s in repo.out("rev-list", "--reverse", "%s..%s" % (base, signed)).split("\n") if s]
    if sign and chain != originals:
        try:
            chain = resign(repo, committer, base, chain, originals)
        except GitFailed as error:
            raise Skip("signing a folded commit failed: %s" % error.call.first_error())
    tip = chain[-1] if chain else base
    differ = repo.names("diff-tree", "-z", "-r", "--name-only", signed, tip)
    if differ:
        raise Skip("the folded tree would differ from the signed tree in: %s" % ", ".join(differ))
    lines = report(repo, chain, sources)
    if write and tip != signed:
        repo.call("update-ref", "-m", "vdd loop fold", ref, tip, signed)
    return before, chain, sources, tip, lines


def skipped(loop, state, out, signed, reason, write, harness):
    branch, _ = loop.setting("Feature branch")
    if not write:
        out.line("Would skip the fold: %s. %s would stay at the signed commit %s." % (reason, branch, signed[:7]))
        return out.finish("Run %s" % fold_command(loop, harness))
    state.append("fold skipped %s %s" % (signed, " ".join(reason.split())))
    recap.write(loop, state, {"Commits": [
        "Not folded: %s stays at the signed commit %s, because %s." % (branch, signed[:7], reason)]})
    out.line("Not folded: %s." % reason)
    out.line("%s stays at the signed commit %s. Recorded in %s/%s." % (branch, signed[:7], loop.tracker, recap.NAME))
    pr, _ = loop.setting("PR")
    after = "The branch stays local." if pr == "no" else "The loop goes on to the PR."
    out.tell("Not folded: %s stays exactly as the Code-Reviewer signed it off (%s), because %s. %s" % (
        branch, signed[:7], reason, after))
    return out.finish(signoff.pr_step(loop))
