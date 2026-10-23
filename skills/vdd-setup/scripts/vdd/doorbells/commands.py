"""The command lines a Role is told to run for a Doorbell. Every command the
tool prints for a Role to run names the loop it ran on."""

from __future__ import annotations

from .. import places
from ..harness import Harness


def take_command(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    """The take command, naming the copy at entry (the running one by default)."""
    return "%s doorbell take --role %s --harness %s --slug %s" % (places.command(entry), role, harness.name, slug)


def wait_command(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    return "%s doorbell wait --role %s --harness %s --slug %s" % (places.command(entry), role, harness.name, slug)


def ring_command(role: str, harness: Harness, slug: str) -> str:
    return "%s doorbell ring --role %s --harness %s --slug %s --write" % (places.command(), role, harness.name, slug)


def paste_command(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    return '%s doorbell take --role %s --pasted "<the line the user pastes>" --harness %s --slug %s' % (
        places.command(entry), role, harness.name, slug)


def wait_next(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    return harness.wait_next(wait_command(role, harness, slug, entry), paste_command(role, harness, slug, entry))
