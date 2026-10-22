"""The test sandbox itself: what every other test stands on."""

import os
import stat
import unittest
import warnings

from vddtest import Sandbox


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


if __name__ == "__main__":
    unittest.main()
