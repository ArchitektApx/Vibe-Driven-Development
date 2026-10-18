"""Cursor, the IDE's Agent and the Cursor CLI alike."""

import os

from . import Harness
from .. import places
from ..stores import PLUGIN_CACHE, PROJECT, SKILL_STORE, USER, Root, cli_add, cli_update

NEW_CHAT = "open a new chat or a new agent Session"


class Cursor(Harness):
    name = "cursor"
    label = "Cursor"

    def borrowed_skill(self, skill):
        return "/" + skill

    def vdd_skill(self, skill):
        return "/" + skill

    def present_roots(self, cwd):
        # The IDE and the CLI read the same stores, and no variable moves
        # them. Every .claude and .codex store stays out: Cursor reads those
        # only through the IDE's third-party import, which the user can turn
        # off and the CLI ignores.
        home = places.home()
        return [
            Root(os.path.join(home, ".agents", "skills"), SKILL_STORE, USER, self.name),
            Root(os.path.join(cwd, ".agents", "skills"), SKILL_STORE, PROJECT, self.name),
            Root(os.path.join(home, ".cursor", "skills"), SKILL_STORE, USER, self.name),
            Root(os.path.join(cwd, ".cursor", "skills"), SKILL_STORE, PROJECT, self.name),
            Root(os.path.join(home, ".cursor", "plugins", "cache"), PLUGIN_CACHE, USER, self.name),
        ]

    def route_not_present(self):
        return [
            "Install Matt Pocock's collection: npx skills@latest add -g mattpocock/skills, selecting "
            "Cursor when the installer asks which agents to install for, then %s before you rerun %s."
            % (NEW_CHAT, self.vdd_skill("vdd-setup"))
        ]

    def route_present_not_resolvable(self, store):
        if store.kind == PLUGIN_CACHE:
            return [
                "Reinstall the plugin in the Cursor IDE's plugin UI, then %s. Cursor has no "
                "command-line route for this." % NEW_CHAT
            ]
        return [
            "First %s. If that still cannot run it, re-run the install and select Cursor: %s, then %s."
            % (NEW_CHAT, cli_add(store.scope), NEW_CHAT)
        ]

    def route_old_collection(self, store):
        if store is None:
            return None
        if store.kind == PLUGIN_CACHE:
            return ["Update it: refresh the plugin in the Cursor IDE's plugin UI."]
        return ["Update it: %s" % cli_update(store.scope)]

    def no_hit_continuation(self):
        return (
            "This is likely Claude Code's or Codex's store, read through Cursor's third-party "
            "import, which the IDE setting can turn off. A skills-CLI install that selects Cursor "
            "does not depend on it."
        )

    def respawn_recommendation(self):
        return ("every round", None)

    def codex_hook_steps(self):
        return False

    def orchestrator_launch(self, slug):
        return (
            "in the Cursor IDE, open a new chat and type /vdd-orchestrator %s in it; in the Cursor CLI, run "
            "agent in a terminal in this repository, then /vdd-orchestrator %s in that Session" % (slug, slug)
        )

    def wait_next(self, role, wait_command, paste_command):
        return "Run this as a background shell, then end your turn: %s" % wait_command


HARNESS = Cursor()
