"""Codex."""

import os

from . import Harness
from .. import places
from ..stores import PLUGIN_CACHE, PROJECT, SKILL_STORE, USER, Root, cli_add, cli_update, env

NEW_SESSION = "start a new Codex Session: a skill added while a Session runs appears only in a new one"


class Codex(Harness):
    name = "codex"
    label = "Codex"

    def borrowed_skill(self, skill):
        return "$" + skill

    def vdd_skill(self, skill):
        return "$vdd:" + skill

    def present_roots(self, cwd):
        # The skills-CLI stores, Codex's own skill stores (still read,
        # deprecated) and its plugin cache, the last two moved by CODEX_HOME.
        home = places.home()
        codex = env("CODEX_HOME") or os.path.join(home, ".codex")
        return [
            Root(os.path.join(home, ".agents", "skills"), SKILL_STORE, USER, self.name),
            Root(os.path.join(cwd, ".agents", "skills"), SKILL_STORE, PROJECT, self.name),
            Root(os.path.join(codex, "skills"), SKILL_STORE, USER, self.name),
            Root(os.path.join(cwd, ".codex", "skills"), SKILL_STORE, PROJECT, self.name),
            Root(os.path.join(codex, "plugins", "cache"), PLUGIN_CACHE, USER, self.name),
        ]

    def route_not_present(self):
        return [
            "Install Matt Pocock's collection: npx skills@latest add -g mattpocock/skills, selecting "
            "Codex when the installer asks which agents to install for, then %s. Rerun %s there."
            % (NEW_SESSION, self.vdd_skill("vdd-setup"))
        ]

    def route_present_not_resolvable(self, store):
        if store.kind == PLUGIN_CACHE:
            return [
                "Run codex plugin add %s@%s, then start a new Codex Session and rerun %s there."
                % (store.second, store.first, self.vdd_skill("vdd-setup"))
            ]
        return [
            "First %s. If the new Session still cannot run it, re-run the install and select Codex: "
            "%s, then start a new Codex Session and rerun %s there."
            % (NEW_SESSION, cli_add(store.scope), self.vdd_skill("vdd-setup"))
        ]

    def route_old_collection(self, store):
        if store is None:
            return None
        if store.kind == PLUGIN_CACHE:
            return [
                "Update it: codex plugin marketplace upgrade %s, then codex plugin add %s@%s, then "
                "start a new Codex Session." % (store.first, store.second, store.first)
            ]
        return ["Update it: %s, then start a new Codex Session." % cli_update(store.scope)]

    def no_hit_continuation(self):
        return ""

    def codex_hook_steps(self):
        return True

    def orchestrator_launch(self):
        return "run codex --no-daemon in a terminal in this repository, then $vdd:vdd-orchestrator in that Session"

    def wait_next(self, role, wait_command, paste_command):
        return "Run this, which arms the Stop hook, then end your turn: %s" % wait_command


HARNESS = Codex()
