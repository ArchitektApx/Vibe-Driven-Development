"""Seam 2: every Harness module implements the whole interface."""

import inspect
import sys
import unittest

from vddtest import SCRIPTS

sys.path.insert(0, SCRIPTS)
sys.dont_write_bytecode = True

from vdd import harness  # noqa: E402


class HarnessContractTest(unittest.TestCase):
    def interface(self):
        return sorted(
            name
            for name, member in vars(harness.Harness).items()
            if getattr(member, "__isabstractmethod__", False)
        )

    def test_the_interface_is_not_empty(self):
        self.assertTrue(self.interface())

    def test_five_harnesses(self):
        self.assertEqual(
            list(harness.NAMES), ["claude-code", "codex", "cursor", "copilot-cli", "generic"]
        )

    def test_every_harness_implements_every_method(self):
        for name in harness.NAMES:
            with self.subTest(harness=name):
                found = harness.get(name)
                self.assertIsInstance(found, harness.Harness)
                self.assertEqual(found.name, name)
                cls = type(found)
                for method in self.interface():
                    own = any(method in vars(klass) for klass in cls.__mro__[:-1] if klass is not harness.Harness)
                    self.assertTrue(own, "%s lacks %s" % (name, method))
                    self.assertTrue(callable(getattr(found, method)))
                self.assertFalse(inspect.isabstract(cls))

    def test_unknown_name(self):
        self.assertIsNone(harness.get("nonsense"))


if __name__ == "__main__":
    unittest.main()
