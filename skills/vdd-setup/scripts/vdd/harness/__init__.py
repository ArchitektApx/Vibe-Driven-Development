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

    @abc.abstractmethod
    def present_roots(self, cwd):
        """The roots this Harness reads skills from, as stores.Root, in the
        current environment and on the current platform, with the relocation
        variables the Harness honours applied."""

    @abc.abstractmethod
    def route_not_present(self):
        """The lines that tell the user to install Matt Pocock's collection."""

    @abc.abstractmethod
    def route_present_not_resolvable(self, store):
        """The lines that get this Session to load a collection the search
        found in store (a stores.Store) and the Session cannot run."""

    @abc.abstractmethod
    def route_old_collection(self, store):
        """The lines that update a collection from before the glossary rename
        found in store, or None when store is None (no search hit)."""

    @abc.abstractmethod
    def no_hit_continuation(self):
        """Text that continues the "Resolvable from a store Setup does not
        search" line, or an empty string."""


def get(name):
    """The Harness --harness names, or None."""
    module = _MODULES.get(name)
    if module is None:
        return None
    return importlib.import_module("." + module, __name__).HARNESS


def all_harnesses():
    return [get(name) for name in NAMES]
