"""The idea store's safety, driven from outside: the write lock, the
journal with its recovery and validation, the ledger, and killed runs staged
as a leftover journal and lock."""

import json
import os
import stat
import subprocess
import sys
import time
import unittest

from test_brainstorm import S, TODAY, BrainstormTest
from vddtest import ENTRY, WINDOWS, b64


class LockTest(BrainstormTest):
    def setUp(self):
        BrainstormTest.setUp(self)
        self.new("main-idea", "Main idea", "The whole thing.")
        self.new("part-one", "Part one", "The first half.", "--parent", "main-idea")

    def lock(self, text, age=None):
        path = self.box.write(S + ".state/lock", text)
        if age is not None:
            then = time.time() - age
            os.utime(path, (then, then))
        return path

    def set_size(self):
        return self.bs("set", "--idea", "part-one", "--size", "large", "--write")

    def test_a_dead_writers_lock_is_taken_over_at_once(self):
        """Prevents the false 'another Session is writing' after a killed
        write (red team M9, U13): a fresh lock whose process is gone is taken
        over without waiting, and the write lands."""
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        self.lock("%d 0123abcd" % dead.pid)
        result = self.set_size()
        self.assertEqual(result.code, 0, result)
        self.assertNotIn("Another Session", result.text)
        self.assertIn("size: large", self.read("part-one.md"))
        self.assertFalse(self.exists(".state/lock"))

    def test_a_live_writers_lock_is_never_taken_over_however_old(self):
        """Prevents a stalled live writer losing the lock to age (red team M1,
        a laptop put to sleep mid-write): its lock refuses, names the running
        process, and keeps refusing past 30 s."""
        path = self.lock("%d" % os.getpid(), age=3600)
        before = self.ideas_tree()
        result = self.set_size()
        self.assertEqual(result.code, 1, result)
        self.assertIn("Another Session is writing to the idea store right now: process %d, still running"
                      % os.getpid(), result.text)
        self.assertIn("they can delete that file", result.last)
        self.assertEqual(self.ideas_tree(), before)
        self.assertTrue(os.path.exists(path))

    def test_another_machines_lock_falls_back_to_age(self):
        """Prevents judging another machine's pid (a shared folder) by this
        machine's processes, and a refusal that claims a Session is writing
        (spec story 51): refused while young as 'cannot be checked from
        here', taken over past 30 s."""
        self.lock("%d tok elsewhere-host" % os.getpid())
        result = self.set_size()
        self.assertEqual(result.code, 1, result)
        self.assertIn("cannot be checked from here", result.text)
        self.assertNotIn("still running", result.text)
        self.assertNotIn("Another Session", result.text)
        self.lock("%d tok elsewhere-host" % os.getpid(), age=31)
        result = self.set_size()
        self.assertEqual(result.code, 0, result)
        self.assertFalse(self.exists(".state/lock"))

    def test_an_empty_lock_is_taken_over_after_the_short_wait(self):
        """Prevents a lock left empty by a run killed between creating it and
        writing its pid from refusing every write."""
        self.lock("")
        started = time.monotonic()
        result = self.set_size()
        self.assertEqual(result.code, 0, result)
        self.assertLess(time.monotonic() - started, 20)
        self.assertFalse(self.exists(".state/lock"))

    def test_a_writer_whose_lock_was_taken_over_writes_nothing_more(self):
        """Prevents a stalled writer overwriting the Session that took its
        lock (red team M1, spec story 52): with the pause seam the test
        rewrites the lock's token mid-run; the writer stops, says another
        Session took over, and leaves the store and the new lock as they
        are."""
        before = self.ideas_tree()
        env = self.box.env(VDD_TODAY=TODAY, VDD_SAVE_PAUSE_SECONDS="4")
        proc = subprocess.Popen([sys.executable, ENTRY, "brainstorm", "set", "--idea", "part-one", "--status",
                                 "done", "--decision", "x", "--write"], cwd=self.box.proj, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        lock = self.box.path(S + ".state/lock")
        deadline = time.monotonic() + 30
        while not os.path.exists(lock) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(os.path.exists(lock))
        token = "%d other-token %s" % (os.getpid(), "elsewhere-host")
        with open(lock, "w") as handle:
            handle.write(token)
        out = self.box.finish(proc, timeout=60).text
        self.assertNotEqual(proc.returncode, 0, out)
        self.assertIn("another Session took over", out)
        self.assertTrue(out.rstrip("\n").split("\n")[-1].startswith("Next: "), out)
        self.assertEqual(self.ideas_tree(), before)
        self.assertEqual(self.read(".state/lock"), token)

    def test_no_lock_is_left_behind(self):
        """Prevents a lock leaked by a command that held it to the end,
        refused or not."""
        self.assertEqual(self.set_size().code, 0)
        self.assertEqual(self.bs("set", "--idea", "part-one", "--status", "done", "--write").code, 1)
        self.assertFalse(self.exists(".state/lock"))


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
                self.assertFalse(self.exists(".state/lock"))

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
                self.assertFalse(self.exists(".state/lock"))
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
        self.assertFalse(self.exists(".state/lock"))
        self.assertEqual(self.bs("set", "--idea", "part-one", "--size", "large", "--write").code, 0)

    def test_a_live_writers_journal_is_left_to_it(self):
        """Prevents a read settling a move another Session is writing right
        now: with the lock held by a live process, start leaves the journal."""
        self.stage_close(done=1)
        self.box.write(S + ".state/lock", "%d" % os.getpid())
        result = self.ok("start")
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
        self.assertFalse(self.exists(".state/lock"))

    def test_leftover_temp_files_are_swept(self):
        """Prevents temp files a killed write left piling up (red team F14)."""
        self.box.write(S + "part-one.md.vdd-new-999", "half")
        self.box.write(S + ".state/ledger.json.vdd-new-999", "half")
        self.ok("set", "--idea", "part-one", "--size", "large", "--write")
        self.assertFalse(self.exists("part-one.md.vdd-new-999"))
        self.assertFalse(self.exists(".state/ledger.json.vdd-new-999"))

