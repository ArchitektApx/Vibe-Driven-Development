"""The parallel runner, tests/run.py, as a process on a staged test
directory."""

import os
import subprocess
import sys
import unittest

from vddtest import ToolTest

RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.py")

PASSING = """import unittest


class Passing(unittest.TestCase):
    def test_one(self):
        print("PASSING CLASS OUTPUT")

    def test_two(self):
        pass
"""

FAILING = """import unittest


class Failing(unittest.TestCase):
    def test_it_fails(self):
        self.assertEqual(1, 2, "THE FAILURE'S OWN MESSAGE")
"""


class RunnerTest(ToolTest):
    def test_a_failing_class_fails_the_run_with_its_whole_output(self):
        """Prevents a parallel run that hides a failure: the runner exits
        non-zero, prints the failing class's output whole and leaves no
        bytecode prefix behind."""
        start = os.path.join(self.box.root, "suite")
        self.box.write("test_pass.py", PASSING, base=start)
        self.box.write("test_fail.py", FAILING, base=start)
        temp = os.path.join(self.box.root, "tmp")
        os.makedirs(temp)
        env = self.box.env(TMPDIR=temp, TEMP=temp, TMP=temp, VDD_TEST_PYCACHE=None)
        proc = subprocess.run([sys.executable, "-B", RUNNER, "-s", start], env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=300)
        out = proc.stdout.decode("utf-8", "replace")
        self.assertNotEqual(proc.returncode, 0, out)
        self.assertIn("FAILED CLASS: test_fail.Failing", out)
        self.assertIn("THE FAILURE'S OWN MESSAGE", out)
        self.assertIn("Traceback", out)
        self.assertNotIn("FAILED CLASS: test_pass.Passing", out)
        self.assertIn("Ran 3 tests in 2 classes", out)
        self.assertIn("1 failures, 0 errors", out)
        self.assertEqual([name for name in os.listdir(temp) if name.startswith("vdd-pycache-")], [])

    def test_a_passing_run_exits_zero(self):
        start = os.path.join(self.box.root, "suite")
        self.box.write("test_pass.py", PASSING, base=start)
        temp = os.path.join(self.box.root, "tmp")
        os.makedirs(temp)
        env = self.box.env(TMPDIR=temp, TEMP=temp, TMP=temp, VDD_TEST_PYCACHE=None)
        proc = subprocess.run([sys.executable, "-B", RUNNER, "-s", start], env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=300)
        out = proc.stdout.decode("utf-8", "replace")
        self.assertEqual(proc.returncode, 0, out)
        self.assertTrue(out.endswith("OK\n"), out)
        self.assertNotIn("PASSING CLASS OUTPUT", out)


if __name__ == "__main__":
    unittest.main()
