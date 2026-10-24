"""Claude Code."""

from __future__ import annotations

import os

from . import Harness
from .. import places
from ..stores import PLUGIN_CACHE, PROJECT, SKILL_STORE, USER, Root, Store, cli_add, cli_update, env


class ClaudeCode(Harness):
    name = "claude-code"
    label = "Claude Code"
    display_name = "Claude Code"

    def borrowed_skill(self, skill: str) -> str:
        return "/" + skill

    def vdd_skill(self, skill: str) -> str:
        return "/vdd:" + skill

    def present_roots(self, cwd: str) -> list[Root]:
        # Claude Code moves its user store with CLAUDE_CONFIG_DIR and its
        # plugin directory with CLAUDE_CODE_PLUGIN_CACHE_DIR. The cache root
        # stops at */mattpocock-skills: Claude Code stages a marketplace clone
        # as cache/temp_git_*, laid out as the collection's own repository,
        # and that transient copy is not an install.
        config = env("CLAUDE_CONFIG_DIR") or os.path.join(places.home(), ".claude")
        plugins = env("CLAUDE_CODE_PLUGIN_CACHE_DIR") or os.path.join(config, "plugins")
        return [
            Root(os.path.join(config, "skills"), SKILL_STORE, USER, self.name),
            Root(os.path.join(cwd, ".claude", "skills"), SKILL_STORE, PROJECT, self.name),
            Root(os.path.join(plugins, "cache"), PLUGIN_CACHE, USER, self.name, "*/mattpocock-skills"),
        ]

    def route_not_present(self) -> list[str]:
        return [
            "Install Matt Pocock's collection: /plugin marketplace add mattpocock/skills, then "
            "/plugin install mattpocock-skills@mattpocock, then turn on auto-update for the "
            "mattpocock marketplace under /plugin > Marketplaces (auto-update is off by default "
            "for every marketplace but Anthropic's own)."
        ]

    def route_present_not_resolvable(self, store: Store) -> list[str]:
        if store.kind == PLUGIN_CACHE:
            return [
                "Run claude plugin enable mattpocock-skills@%s from the repository root, then start "
                "a new Claude Code Session. If the plugin is enabled and still not loaded, reinstall "
                "it." % store.first
            ]
        return [
            "Re-run the install and select Claude Code: %s, then start a new Claude Code Session."
            % cli_add(store.scope)
        ]

    def route_old_collection(self, store: Store | None) -> list[str] | None:
        if store is None:
            return None
        if store.kind == PLUGIN_CACHE and store.first == "claude-plugins-official":
            return [
                "Anthropic's marketplace pins an old version of the collection, so switch to Matt "
                "Pocock's: claude plugin uninstall mattpocock-skills@claude-plugins-official, then "
                "claude plugin marketplace add mattpocock/skills, then claude plugin install "
                "mattpocock-skills@mattpocock, then turn on auto-update for mattpocock under "
                "/plugin > Marketplaces."
            ]
        if store.kind == PLUGIN_CACHE:
            return [
                "Update it: claude plugin marketplace update %s, then claude plugin update "
                "mattpocock-skills (inside a Claude Code Session the first half is /plugin "
                "marketplace update %s)." % (store.first, store.first)
            ]
        return ["Update it: %s" % cli_update(store.scope)]

    def no_hit_continuation(self) -> str:
        return ""

    def respawn_recommendation(self) -> tuple[str | None, str | None]:
        return ("every round", "over 200k")

    def reports_subagent_tokens(self) -> bool:
        return True

    def picks_up_doorbell(self) -> bool:
        return True

    def runs_sandboxed(self) -> bool:
        # Claude Code's sandbox sets it in every command it runs sandboxed.
        return os.environ.get("SANDBOX_RUNTIME") == "1"

    def waits_through_stop_hook(self) -> bool:
        return False

    def orchestrator_launch(self, slug: str) -> str:
        return "run claude in a terminal in this repository, then /vdd:vdd-orchestrator %s in that Session" % slug

    def wait_next(self, wait_command: str, paste_command: str) -> str:
        return (
            "Run this in the background with run_in_background set and a timeout of at least 2760000 ms, "
            "then end your turn: %s" % wait_command
        )


HARNESS = ClaudeCode()
