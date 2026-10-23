"""The idea store's safety, driven from outside: the write lock, the
journal with its recovery and validation, the ledger, and killed runs staged
as a leftover journal and lock."""

import json
import os
import shutil
import stat
import subprocess
import sys
import time
import unittest

from test_brainstorm import S, TODAY, BrainstormTest
from vddtest import ENTRY, WINDOWS, b64


# Takes the store lock as the tool does, writes its pid, says "locked" and
# holds it for argv[2] seconds; the kernel releases it when the process ends.
LOCKER = """
import os, sys, time
path, hold = sys.argv[1], float(sys.argv[2])
fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
if sys.platform == "win32":
    import msvcrt
    os.lseek(fd, 1 << 20, 0)
    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
else:
    import fcntl
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
os.ftruncate(fd, 0)
os.lseek(fd, 0, 0)
os.write(fd, str(os.getpid()).encode("ascii"))
sys.stdout.write("locked\\n")
sys.stdout.flush()
time.sleep(hold)
"""


# Runs the VDD tool (argv[1]) with an audit hook: the first time it raises
# the audit event argv[2] on a path that contains argv[3], the file at that
# path is copied to argv[4]. The tool's own arguments follow.
AUDITED = """
import os, runpy, shutil, sys
entry, event, needle, out = sys.argv[1:5]
del sys.argv[1:5]
sys.argv[0] = entry
done = []
def hook(name, args):
    if done or name != event or not args or not isinstance(args[0], str) or needle not in args[0]:
        return
    done.append(1)
    shutil.copyfile(args[0], out + ".part")
    os.replace(out + ".part", out)
sys.addaudithook(hook)
sys.path.insert(0, os.path.dirname(entry))
runpy.run_path(entry, run_name="__main__")
"""


def audited(test, event, needle, out, *args):
    """The tool started on args, copying the file it first raises event on
    whose path contains needle to out."""
    return subprocess.Popen([sys.executable, "-c", AUDITED, ENTRY, event, needle, out, "brainstorm"] + list(args),
                            cwd=test.box.proj, env=test.box.env(VDD_TODAY=TODAY), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)


