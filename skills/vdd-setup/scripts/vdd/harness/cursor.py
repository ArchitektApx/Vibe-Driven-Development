"""Cursor, the IDE's Agent and the Cursor CLI alike."""

from . import Harness


class Cursor(Harness):
    name = "cursor"
    label = "Cursor"

    def borrowed_skill(self, skill):
        return "/" + skill

    def vdd_skill(self, skill):
        return "/" + skill


HARNESS = Cursor()
