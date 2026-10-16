"""The Harness subpackage: one module per Harness, each implementing the
interface below. Adding a Harness is one module here, one Harness file per
skill that keeps them, and its tests."""

import abc

NAMES = ("claude-code", "codex", "cursor", "copilot-cli", "generic")


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

    @abc.abstractmethod
    def orchestrator_launch(self):
        """How the user starts the Orchestrator's Session, as one clause."""

    @abc.abstractmethod
    def fresh_coder(self):
        """The Fresh Coder question on this Harness: (the answer it
        recommends, the limit it offers as "over <n>k"), each None for none."""

    @abc.abstractmethod
    def codex_hook_steps(self):
        """Whether Setup's Codex hook steps (the hooks.json migration and the
        trust check) apply."""

    @abc.abstractmethod
    def wait_next(self, role, wait_command, paste_command):
        """The Next: step that waits for the other Role's Doorbell: how to run
        wait_command on this Harness, or hand relay through paste_command."""


def get(name):
    """The Harness --harness names, or None. Plain relative imports: the
    static check refuses an import by a computed name."""
    if name == "claude-code":
        from . import claude_code as module
    elif name == "codex":
        from . import codex as module
    elif name == "cursor":
        from . import cursor as module
    elif name == "copilot-cli":
        from . import copilot_cli as module
    elif name == "generic":
        from . import generic as module
    else:
        return None
    return module.HARNESS


def all_harnesses():
    return [get(name) for name in NAMES]
