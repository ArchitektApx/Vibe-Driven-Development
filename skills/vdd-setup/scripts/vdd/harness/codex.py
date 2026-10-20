"""Codex."""

from __future__ import annotations

import os

from . import Harness
from .. import places
from ..stores import PLUGIN_CACHE, PROJECT, SKILL_STORE, USER, Root, Store, cli_add, cli_update, env

NEW_SESSION = "start a new Codex Session: a skill added while a Session runs appears only in a new one"


class Codex(Harness):
    name = "codex"
    label = "Codex"

    def borrowed_skill(self, skill: str) -> str:
        return "$" + skill

    def vdd_skill(self, skill: str) -> str:
        return "$vdd:" + skill

    def present_roots(self, cwd: str) -> list[Root]:
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

    def route_not_present(self) -> list[str]:
        return [
            "Install Matt Pocock's collection: npx skills@latest add -g mattpocock/skills, selecting "
            "Codex when the installer asks which agents to install for, then %s. Rerun %s there."
            % (NEW_SESSION, self.vdd_skill("vdd-setup"))
        ]

    def route_present_not_resolvable(self, store: Store) -> list[str]:
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

    def route_old_collection(self, store: Store | None) -> list[str] | None:
        if store is None:
            return None
        if store.kind == PLUGIN_CACHE:
            return [
                "Update it: codex plugin marketplace upgrade %s, then codex plugin add %s@%s, then "
                "start a new Codex Session." % (store.first, store.second, store.first)
            ]
        return ["Update it: %s, then start a new Codex Session." % cli_update(store.scope)]

    def no_hit_continuation(self) -> str:
        return ""

    def respawn_recommendation(self) -> tuple[str | None, str | None]:
        return ("never", None)

    def codex_hook_steps(self) -> bool:
        return True

    def orchestrator_launch(self, slug: str) -> str:
        return (
            "run codex --no-daemon in a terminal in this repository, then $vdd:vdd-orchestrator %s in that Session"
            % slug
        )

    def wait_next(self, role: str, wait_command: str, paste_command: str) -> str:
        return "Run this, which arms the Stop hook, then end your turn: %s" % wait_command


HARNESS = Codex()
