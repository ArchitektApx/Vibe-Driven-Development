"""Generic: a Harness VDD does not know. Nobody knows which stores it reads or
how the user types a skill name, so it names skills bare."""

from . import Harness


class Generic(Harness):
    name = "generic"
    label = ""

    def borrowed_skill(self, skill):
        return skill

    def vdd_skill(self, skill):
        return skill


HARNESS = Generic()
