"""Copilot CLI."""

import os

from . import Harness
from .. import places
from ..stores import PLUGIN_CACHE, PROJECT, SKILL_STORE, USER, Root, cli_add, cli_update, env

RELOAD = "/skills reload or a new copilot Session"


def agents_store_line():
    """With COPILOT_HOME set, Copilot CLI does not read ~/.agents/skills, which
    the skills CLI's -g writes, so the store is added by hand. The path goes
    in expanded: PowerShell does not expand ~ for a program it runs."""
    if not env("COPILOT_HOME"):
        return ""
    path = os.path.join(places.home(), ".agents", "skills")
    return (
        " Then run copilot skill add '%s': Copilot CLI does not read that store while "
        "COPILOT_HOME is set." % path
    )


class CopilotCli(Harness):
    name = "copilot-cli"
    label = "Copilot CLI"

    def borrowed_skill(self, skill):
        return "/" + skill

    def vdd_skill(self, skill):
        return "/vdd:" + skill

    def present_roots(self, cwd):
        # Copilot's own store and plugin directory move with COPILOT_HOME,
        # and it reads ~/.agents/skills only while COPILOT_HOME is unset.
        home = places.home()
        copilot = env("COPILOT_HOME") or os.path.join(home, ".copilot")
        roots = [
            Root(os.path.join(cwd, ".agents", "skills"), SKILL_STORE, PROJECT, self.name),
            Root(os.path.join(copilot, "skills"), SKILL_STORE, USER, self.name),
            Root(os.path.join(cwd, ".github", "skills"), SKILL_STORE, PROJECT, self.name),
            Root(os.path.join(cwd, ".claude", "skills"), SKILL_STORE, PROJECT, self.name),
            Root(os.path.join(copilot, "installed-plugins"), PLUGIN_CACHE, USER, self.name),
        ]
        if not env("COPILOT_HOME"):
            roots.append(Root(os.path.join(home, ".agents", "skills"), SKILL_STORE, USER, self.name))
        return roots

    def route_not_present(self):
        return [
            "Install Matt Pocock's collection: npx skills@latest add -g mattpocock/skills, selecting "
            "GitHub Copilot when the installer asks which agents to install for.%s Then run %s "
            "before you rerun %s." % (agents_store_line(), RELOAD, self.vdd_skill("vdd-setup"))
        ]

    def route_present_not_resolvable(self, store):
        if store.kind == PLUGIN_CACHE:
            if store.first == "_direct":
                command = "copilot plugin enable %s" % store.second
            else:
                command = "copilot plugin enable %s@%s" % (store.second, store.first)
            return ["Run %s, then start a new copilot Session." % command]
        extra = agents_store_line() if store.scope == USER else ""
        return [
            "First run %s. If that still cannot run it, re-run the install and select GitHub "
            "Copilot: %s.%s Then run %s." % (RELOAD, cli_add(store.scope), extra, RELOAD)
        ]

    def route_old_collection(self, store):
        if store is None:
            return None
        if store.kind == PLUGIN_CACHE:
            if store.first == "_direct":
                return [
                    "Update it: copilot plugin update <plugin>, where <plugin> is the bare plugin "
                    "name copilot plugin list shows, not the source id %s." % store.second
                ]
            return ["Update it: copilot plugin update %s@%s" % (store.second, store.first)]
        return ["Update it: %s" % cli_update(store.scope)]

    def no_hit_continuation(self):
        return ""

    def orchestrator_launch(self):
        return "run copilot in a terminal in this repository, then /vdd:vdd-orchestrator in that Session"

    def wait_next(self, role, wait_command, paste_command):
        return "Run this in async or detach mode, never sync, then end your turn: %s" % wait_command


HARNESS = CopilotCli()