def hold(test, seconds, rel=S + ".state/lock"):
    """A child process holding the lock at rel for seconds."""
    path = test.box.path(rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    child = subprocess.Popen([sys.executable, "-c", LOCKER, path, str(seconds)], stdout=subprocess.PIPE)
    test.addCleanup(child.wait)
    test.addCleanup(lambda: child.poll() is None and child.kill())
    out = child.stdout
    if out is None:
        raise AssertionError("the locker has no standard output")
    test.assertEqual(out.readline().strip(), b"locked")
    out.close()
    return child


class LockTest(BrainstormTest):
    def setUp(self):
        BrainstormTest.setUp(self)
        self.new("main-idea", "Main idea", "The whole thing.")
        self.new("part-one", "Part one", "The first half.", "--parent", "main-idea")

    def hold(self, seconds, rel=S + ".state/lock"):
        return hold(self, seconds, rel)

    def set_size(self, size="large"):
        return self.bs("set", "--idea", "part-one", "--size", size, "--write")

    def test_a_held_lock_is_waited_for_and_the_write_lands(self):
        """Prevents a second writer refused for a holder that needs a moment
        (T1, 9 of 20 parallel writes refused): a lock freed within 5 s makes
        the write wait, then land."""
        self.hold(1.5)
        started = time.monotonic()
        result = self.set_size()
        self.assertEqual(result.code, 0, result)
        self.assertGreater(time.monotonic() - started, 1.0)
        self.assertIn("size: large", self.read("part-one.md"))

    def test_a_lock_held_past_the_wait_is_refused_with_its_pid(self):
        """Prevents an endless wait, and a refusal that tells the user to
        delete a file that would not help: past 5 s the write refuses, names
        the holder's pid, and writes nothing."""
        child = self.hold(30)
        before = self.ideas_tree()
        result = self.set_size()
        self.assertEqual(result.code, 1, result)
        self.assertIn("Another Session is writing to the idea store right now (process %d). Nothing was written."
                      % child.pid, result.lines)
        self.assertEqual(result.last, "Next: Run the same command again. If it refuses again, tell the user another "
                                      "VDD command (process %d) is writing to the idea store, and stop." % child.pid)
        self.assertEqual(self.ideas_tree(), before)

    def test_a_killed_holders_lock_is_taken_at_once(self):
        """Prevents a crash blocking the next command (red team M9, U13): the
        kernel frees a dead holder's lock, so the write lands without a
        wait, though the file still names the dead pid."""
        child = self.hold(60)
        child.kill()
        child.wait()
        self.assertTrue(self.read(".state/lock").strip().isdigit())
        started = time.monotonic()
        result = self.set_size()
        self.assertEqual(result.code, 0, result)
        # A run that waited out the 5 s takes at least that long.
        self.assertLess(time.monotonic() - started, 5)
        self.assertIn("size: large", self.read("part-one.md"))

    def test_parallel_writes_all_land(self):
        """Prevents a lost or refused update among parallel subagents (T1's
        parallel.py): 4 writes at once, 5 rounds, every one lands."""
        for n in range(4):
            self.new("idea-%d" % n)
        env = self.box.env(VDD_TODAY=TODAY)
        for round_n in range(5):
            procs = [subprocess.Popen([sys.executable, ENTRY, "brainstorm", "note", "--idea", "idea-%d" % n,
                                       "--section", "Evidence", "--text", "round %d" % round_n, "--write"],
                                      cwd=self.box.proj, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for n in range(4)]
            for proc in procs:
                result = self.box.finish(proc)
                self.assertEqual(result.code, 0, result)
        for n in range(4):
            text = self.read("idea-%d.md" % n)
            for round_n in range(5):
                self.assertIn("round %d" % round_n, text)

    def test_the_lock_file_stays(self):
        """Prevents a release or a takeover deleting the lock file, which
        would let two writers hold a lock each (story 5)."""
        self.assertTrue(self.exists(".state/lock"))
        self.assertEqual(self.set_size().code, 0)
        self.assertTrue(self.exists(".state/lock"))
        self.assertEqual(self.bs("set", "--idea", "part-one", "--status", "done", "--write").code, 1)
        self.assertTrue(self.exists(".state/lock"))

    @unittest.skipUnless(sys.platform == "darwin",
                         "no trigger for the lock call's failure on Linux or Windows: flock works on a FIFO on Linux, "
                         "and Windows has no FIFOs")
    def test_a_lock_call_the_filesystem_refuses_goes_ahead_without_it(self):
        """Prevents a lone writer blocked where the lock call is not
        supported: a FIFO at .state/lock makes flock fail with ENOTSUP on
        macOS; the write lands and says it went ahead without the lock."""
        path = self.box.path(S + ".state/lock")
        os.remove(path)
        os.mkfifo(path)
        result = self.set_size()
        self.assertEqual(result.code, 0, result)
        found = [line for line in result.lines if line.startswith("The idea store's lock is not supported here (")]
        self.assertEqual(len(found), 1, result)
        self.assertTrue(found[0].endswith("); this command went ahead without it."), result)
        self.assertIn("size: large", self.read("part-one.md"))

    def test_a_lock_file_that_cannot_be_opened_refuses_naming_it(self):
        """Prevents a real fault hidden behind the fallback: a folder at
        .state/lock refuses the write, naming the file."""
        path = self.box.path(S + ".state/lock")
        os.remove(path)
        os.mkdir(path)
        before = self.ideas_tree()
        result = self.set_size()
        self.assertEqual(result.code, 1, result)
        self.assertContract(result)
        self.assertIn("The idea store's lock file .scratch/_brainstorming/.state/lock could not be opened", result.text)
        self.assertEqual(self.ideas_tree(), before)

    def test_a_held_migration_lock_refuses_as_migrating(self):
        """Prevents two migrations at once, and a wait without end: the
        migration lock waits as every store lock does, then refuses naming
        the migration."""
        shutil.rmtree(self.box.path(S))
        self.box.write(S + "index.md", "# Ideas\n")
        self.box.write(S + "old-idea.md", "---\nstatus: idea\n---\n\n# Old idea\n")
        before = self.tree()
        child = self.hold(30, ".scratch/_brainstorming.lock")
        result = self.bs("migrate", "--write")
        self.assertEqual(result.code, 1, result)
        self.assertIn("Another Session is migrating the idea store right now (process %d). Nothing was written."
                      % child.pid, result.lines)
        self.assertEqual(self.tree(), before)


class JournalTest(BrainstormTest):
    """A write killed half way, staged from a real run's before and after
    bytes with the journal that run would have left."""

    JOURNAL = S + ".state/journal/20261020T000000-1-000001.json"

    def setUp(self):
        BrainstormTest.setUp(self)
        self.new("main-idea", "Main idea", "The whole thing.")
        self.new("part-one", "Part one", "The first half.", "--parent", "main-idea")
        self.base = self.box.path(S)

    def store_tree(self):
        """The store with its ledger, without the lock and the journal."""
        return {k: v for k, v in self.tree().items()
                if not k.startswith(".state/journal") and k != ".state/lock"}

    def put(self, rel, data):
        path = os.path.join(self.base, rel)
        if data is None:
            if os.path.exists(path):
                os.remove(path)
        else:
            with open(path, "wb") as handle:
                handle.write(data)

    def stage_close(self, done=0, ledger=False):
        """A part's close (two files: the part and its parent's History)
        killed after done files, and after the ledger when ledger is set.
        Returns the clean run's store and the ops."""
        before = self.store_tree()
        self.ok("set", "--idea", "part-one", "--status", "done", "--decision", "x", "--write")
        after = self.store_tree()
        ops = [{"path": name, "before": b64(before.get(name)), "after": b64(after.get(name))}
               for name in sorted(set(before) | set(after))
               if not name.startswith(".") and before.get(name) != after.get(name)]
        self.assertEqual([op["path"] for op in ops], ["main-idea.md", "part-one.md"])
        for name in set(before) | set(after):
            self.put(name, before.get(name))
        for op in ops[:done]:
            self.put(op["path"], after[op["path"]])
        if ledger:
            self.put(".state/ledger.json", after[".state/ledger.json"])
        self.journal(ops)
        return after, ops

    def journal(self, ops, dirs=(), **extra):
        data = dict({"label": "set part-one", "pid": 1, "ops": ops, "dirs": [list(d) for d in dirs]}, **extra)
        return self.box.write(self.JOURNAL, json.dumps(data))

    def journal_left(self):
        folder = self.box.path(S + ".state/journal")
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

    def test_start_finishes_a_write_killed_at_any_step(self):
        """Prevents a half-applied move the next command cannot finish (red
        team U3, F3, D6): killed after the journal, after one file, after both
        files or after the ledger, start rolls it forward to a clean run's
        store."""
        for done, ledger in ((0, False), (1, False), (2, False), (2, True)):
            with self.subTest(done=done, ledger=ledger):
                self.box.cleanup()
                self.setUp()
                after, _ = self.stage_close(done, ledger)
                result = self.ok("start")
                self.assertIn("An interrupted write (set part-one) was finished.", result.text)
                self.assertEqual(self.store_tree(), after)
                self.assertEqual(self.journal_left(), [])
                self.assertTrue(self.exists(".state/lock"))

    def test_a_file_edited_since_is_left_and_the_rest_rolled_back(self):
        """Prevents the roll-forward overwriting an edit made after the crash
        (red team F3): the edited file stays as it is, the other goes back to
        its before bytes, and the file is named. The ledger keeps the file's
        old hash, so the hand edit is stamped, never taken for the tool's
        own (spec 'last-updated and the ledger')."""
        self.stage_close(done=2)
        edited = self.read("part-one.md").replace("last-updated: %s" % TODAY, "last-updated: 2026-01-01")
        edited += "\nA hand note.\n"
        self.box.write(S + "part-one.md", edited)
        result = self.ok("set", "--idea", "main-idea", "--size", "large", "--write")
        self.assertIn("was rolled back: part-one.md changed since and was left as it is.", result.text)
        self.assertIn("last-updated set for ideas edited since the tool last wrote them: part-one.", result.text)
        self.assertIn("A hand note.", self.read("part-one.md"))
        self.assertIn("last-updated: %s" % TODAY, self.read("part-one.md"))
        self.assertNotIn("part part-one done", self.read("main-idea.md"))

    def test_a_created_file_edited_since_is_kept_and_told(self):
        """Prevents a silent duplicate after a killed move whose new file was
        edited before recovery (red team M10): the undo keeps the edited new
        file and a Tell line names it and the file the undo brought back."""
        old = self.box.read(S + "part-one.md").encode("utf-8")
        self.put("part-one.md", None)
        self.box.write(S + "renamed-one.md", "edited after the crash\n")
        self.journal([{"path": "part-one.md", "before": b64(old), "after": None},
                      {"path": "renamed-one.md", "before": None, "after": b64(b"the new file\n")}],
                     label="rename part-one to renamed-one")
        result = self.ok("start")
        self.assertIn("renamed-one.md changed since", result.text)
        tells = [t for t in result.tells() if "renamed-one.md" in t]
        self.assertTrue(tells, result)
        self.assertIn("which it had created, was edited since and is kept", tells[0])
        self.assertIn("the undo brought back part-one.md", tells[0])
        self.assertEqual(self.read("renamed-one.md"), "edited after the crash\n")
        self.assertEqual(self.read("part-one.md").encode("utf-8"), old)

    def test_a_refused_write_still_prints_the_recovery_it_did(self):
        """Prevents the recovery's Tell line lost for good when the write that
        settled the journal is then refused (finding 15): the refusal prints
        the recovery's lines first."""
        old = self.box.read(S + "part-one.md").encode("utf-8")
        self.put("part-one.md", None)
        self.box.write(S + "renamed-one.md", "edited after the crash\n")
        self.journal([{"path": "part-one.md", "before": b64(old), "after": None},
                      {"path": "renamed-one.md", "before": None, "after": b64(b"the new file\n")}],
                     label="rename part-one to renamed-one")
        result = self.bs("set", "--idea", "main-idea", "--status", "done", "--write")
        self.assertEqual(result.code, 1, result)
        self.assertTrue([t for t in result.tells() if "renamed-one.md" in t], result)
        self.assertIn("done needs --decision", result.text)
        self.assertEqual(self.journal_left(), [])

    def test_a_journal_naming_a_path_outside_the_store_is_set_aside(self):
        """Prevents recovery writing or moving outside the store from a
        crafted journal (red team M4): every path is checked before anything
        is touched; a journal that fails is set aside as .unreadable and
        named."""
        outside = os.path.join(self.box.root, "victim")
        os.makedirs(os.path.join(outside, "dir"))
        cases = [
            ([{"path": "../outside.md", "before": None, "after": b64(b"x\n")}], []),
            ([{"path": "../../../victim/file.md", "before": None, "after": b64(b"x\n")}], []),
            ([{"path": os.path.join(outside, "abs.md"), "before": None, "after": b64(b"x\n")}], []),
            ([{"path": ".state/ledger.json", "before": None, "after": b64(b"{}")}], []),
            ([], [("../../../victim/dir", "research/moved-in")]),
        ]
        try:
            os.makedirs(self.box.path(S + "research"))
            os.symlink(outside, self.box.path(S + "research", "escape"))
            cases.append(([], [("research/escape", "research/moved-in")]))
            cases.append(([], [("research/escape/dir", "research/moved-in")]))
        except (OSError, NotImplementedError):
            pass
        for ops, dirs in cases:
            with self.subTest(ops=ops, dirs=dirs):
                before = self.store_tree()
                self.journal(ops, dirs)
                result = self.ok("show", "--idea", "part-one")
                self.assertIn("was not used, because it names", result.text)
                self.assertIn(".unreadable", result.text)
                self.assertEqual(sorted(os.listdir(outside)), ["dir"])
                self.assertEqual(os.listdir(os.path.join(outside, "dir")), [])
                self.assertEqual(self.store_tree(), before)
                self.assertFalse(os.path.exists(os.path.join(self.box.root, "outside.md")))
                self.assertTrue(self.exists(".state/lock"))
                self.assertEqual([n for n in self.journal_left() if n.endswith(".json")], [])
                for name in self.journal_left():
                    os.remove(self.box.path(S + ".state/journal", name))

    @unittest.skipIf(WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "a read-only directory refuses a rename only for a non-root user on macOS and Linux")
    def test_a_refused_set_aside_names_both_files(self):
        """A refused rename named only its source, so the user could not tell
        where the file was going."""
        self.journal([{"path": "../outside.md", "before": None, "after": b64(b"x\n")}])
        folder = self.box.path(S + ".state/journal")
        os.chmod(folder, 0o555)
        self.addCleanup(os.chmod, folder, 0o755)
        result = self.bs("show", "--idea", "part-one")
        self.assertEqual(result.code, 1, result)
        journal = ".scratch/_brainstorming/.state/journal/20261020T000000-1-000001.json"
        self.assertIn("A file could not be read or written: %s, moving it to %s.unreadable: Permission denied"
                      % (journal, journal), result.lines)

    def test_a_journal_in_another_form_is_set_aside_without_a_crash(self):
        """Prevents a newer tool's journal crashing every command and leaking
        the lock (red team M8): it is set aside, naming the files it touches."""
        self.stage_close(done=1)
        with open(self.box.path(self.JOURNAL)) as handle:
            data = json.load(handle)
        data["dirs"] = [["research/a", "research/b", "move"]]
        self.box.write(self.JOURNAL, json.dumps(data))
        result = self.ok("start")
        self.assertIn("a folder move is not in the form this tool writes", result.text)
        self.assertIn("It names main-idea.md, part-one.md, which may be half written", result.text)
        self.assertTrue(self.exists(".state/lock"))
        self.assertEqual(self.bs("set", "--idea", "part-one", "--size", "large", "--write").code, 0)

    def test_a_live_writers_journal_is_left_to_it(self):
        """Prevents a read settling a move another Session is writing right
        now, and a read slowed by a writer: with the lock held by a live
        process, start reads at once and leaves the journal."""
        self.stage_close(done=1)
        hold(self, 30)
        started = time.monotonic()
        result = self.ok("start")
        # A run that waited out the 5 s takes at least that long.
        self.assertLess(time.monotonic() - started, 5)
        self.assertNotIn("interrupted write", result.text)
        self.assertEqual(len(self.journal_left()), 1)

    @unittest.skipIf(WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0), "POSIX permissions")
    def test_a_refused_write_leaves_no_journal_and_the_store_as_it_was(self):
        """Prevents a refused write leaving its journal for the next command
        to replay (red team F3): with the store folder read-only the journal
        is written, the idea file's write fails, and the save rolls back."""
        before = self.store_tree()
        store = self.box.path(S.rstrip("/"))
        os.chmod(store, stat.S_IRUSR | stat.S_IXUSR)
        try:
            result = self.bs("set", "--idea", "part-one", "--status", "done", "--decision", "x", "--write")
        finally:
            os.chmod(store, stat.S_IRWXU)
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertEqual(self.journal_left(), [])
        self.assertEqual(self.store_tree(), before)
        self.assertTrue(self.exists(".state/lock"))

    def test_leftover_temp_files_are_swept(self):
        """Prevents temp files a killed write left piling up (red team F14)."""
        self.box.write(S + "part-one.md.vdd-new-999", "half")
        self.box.write(S + ".state/ledger.json.vdd-new-999", "half")
        self.ok("set", "--idea", "part-one", "--size", "large", "--write")
        self.assertFalse(self.exists("part-one.md.vdd-new-999"))
        self.assertFalse(self.exists(".state/ledger.json.vdd-new-999"))


    def test_a_beta_journal_with_a_pid_settles_and_a_new_one_has_none(self):
        """Prevents an upgrade setting aside a pending write an earlier 0.16
        beta journaled with its pid (story 38), and a field nobody reads
        written again (story 39): the journal a rename writes, copied just
        before the tool removes it, holds no pid."""
        after, _ = self.stage_close(done=1)
        with open(self.box.path(self.JOURNAL)) as handle:
            self.assertIn("pid", json.load(handle))
        self.assertIn("An interrupted write (set part-one) was finished.", self.ok("start").text)
        self.assertEqual(self.store_tree(), after)
        out = self.box.path("journal-copy.json")
        proc = audited(self, "os.remove", os.path.join(".state", "journal") + os.sep, out,
                       "rename", "--idea", "part-one", "--to", "half-one", "--write")
        self.assertEqual(self.box.finish(proc).code, 0)
        with open(out) as handle:
            seen = json.load(handle)
        self.assertEqual(seen["label"], "rename part-one to half-one")
        self.assertEqual(sorted(seen), ["dirs", "label", "ops"])
