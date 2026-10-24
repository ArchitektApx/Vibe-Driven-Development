"""Generic: a Harness VDD does not know. Nobody knows which stores it reads or
how the user types a skill name, so it searches every Harness's stores and
names skills bare."""

from __future__ import annotations

from . import Harness, every, known
from ..out import RELAY_HELD
from ..stores import PLUGIN_CACHE, Root, Store, cli_add, cli_update, union


class Generic(Harness):
    name = "generic"
    label = "Generic"
    display_name = "your agent"

    def borrowed_skill(self, skill: str) -> str:
        return skill

    def vdd_skill(self, skill: str) -> str:
        return skill

    def present_roots(self, cwd: str) -> list[Root]:
        return union(other.present_roots(cwd) for other in every() if other is not self)

    def route_not_present(self) -> list[str]:
        return [
            "Install Matt Pocock's collection: npx skills@latest add -g mattpocock/skills, selecting "
            "your agent when the installer asks."
        ]

    def route_present_not_resolvable(self, store: Store) -> list[str]:
        if store.kind == PLUGIN_CACHE:
            return known(store.owner).route_present_not_resolvable(store)
        return ["Re-run the install and select your agent: %s" % cli_add(store.scope)]

    def route_old_collection(self, store: Store | None) -> list[str] | None:
        if store is None:
            return None
        if store.kind == PLUGIN_CACHE:
            return known(store.owner).route_old_collection(store)
        return ["Update it: %s" % cli_update(store.scope)]

    def no_hit_continuation(self) -> str:
        return ""

    def respawn_recommendation(self) -> tuple[str | None, str | None]:
        return (None, None)

    def reports_subagent_tokens(self) -> bool:
        return False

    def picks_up_doorbell(self) -> bool:
        return False

    def runs_sandboxed(self) -> bool:
        return False

    def waits_through_stop_hook(self) -> bool:
        return False

    def orchestrator_launch(self, slug: str) -> str:
        return (
            "open a second Session in the same Harness, invoke vdd-orchestrator there and give it the slug %s"
            % slug
        )

    def wait_next(self, wait_command: str, paste_command: str) -> str:
        return (
            "If your tools can run a command in the background and wake you when it exits, run this that "
            "way, then end your turn: %s Otherwise ask the user to paste the next Doorbell here, and run "
            "with it: %s" % (wait_command, paste_command)
        )

    def relayed_wait_next(self, wait_command: str, paste_command: str) -> str:
        return (
            "If your tools can run a command in the background and wake you when it exits, run this that way "
            "before you write anything to the user: %s Then end your turn with a reply that %s. Otherwise "
            "relay every Tell the user verbatim line above unchanged, then ask the user to paste the next "
            "Doorbell here, and run with it: %s" % (wait_command, RELAY_HELD, paste_command)
        )


HARNESS = Generic()
