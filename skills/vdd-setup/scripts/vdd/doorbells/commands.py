"""The command lines a Role is told to run for a Doorbell. Every command the
tool prints for a Role to run names the loop it ran on."""

from __future__ import annotations

from .. import catalog
from ..harness import Harness

PASTED = '"<the line the user pastes>"'


def take_command(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    """The take command, naming the copy at entry (the running one by default)."""
    return catalog.line("doorbell", "take", entry, role=role, harness=harness.name, slug=slug)


def wait_command(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    return catalog.line("doorbell", "wait", entry, role=role, harness=harness.name, slug=slug)


def ring_command(role: str, harness: Harness, slug: str) -> str:
    return catalog.line("doorbell", "ring", role=role, harness=harness.name, slug=slug, write=True)


def paste_command(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    return catalog.line("doorbell", "take", entry, role=role, pasted=PASTED, harness=harness.name, slug=slug)


def wait_next(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    return harness.wait_next(wait_command(role, harness, slug, entry), paste_command(role, harness, slug, entry))


def relayed_wait_next(role: str, harness: Harness, slug: str) -> str:
    return harness.relayed_wait_next(wait_command(role, harness, slug), paste_command(role, harness, slug))
