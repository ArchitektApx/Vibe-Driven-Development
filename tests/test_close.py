"""Closing a loop, driven through vdd.py: every closer deletes the Codex
armed files, and pr open prints what it already did before a late
failure."""

import os
import stat
import unittest

from scenes import CC, CODEX_ID, PR_URL, SLUG, Staged
from vddtest import WINDOWS

ARMED = "codex-armed-" + CODEX_ID


class Closers(Staged):
    def armed(self):
        self.put(ARMED, "vdd codex-armed 1\nOrchestrator 0\n")
        self.put("codex-claim-" + CODEX_ID, "")

    def assertDeleted(self, result, directory="demo"):
        self.assertEqual(result.code, 0, result)
        self.assertIn("Deleted the Codex armed file %s." % ARMED, result.lines)
        left = os.listdir(self.box.path(".scratch", directory))
        self.assertNotIn(ARMED, left)
        self.assertNotIn("codex-claim-" + CODEX_ID, left)

    def test_loop_close(self):
        """Prevents loop close leaving the Codex Stop hook armed on a closed
        loop."""
        self.plan()
        self.armed()
        result = self.run_ok("loop", "close", *SLUG, "--write")
        self.assertDeleted(result)
        self.assertIn("Closed: the loop demo. Its files stay in .scratch/demo/ as the record.", result.lines)

    def test_loop_aside(self):
        """Prevents loop aside leaving the Codex Stop hook armed on the loop
        it closes, and keeps its own Closed line."""
        self.plan()
        self.armed()
        result = self.run_ok("loop", "aside", *SLUG, "--write")
        self.assertDeleted(result, "demo-2")
        self.assertIn("Closed the loop demo.", result.lines)

    @unittest.skipIf(WINDOWS, "the gh fake is a POSIX script")
    def test_pr_open(self):
        """Prevents pr open leaving the Codex Stop hook armed on the loop it
        closes."""
        self.pr_open_open()
        self.armed()
        result = self.box.run("pr", "open", "--path", "open", *SLUG, *CC, "--write", env=self.env(self.gh_on_path()))
        self.assertDeleted(result)
        self.assertIn("Closed: the loop demo. Its files stay in .scratch/demo/ as the record.", result.lines)


class LinesAlreadyDone(Staged):
    @unittest.skipIf(WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "the gh fake is a POSIX script, and the state file's permission a POSIX bit")
    def test_a_failed_close_still_names_the_push_and_the_pr(self):
        """Prevents pr open hiding that it pushed and opened the PR when
        closing the loop fails after both."""
        self.pr_open_open()
        path = self.box.path(self.rel("loop-state"))
        os.chmod(path, stat.S_IREAD)
        self.addCleanup(os.chmod, path, stat.S_IWRITE | stat.S_IREAD)
        result = self.box.run("pr", "open", "--path", "open", *SLUG, *CC, "--write", env=self.env(self.gh_on_path()))
        self.assertEqual(result.code, 1, result)
        self.assertEqual(result.lines[:3], [
            "Pushed demo to origin.",
            'Tell the user verbatim: "Opened the PR: %s"' % PR_URL,
            result.lines[2]])
        self.assertTrue(result.lines[2].startswith("Could not close the loop demo: "), result)
        self.assertNext(result, "could not be closed")


if __name__ == "__main__":
    unittest.main()
