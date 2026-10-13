"""Copilot CLI."""

from . import Harness


class CopilotCli(Harness):
    name = "copilot-cli"
    label = "Copilot CLI"

    def borrowed_skill(self, skill):
        return "/" + skill

    def vdd_skill(self, skill):
        return "/vdd:" + skill


HARNESS = CopilotCli()
