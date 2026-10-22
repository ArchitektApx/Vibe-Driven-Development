"""The test sandbox itself: what every other test stands on."""

import os
import stat
import json
import subprocess
import sys
import unittest
import warnings

from vddtest import PLAN_SIGNED, Sandbox, SceneTest


class CleanupTest(unittest.TestCase):
    def test_a_sandbox_with_read_only_git_objects_is_removed(self):
        """Prevents the Windows %TEMP% leak: git marks its objects read-only,
        Windows refuses to delete a read-only file, and every git-backed
        sandbox stayed behind. The removal raises no DeprecationWarning on
        Python 3.12 and later either."""
        box = Sandbox()
        try:
            box.init_git("main")
            box.commit("a.txt", "a\n", "feat: a")
            marked = box.write("read-only.txt", "x\n")
            os.chmod(marked, stat.S_IREAD)
            objects = [root for root, _, names in os.walk(os.path.join(box.proj, ".git", "objects")) if names]
            self.assertTrue(objects)
            # A read-only directory makes POSIX refuse the delete as well, so
            # the retry runs on every OS.
            os.chmod(objects[0], stat.S_IREAD | stat.S_IEXEC)
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                box.cleanup()
            self.assertFalse(os.path.exists(box.root))
        finally:
            if os.path.exists(box.root):
                for root, dirs, _ in os.walk(box.root):
                    for name in dirs:
                        os.chmod(os.path.join(root, name), stat.S_IRWXU)
                box.cleanup()


class CopiedSceneTest(SceneTest):
    """A scene staged once and copied per test, as the git-backed classes
    stage theirs."""

    def stage_scene(self):
        self.box.init_git("main")
        self.box.write(".gitignore", ".scratch/\n")
        self.box.git("add", ".gitignore")
        self.box.git("commit", "-q", "-m", "ignore")
        self.git("checkout", "-q", "-b", "demo")
        self.box.write_loop("demo", extra=(PLAN_SIGNED,))
        self.start = self.commit("a.txt", "a\n", "feat: a")
        self.where = self.box.root
        self.staged_by = type(self).__name__

    def test_the_copy_is_clean(self):
        """Prevents a copied scene whose index still holds the template's file
        stats: git would list every file as modified."""
        self.assertEqual(self.out("status", "--porcelain"), "")
        self.assertEqual(self.sha(), self.start)

    def test_nothing_in_the_copy_points_into_the_template(self):
        """Prevents a test that reads or writes another test's files through a
        path the template left behind."""
        template = SceneTest._scenes[type(self)][0].root
        self.assertNotEqual(template, self.box.root)
        self.assertEqual(self.where, self.box.root)
        for directory, _, names in os.walk(self.box.root):
            for name in names:
                with open(os.path.join(directory, name), "rb") as handle:
                    self.assertNotIn(template.encode("utf-8"), handle.read(), os.path.join(directory, name))

    def test_each_test_gets_its_own_copy(self):
        self.commit("b.txt", "b\n", "feat: b")
        self.assertNotEqual(self.sha(), self.start)


class OtherSceneTest(CopiedSceneTest):
    """A subclass stages a template of its own, keyed by its class."""

    def test_the_template_is_its_own(self):
        self.assertEqual(self.staged_by, "OtherSceneTest")


if __name__ == "__main__":
    unittest.main()
