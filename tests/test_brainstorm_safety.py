"""The idea store's safety, driven from outside: the write lock, the
journal with its recovery and validation, the ledger, and killed runs staged
as a leftover journal and lock."""

import os
import subprocess
import sys
import time

from test_brainstorm import S, TODAY, BrainstormTest
from vddtest import ENTRY


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
        out = proc.communicate(timeout=60)[0].decode("utf-8")
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
