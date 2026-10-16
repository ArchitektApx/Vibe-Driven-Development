"""Generic: a Harness VDD does not know. Nobody knows which stores it reads or
how the user types a skill name, so it searches every Harness's stores and
names skills bare."""

from . import Harness, get
from ..stores import PLUGIN_CACHE, cli_add, cli_update, union

OTHERS = ("claude-code", "codex", "cursor", "copilot-cli")


class Generic(Harness):
    name = "generic"
    label = ""

    def borrowed_skill(self, skill):
        return skill

    def vdd_skill(self, skill):
        return skill

    def present_roots(self, cwd):
        return union(get(name).present_roots(cwd) for name in OTHERS)

    def route_not_present(self):
        return [
            "Install Matt Pocock's collection: npx skills@latest add -g mattpocock/skills, selecting "
            "your agent when the installer asks."
        ]

    def route_present_not_resolvable(self, store):
        if store.kind == PLUGIN_CACHE:
            return get(store.owner).route_present_not_resolvable(store)
        return ["Re-run the install and select your agent: %s" % cli_add(store.scope)]

    def route_old_collection(self, store):
        if store is None:
            return None
        if store.kind == PLUGIN_CACHE:
            return get(store.owner).route_old_collection(store)
        return ["Update it: %s" % cli_update(store.scope)]

    def no_hit_continuation(self):
        return ""

    def fresh_coder(self):
        return (None, None)

    def codex_hook_steps(self):
        return False

    def orchestrator_launch(self):
        return "open a second Session in the same Harness and invoke vdd-orchestrator there"

    def wait_next(self, role, wait_command, paste_command):
        return (
            "If your tools can run a command in the background and wake you when it exits, run this that "
            "way, then end your turn: %s Otherwise ask the user to paste the next Doorbell here, and run "
            "with it: %s" % (wait_command, paste_command)
        )


HARNESS = Generic()
