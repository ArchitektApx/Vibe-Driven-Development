"""The Harness subpackage: one module per Harness, each implementing the
interface below. Adding a Harness is one module here, its entry in every(),
one Harness file per skill that keeps them, and its tests."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any

from ..catalog.refusals import missing
from ..out import Failure

if TYPE_CHECKING:
    from ..stores import Root, Store


class Harness(abc.ABC):
    """The fixed interface every Harness module implements. Each module sets
    the three names below on its class; the Harness contract test fails a
    module that lacks one."""

    # The value --harness takes, and the slug a Harness file is named for.
    name: str
    # The Loop file's Harness: line.
    label: str
    # How a line the user reads names it.
    display_name: str

    @abc.abstractmethod
    def reports_subagent_tokens(self) -> bool:
        """Whether a subagent's completion notice reports its token count, so
        a Respawn policy can say "over <n>k"."""

    @abc.abstractmethod
    def picks_up_doorbell(self) -> bool:
        """Whether a new Orchestrator Session picks up the Planner's first
        Doorbell from the Doorbell file by itself."""

    @abc.abstractmethod
    def waits_through_stop_hook(self) -> bool:
        """Whether a wait arms a Stop hook that waits when the turn ends,
        instead of running in the background; Setup's Stop-hook steps apply
        to such a Harness."""

    @abc.abstractmethod
    def runs_sandboxed(self) -> bool:
        """Whether this process runs inside the Harness's sandbox, as the
        environment the sandbox sets says; False when the Harness sets
        nothing to tell."""

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
    def wait_next(self, wait_command: str, paste_command: str) -> str:
        """The Next: step that waits for the other Role's Doorbell: how to run
        wait_command on this Harness, or hand relay through paste_command."""


def every() -> tuple[Harness, ...]:
    """Every Harness, in the order the tool lists them, Generic last: the one
    list of Harnesses, which every other derives from. Plain relative
    imports: the static check refuses an import by a computed name."""
    from . import claude_code, codex, copilot_cli, cursor, generic
    return (claude_code.HARNESS, codex.HARNESS, cursor.HARNESS, copilot_cli.HARNESS, generic.HARNESS)


def get(name: str) -> Harness | None:
    """The Harness whose --harness value is name, or None."""
    for found in every():
        if found.name == name:
            return found
    return None


def known(name: str) -> Harness:
    """The Harness a name the tool itself holds names: one of every()'s, or a
    stores.Root's owner. Raises ValueError for any other name."""
    found = get(name)
    if found is None:
        raise ValueError("no Harness is named %s" % name)
    return found


def of_label(label: str) -> Harness:
    """The Harness a Loop file's Harness: line names, Generic for a label no
    Harness carries."""
    for found in every():
        if found.label == label:
            return found
    return every()[-1]


def folded(text: str) -> str:
    return "-".join(text.lower().split())


def from_option(values: dict[str, Any], usage: str) -> Harness:
    """The Harness the --harness option names, as its name or as the Loop
    file's Harness: line spells it, in any case and spacing. Refuses a
    missing or unknown one, naming usage."""
    given = values.get("harness")
    if given is None:
        raise missing(["harness"], usage)
    key = folded(given)
    for found in every():
        if key in (found.name, folded(found.label)):
            return found
    names = ", ".join(found.name for found in every())
    raise Failure(
        "Unknown Harness: %s. --harness takes one of: %s." % (given, names),
        "Run again with --harness set to one of: %s." % names,
    )
