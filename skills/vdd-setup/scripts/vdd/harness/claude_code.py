"""Claude Code."""

from . import Harness


class ClaudeCode(Harness):
    name = "claude-code"
    label = "Claude Code"

    def borrowed_skill(self, skill):
        return "/" + skill

    def vdd_skill(self, skill):
        return "/vdd:" + skill


HARNESS = ClaudeCode()
