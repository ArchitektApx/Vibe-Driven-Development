"""The Harness subpackage: one module per Harness, each implementing the
interface below. Adding a Harness is one module here, one Harness file per
skill that keeps them, and its tests."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..stores import Root, Store

NAMES = ("claude-code", "codex", "cursor", "copilot-cli", "generic")


class Harness(abc.ABC):
    """The fixed interface every Harness module implements."""

    # The value --harness takes, and the label the Loop file's Harness: line holds.
    name = ""
    label = ""

    @abc.abstractmethod
    def borrowed_skill(self, skill: str) -> str:
        """The form the user types to invoke a Borrowed skill."""

    @abc.abstractmethod
    def vdd_skill(self, skill: str) -> str:
        """The form the user types to invoke a VDD skill, such as vdd-setup."""

    @abc.abstractmethod
    def present_roots(self, cwd: str) -> list[Root]:
        """The roots this Harness reads skills from, as stores.Root, in the
        current environment and on the current platform, with the relocation
        variables the Harness honours applied."""

    @abc.abstractmethod
    def route_not_present(self) -> list[str]:
        """The lines that tell the user to install Matt Pocock's collection."""

    @abc.abstractmethod
    def route_present_not_resolvable(self, store: Store) -> list[str]:
        """The lines that get this Session to load a collection the search
        found in store (a stores.Store) and the Session cannot run."""

    @abc.abstractmethod
    def route_old_collection(self, store: Store | None) -> list[str] | None:
        """The lines that update a collection from before the glossary rename
        found in store, or None when store is None (no search hit)."""

    @abc.abstractmethod
    def no_hit_continuation(self) -> str:
        """Text that continues the "Resolvable from a store Setup does not
        search" line, or an empty string."""

    @abc.abstractmethod
    def orchestrator_launch(self, slug: str) -> str:
        """How the user starts the Orchestrator's Session for the loop slug,
        as one clause."""

    @abc.abstractmethod
    def respawn_recommendation(self) -> tuple[str | None, str | None]:
        """The Respawn question for the Coder's Respawn policy on this
        Harness, asked at Model approval: (the answer it recommends, the
        "over <n>k" limit it offers as an example), each None for none. Only
        a Harness that reports a subagent's token count offers a limit."""

    @abc.abstractmethod
    def codex_hook_steps(self) -> bool:
        """Whether Setup's Codex hook steps (the hooks.json migration and the
        trust check) apply."""

    @abc.abstractmethod
    def wait_next(self, role: str, wait_command: str, paste_command: str) -> str:
        """The Next: step that waits for the other Role's Doorbell: how to run
        wait_command on this Harness, or hand relay through paste_command."""


def get(name: str) -> Harness | None:
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


def known(name: str) -> Harness:
    """The Harness a name the tool itself holds names: one of NAMES, or a
    stores.Root's owner. Raises ValueError for any other name."""
    found = get(name)
    if found is None:
        raise ValueError("no Harness is named %s" % name)
    return found
