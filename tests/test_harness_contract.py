"""Every Harness module implements the whole interface."""

import abc
import inspect
import sys
import unittest

from vddtest import SCRIPTS

sys.path.insert(0, SCRIPTS)
sys.dont_write_bytecode = True

from vdd import harness  # noqa: E402

CAPABILITIES = ("reports_subagent_tokens", "picks_up_doorbell", "waits_through_stop_hook")
NAMES = ("name", "label", "display_name")


def interface():
    return sorted(
        name
        for name, member in vars(harness.Harness).items()
        if getattr(member, "__isabstractmethod__", False)
    )


def own(cls, member):
    """Whether cls or a class between it and the interface defines member."""
    return any(member in vars(klass) for klass in cls.__mro__[:-1] if klass is not harness.Harness)


def lacks(cls):
    """What a Harness class leaves out of the interface: a method, or one of
    the names it must carry, as a non-empty string of its own."""
    missing = [method for method in interface() if not own(cls, method)]
    missing += [name for name in NAMES if not (own(cls, name) and isinstance(getattr(cls, name), str)
                                               and getattr(cls, name))]
    if not missing and inspect.isabstract(cls):
        missing.append("a concrete class")
    return missing


def without(cls, member):
    """A copy of a Harness class with member left out."""
    namespace = {key: value for key, value in vars(cls).items()
                 if key != member and key not in ("__dict__", "__weakref__")}
    return abc.ABCMeta(cls.__name__ + "Lacking", (harness.Harness,), namespace)


class HarnessContractTest(unittest.TestCase):
    def test_the_interface_is_not_empty(self):
        self.assertTrue(interface())

    def test_five_harnesses_generic_last(self):
        self.assertEqual(
            [found.name for found in harness.every()], ["claude-code", "codex", "cursor", "copilot-cli", "generic"]
        )

    def test_every_harness_implements_every_method(self):
        for found in harness.every():
            with self.subTest(harness=found.name):
                self.assertIsInstance(found, harness.Harness)
                self.assertIs(harness.known(found.name), found)
                self.assertEqual(lacks(type(found)), [])
                for method in interface():
                    self.assertTrue(callable(getattr(found, method)))

    def test_the_capabilities_have_no_default(self):
        """A name check outside the Harness modules became a capability, and
        a capability with a default would let a new Harness take it without
        deciding it."""
        for capability in CAPABILITIES:
            self.assertIn(capability, interface())
        self.assertNotIn("codex_hook_steps", interface())

    def test_a_harness_lacking_a_capability_or_a_name_fails(self):
        """The check above would pass a module that forgot a capability, its
        label or its user-facing name, if it only looked at the five that
        carry them all."""
        for found in harness.every():
            for member in CAPABILITIES + NAMES:
                with self.subTest(harness=found.name, lacking=member):
                    self.assertIn(member, lacks(without(type(found), member)))

    def test_the_capabilities_per_harness(self):
        expected = {
            "claude-code": (True, True, False),
            "codex": (False, True, True),
            "cursor": (False, True, False),
            "copilot-cli": (False, True, False),
            "generic": (False, False, False),
        }
        for found in harness.every():
            with self.subTest(harness=found.name):
                self.assertEqual(tuple(getattr(found, name)() for name in CAPABILITIES), expected[found.name])

    def test_labels_and_user_facing_names(self):
        """Generic's label is the Loop file's "Generic", and lines for the
        user call it "your agent"; every other Harness has one spelling."""
        expected = {
            "claude-code": ("Claude Code", "Claude Code"),
            "codex": ("Codex", "Codex"),
            "cursor": ("Cursor", "Cursor"),
            "copilot-cli": ("Copilot CLI", "Copilot CLI"),
            "generic": ("Generic", "your agent"),
        }
        for found in harness.every():
            with self.subTest(harness=found.name):
                self.assertEqual((found.label, found.display_name), expected[found.name])
                self.assertIs(harness.of_label(found.label), found)

    def test_the_respawn_recommendation_replaced_the_fresh_coder_hook(self):
        """The Fresh Coder hook became the Respawn recommendation. Only Claude
        Code, which reports subagent_tokens, offers a limit."""
        self.assertIn("respawn_recommendation", interface())
        self.assertNotIn("fresh_coder", interface())
        expected = {
            "claude-code": ("every round", "over 200k"),
            "codex": ("never", None),
            "cursor": ("every round", None),
            "copilot-cli": ("every round", None),
            "generic": (None, None),
        }
        for name, pair in expected.items():
            with self.subTest(harness=name):
                self.assertEqual(harness.known(name).respawn_recommendation(), pair)
                self.assertEqual(pair[1] is not None, harness.known(name).reports_subagent_tokens())

    def test_unknown_name(self):
        self.assertIsNone(harness.get("nonsense"))
        self.assertIs(harness.of_label("nonsense"), harness.known("generic"))


if __name__ == "__main__":
    unittest.main()
