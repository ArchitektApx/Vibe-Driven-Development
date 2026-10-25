"""Whether Codex trusts VDD's hook: each vdd@<marketplace> entry in
config.toml checked against the installed copy, hashed as Codex hashes it,
and the report lines and Tell lines Setup prints for it."""

from __future__ import annotations

import os

from ... import stores, textfile
from ..report import Report
from . import fingerprint, installed, trust

NOT_TRUSTED_WAIT = "Trust VDD's hook in /hooks, then say so here, or say skip."
CHANGED_WAIT = "VDD changed since you trusted its hook. Trust it again in /hooks, then say so here, or say skip."
COULD_NOT_VERIFY = ("Setup could not verify that Codex trusts VDD's hook. If /hooks lists it for review, "
                    "trust it there.")
SWITCHED_OFF = "VDD's hook is switched off in Codex: turn it on in /hooks, or every Doorbell waits for a paste."

TRUSTED = "trusted"
CHANGED = "changed"
NOT_TRUSTED = "not trusted"
OFF = "switched off"
UNVERIFIED = "could not verify"


class Check:
    """One run's trust check: the Codex home, config.toml and how the report
    shows paths."""

    def __init__(self, report: Report, home: str, cwd: str) -> None:
        self.report = report
        self.home = home
        self.cwd = cwd
        self.config = os.path.join(home, "config.toml")
        self.config_label = self.shown(self.config)
        self.states: list[str] = []

    def shown(self, path: str) -> str:
        return stores.display(path, self.cwd)

    def run(self, text: str | None) -> None:
        found = trust.entries(text)
        if found == trust.UNREADABLE:
            self.unverified("VDD's Codex hook", "%s could not be read" % self.config_label)
        elif found == trust.NOT_UNDERSTOOD:
            self.unverified("VDD's Codex hook", "%s was read but not understood" % self.config_label)
        elif not found:
            self.line(NOT_TRUSTED, "VDD's Codex hook: not trusted, %s has no entry for it." % self.config_label)
        else:
            for entry in found:
                label = "VDD's Codex hook" if len(found) == 1 else "VDD's Codex hook for vdd@%s" % entry.marketplace
                self.entry(entry, label)
        self.tells()

    def entry(self, entry: trust.Entry, label: str) -> None:
        if entry.enabled is False:
            self.line(OFF, "%s: switched off, %s says enabled = false for it." % (label, self.config_label))
            return
        if entry.trusted_hash is None:
            self.line(NOT_TRUSTED, "%s: not trusted, %s holds no approval for it." % (label, self.config_label))
            return
        if entry.trusted_content_hash is None:
            self.unverified(label, "%s holds an approval from before Codex 0.164" % self.config_label)
            return
        copy = installed.find(self.home, entry.marketplace)
        if copy.root is None and copy.candidates:
            self.unverified(label, "%s holds versions whose order Codex does not fix: %s"
                            % (self.shown(copy.directory), ", ".join(copy.candidates)))
            return
        if copy.root is None:
            self.unverified(label, "no installed copy at %s" % self.shown(copy.directory))
            return
        root = self.shown(copy.root)
        try:
            current = fingerprint.content_hash(copy.root)
        except fingerprint.Unhashable as error:
            self.unverified(label, unhashable(root, error))
            return
        if current == entry.trusted_content_hash:
            self.line(TRUSTED, "%s: trusted, the installed copy at %s is the one you trusted. Passed." % (label, root))
        else:
            self.line(CHANGED, "%s: changed, the installed copy at %s differs from the one you trusted."
                      % (label, root))

    def line(self, state: str, text: str) -> None:
        self.states.append(state)
        self.report.out.line(text)

    def unverified(self, label: str, cause: str) -> None:
        self.line(UNVERIFIED, "%s: could not verify, %s." % (label, cause))

    def tells(self) -> None:
        out = self.report.out
        if OFF in self.states:
            out.tell(SWITCHED_OFF)
        if UNVERIFIED in self.states:
            out.tell(COULD_NOT_VERIFY)
        if CHANGED in self.states:
            out.tell(CHANGED_WAIT)
        elif NOT_TRUSTED in self.states:
            out.tell(NOT_TRUSTED_WAIT)


def unhashable(root: str, error: fingerprint.Unhashable) -> str:
    if error.kind == fingerprint.UNREADABLE:
        why = "it could not be read (%s)" % textfile.reason(error.error or OSError())
    elif error.kind == fingerprint.RESIZED:
        why = "it changed size while Setup read it"
    else:
        why = "it is not a plain file or directory"
    return "the installed copy at %s holds an entry Setup cannot hash, %s: %s" % (root, error.relative, why)


def check(report: Report, home: str, cwd: str, text: str | None) -> None:
    """Report the trust of every VDD hook entry in config.toml, whose text
    trust.read() gave."""
    Check(report, home, cwd).run(text)
