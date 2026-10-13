"""Codex."""

from . import Harness


class Codex(Harness):
    name = "codex"
    label = "Codex"

    def borrowed_skill(self, skill):
        return "$" + skill

    def vdd_skill(self, skill):
        return "$vdd:" + skill


HARNESS = Codex()
