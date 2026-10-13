"""The Harness subpackage: one module per Harness, each implementing the
interface below. Adding a Harness is one module here, one Harness file per
skill that keeps them, and its tests."""

import abc
import importlib

NAMES = ("claude-code", "codex", "cursor", "copilot-cli", "generic")

_MODULES = {
    "claude-code": "claude_code",
    "codex": "codex",
    "cursor": "cursor",
    "copilot-cli": "copilot_cli",
    "generic": "generic",
}


class Harness(abc.ABC):
    """The fixed interface every Harness module implements."""

    # The value --harness takes, and the label LOOP.md's Harness: line holds.
    name = ""
    label = ""

    @abc.abstractmethod
    def borrowed_skill(self, skill):
        """The form the user types to invoke a Borrowed skill."""

    @abc.abstractmethod
    def vdd_skill(self, skill):
        """The form the user types to invoke a VDD skill, such as vdd-setup."""


def get(name):
    """The Harness --harness names, or None."""
    module = _MODULES.get(name)
    if module is None:
        return None
    return importlib.import_module("." + module, __name__).HARNESS


def all_harnesses():
    return [get(name) for name in NAMES]
