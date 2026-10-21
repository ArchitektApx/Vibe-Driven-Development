"""brainstorm migrate, driven from outside on a small 0.15 fixture store:
the plan, the Log's events, links to slugs, the interrupted states, the
migration lock, and the repair of a lost layout marker with M7."""

import os
import shutil
import subprocess
import sys

from test_brainstorm import S, TODAY, BrainstormTest
from vddtest import ENTRY

BACKUP = ".scratch/_brainstorming.pre-0.16"
STAGING = ".scratch/_brainstorming.migrating"

INDEX = """# Brainstorming Index

## Ideas

| Idea | Importance | Size | Fog | Status | TL;DR |
|---|---|---|---|---|---|
| [main-idea.md](main-idea.md) | large | large | small | shaped | Main idea. |

## Log

- 2026-10-07, last: main-idea talked through for a while. Split by the user into
  part-one and part-two; both captured.
- 2026-10-05: part-three folded into part-two.
- 2026-10-04: Three dropped, several folded.
- 2026-10-03: Renamed the naming idea; the old name is gone.
- 2026-10-01: old-name-thing dropped, merged into `beta` in #30.
"""

MAIN_BODY = """## Summary

The main idea; see [research notes](research/main-idea/notes.md) and [the old one](old-name-thing.md).

## Related Ideas

- enables [part-one](part-one.md): part 1.

## Next Steps

- [x] First step, after [part-two](part-two.md).
- [ ] Take the parts forward.
"""

PART_BODY = """## Summary

A part.

## Related Ideas

- depends on [main-idea](main-idea.md): part of it.

## Next Steps

- [ ] Count the cost.
"""


def old_idea(title, tldr, status, body, depends=(), related=(), created="2026-10-01", updated="2026-10-07"):
    fm = ["---", "title: %s" % title, "tldr: %s" % tldr, "status: %s" % status, "created: %s" % created,
          "last-updated: %s" % updated, "importance: medium", "size: small", "fog: small",
          "depends-on:" + "".join("\n  - %s.md" % d for d in depends), "benefits-from:",
          "related:" + "".join("\n  - %s.md" % r for r in related), "---"]
    return "\n".join(fm) + "\n\n# %s\n\n%s" % (title, body)


class MigrateTest(BrainstormTest):
    EVENTS = ("--event", "2026-10-07 main-idea split into part-one, part-two",
              "--event", "2026-10-05 part-three folded into part-two")

    def setUp(self):
        BrainstormTest.setUp(self)
        w = self.box.write
        w(S + "index.md", INDEX)
        w(S + "main-idea.md", old_idea("Main idea", "Main idea. The whole thing.", "shaped", MAIN_BODY,
                                       related=["part-one"]))
        w(S + "part-one.md", old_idea("Part one", "Part 1 of main-idea. The first half.", "idea", PART_BODY,
                                      depends=["main-idea"]))
        w(S + "part-two.md", old_idea("Part two", "Part 2 of main-idea. The second half.", "discussed",
                                      "## Summary\n\nThe second half.\n"))
        w(S + "part-three.md", old_idea("Part three", "Folded away.", "dropped", "## Summary\n\nFolded.\n"))
        w(S + "old-name-thing.md", old_idea("Old name thing", "Sessions named themselves.", "dropped",
                                            "## Decision\n\nDropped 2026-10-01: no.\nReopen when: asked.\n"))
        w(S + "research/main-idea/notes.md", "notes\r\n")
        w(S + "research/check-links.py", "print(1)\n")

    def migrated(self):
        result = self.ok("migrate", *(self.EVENTS + ("--write",)))
        return result

    def all_files(self):
        return self.tree(self.box.path(".scratch"))


class Plan(MigrateTest):
    def test_start_prints_the_plan_with_a_fold_as_a_merge_and_writes_nothing(self):
        """Prevents a read that migrates and a Log fold left out (spec stories
        41, 43, 44): start on a 0.15 store prints the plan, the Log's
        restructure sentences with the fold shown as its merge event and
        the sentences that need the user, a fold whose ideas the Log does not
        name among them (finding 12), and writes nothing; its Next: asks only
        about restructures of ideas (finding 21)."""
        before = self.all_files()
        result = self.ok("start")
        self.assertIn("0.15 layout: index.md and 5 idea files", result.text)
        self.assertIn(BACKUP + "/", result.text)
        self.assertIn("Split by the user into part-one and part-two", result.text)
        self.assertIn("    event: 2026-10-05 part-three merged into part-two", result.text)
        self.assertNotIn("merged into `beta`", result.text)
        self.assertIn("Needs the user: a split, rename or fold whose ideas the Log does not name:", result.text)
        self.assertIn("Renamed the naming idea", result.text.split("Needs the user")[1])
        self.assertIn("Three dropped, several folded.", result.text.split("Needs the user")[1])
        self.assertNext(result, "'X folded into Y' is the event 'X merged into Y'", "Needs the user",
                        "records a split, merge or rename of ideas", "naming it in your ask as passed over", "--write")
        self.assertNotIn("moved under", result.last)
        self.assertEqual(self.all_files(), before)
        self.assertNotIn("Dry run", result.text)
        result = self.ok("migrate", *self.EVENTS)
        self.assertTrue(result.text.startswith("Dry run, nothing was written. With --write, brainstorm migrate would "
                                               "write "), result.text)
        header = result.lines[0].replace("\\", "/")
        self.assertIn(BACKUP, header)
        self.assertIn(STAGING, header)
        self.assertIn("Events to carry: 2026-10-07 main-idea split into part-one, part-two; 2026-10-05 part-three "
                      "merged into part-two", result.text)
        self.assertEqual(self.all_files(), before)

    def test_a_capitalised_fold_is_read_and_a_fold_of_unknown_ideas_needs_the_user(self):
        """Prevents a Log fold lost or mangled (spec 'migrate': a Log 'X
        folded into Y' becomes the merge event): a capitalised slug is read
        whole and lowercased, and a fold naming no idea of the store is put to
        the user, never printed as an event."""
        self.box.write(S + "index.md", INDEX + "- 2026-10-04: Tidied up. Old-Name-Thing folded into part-two.\n"
                                               "- 2026-10-02: Alpha folded into beta.\n")
        result = self.ok("start")
        self.assertIn("    event: 2026-10-04 old-name-thing merged into part-two", result.text)
        self.assertNotIn("lpha merged", result.text)
        self.assertNotIn("merged into beta", result.text)
        self.assertIn("Alpha folded into beta", result.text.split("Needs the user")[1])

    def test_an_event_with_an_unknown_slug_or_a_bad_date_is_refused(self):
        """Prevents an invented or misspelt event reaching History (spec
        'migrate'), and a History the frontmatter contradicts: a move, a date
        after today and an idea on both sides are refused too (findings 19,
        20); the whole migration is refused, nothing written."""
        before = self.all_files()
        for event, says in (("2026-10-07 main-idea split into part-nine", "no idea named part-nine"),
                            ("2026-02-30 main-idea split into part-one", "2026-02-30 is no date"),
                            ("yesterday main-idea split into part-one", "not '<YYYY-MM-DD>"),
                            ("2026-10-07 part-one moved under main-idea", "filed after the migration, with brainstorm move"),
                            ("2027-03-01 main-idea split into part-one", "2027-03-01 is after today, %s" % TODAY),
                            ("2026-10-07 main-idea split into main-idea", "names main-idea on both sides"),
                            ("2026-10-07 part-one renamed from part-one", "names part-one on both sides")):
            result = self.bs("migrate", "--event", event, "--write")
            self.assertEqual(result.code, 1, result)
            self.assertIn(says, result.text)
        self.assertEqual(self.all_files(), before)

    def test_other_commands_refuse_the_old_layout(self):
        """Prevents a lagging plugin writing into a store it does not know."""
        result = self.bs("show", "--idea", "main-idea")
        self.assertEqual(result.code, 1, result)
        self.assertIn("0.15 layout", result.text)


class Migrate(MigrateTest):
    def test_migrate_keeps_a_byte_copy_and_converts_every_idea_in_place(self):
        """Prevents a lossy migration (spec stories 42, 43, 45): the backup is
        the old store byte for byte with index.md; every idea keeps its file,
        with History seeded and the events carried; research moves unchanged;
        no parent is inferred; the undo Tell line and the overview follow."""
        before = self.tree()
        result = self.migrated()
        self.assertEqual(self.tree(self.box.path(BACKUP)), before)
        self.assertEqual(self.read(".layout"), "2\n")
        self.assertFalse(self.exists("index.md"))
        self.assertTrue(self.exists(".state/ledger.json"))
        main = self.read("main-idea.md")
        self.assertTrue(main.startswith("---\ntldr: Main idea. The whole thing.\nstatus: shaped\n"), main)
        self.assertIn("- 2026-10-01: created\n- 2026-10-07: split into part-one\n- 2026-10-07: split into "
                      "part-two\n- 2026-10-07: status shaped\n", main)
        self.assertIn("- 2026-10-05: merged into part-two", self.read("part-three.md"))
        self.assertIn("- 2026-10-05: merged from part-three", self.read("part-two.md"))
        for name in ("main-idea", "part-one", "part-two", "part-three", "old-name-thing"):
            self.assertNotIn("parent:", self.read(name + ".md"))
        with open(self.box.path(S + "research/main-idea/notes.md"), "rb") as handle:
            self.assertEqual(handle.read(), b"notes\r\n")
        self.assertTrue(self.exists("research/check-links.py"))
        tells = result.tells()
        self.assertTrue(any(BACKUP in t and "rename" in t and "0.15 VDD plugin" in t for t in tells), result)
        self.assertIn("Ideas: 3 open, 2 closed.", result.text)
        self.assertEqual(result.text.count("Backup of the 0.15 store: %s/" % BACKUP), 1, result.text)
        self.assertIn("Backup of the 0.15 store: %s/" % BACKUP, self.ok("start").text)
        self.assertIn("Named as a part in their tldr but not filed under that parent: part-one (main-idea), part-two "
                      "(main-idea).", result.text)

    def test_links_to_ideas_become_slugs_next_steps_included(self):
        """Prevents a link that means nothing in the flat store of slugs (spec
        story 45): a link to an idea becomes its slug, bare on a relation
        line and a code span elsewhere; a research link keeps its target; a
        frontmatter relation whose pair a prose line names, under any kind, is
        not written again (finding 17)."""
        self.migrated()
        main = self.read("main-idea.md")
        self.assertIn("- enables part-one: part 1.", main)
        self.assertIn("the old one (`old-name-thing`)", main)
        self.assertIn("- [x] First step, after `part-two`.", main)
        self.assertIn("[research notes](research/main-idea/notes.md)", main)
        self.assertNotIn("- related part-one", main)
        self.assertEqual(self.read("part-one.md").count("depends on main-idea"), 1)
        self.assertIn("No problems.", self.ok("check").text)


class Interrupted(MigrateTest):
    def test_a_leftover_staging_is_rebuilt(self):
        """Prevents a half-written staging from a killed run being swapped in
        (spec story 46): staging only is deleted and built again."""
        self.box.write(STAGING + "/junk.md", "junk")
        self.migrated()
        self.assertFalse(self.exists("junk.md"))
        self.assertFalse(os.path.exists(self.box.path(STAGING)))

    def test_backup_and_staging_without_a_store_are_finished_by_a_rerun(self):
        """Prevents a dead end after a crash between the two renames (red
        team F2, U12): start names it, a dry run writes nothing, new refuses,
        and migrate --write does the second rename, never deletes the
        finished staging, and tells the undo the crash kept from the user
        (finding 18)."""
        self.migrated()
        store = self.box.path(S.rstrip("/"))
        os.rename(store, self.box.path(STAGING))
        result = self.ok("start")
        self.assertIn("interrupted", result.text)
        before = self.all_files()
        result = self.ok("migrate")
        self.assertIn("Dry run, nothing was written. With --write, brainstorm migrate would write "
                      "%s/ (renamed from %s/):" % (S.rstrip("/"), STAGING), result.text.replace("\\", "/"))
        self.assertEqual(self.all_files(), before)
        result = self.bs("new", "--slug", "fresh", "--title", "Fresh", "--tldr", "Fresh.", "--write")
        self.assertEqual(result.code, 1, result)
        self.assertEqual(self.all_files(), before)
        result = self.ok("migrate", "--write")
        self.assertIn("The interrupted migration is finished", result.text)
        self.assertTrue(any("0.15 VDD plugin" in t for t in result.tells()), result)
        self.assertNext(result, "relaying the Tell line above")
        self.assertEqual(result.text.count("Backup of the 0.15 store"), 1, result.text)
        self.assertEqual(self.read(".layout"), "2\n")
        self.assertTrue(self.exists("main-idea.md"))

    def test_backup_and_store_is_done(self):
        """Prevents a second migration over a migrated store."""
        self.migrated()
        result = self.ok("migrate", "--write")
        self.assertIn("already in layout 2; nothing to migrate", result.text)

    def test_two_migrations_at_once_run_one_after_the_other(self):
        """Prevents two Sessions migrating together from losing research
        files and reporting success (red team M2): the second waits for the
        migration lock and then finds the store migrated."""
        env = self.box.env(VDD_TODAY=TODAY)
        argv = [sys.executable, ENTRY, "brainstorm", "migrate"] + list(self.EVENTS) + ["--write"]
        procs = [subprocess.Popen(argv, cwd=self.box.proj, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                 for _ in range(2)]
        outs = [p.communicate(timeout=120)[0].decode("utf-8") for p in procs]
        self.assertEqual([p.returncode for p in procs], [0, 0], outs)
        self.assertEqual(sum(1 for o in outs if "Migrated 5 ideas" in o), 1, outs)
        self.assertEqual(sum(1 for o in outs if "already in layout 2" in o), 1, outs)
        self.assertEqual(self.read("research/main-idea/notes.md"), "notes\r\n")
        self.assertEqual(sorted(os.listdir(self.box.path(".scratch"))), ["_brainstorming", "_brainstorming.pre-0.16"])


class Marker(MigrateTest):
    def setUp(self):
        MigrateTest.setUp(self)
        self.migrated()

    def test_a_lost_marker_is_named_and_written_back(self):
        """Prevents a layout-2 store without .layout taken for a 0.15 store
        (red team D4, spec story 47): start names it, every other command
        refuses, the dry run writes nothing, and migrate --write writes the
        marker and nothing else."""
        os.remove(self.box.path(S + ".layout"))
        before = self.ideas_tree()
        result = self.ok("start")
        self.assertIn("marker is missing", result.text)
        self.assertNotIn("0.15 layout", result.text)
        result = self.bs("show", "--idea", "main-idea")
        self.assertEqual(result.code, 1, result)
        self.assertIn("migrate --write", result.last)
        result = self.ok("migrate")
        self.assertIn("Dry run, nothing was written. With --write, brainstorm migrate would write .layout:",
                      result.text)
        self.assertFalse(self.exists(".layout"))
        self.ok("migrate", "--write")
        self.assertEqual(self.read(".layout"), "2\n")
        after = self.ideas_tree()
        after.pop(".layout")
        self.assertEqual(after, before)

    def test_a_lost_marker_beside_a_stale_index_is_repaired_not_remigrated(self):
        """Prevents a migrated store read as 0.15 because a stale skill wrote
        index.md (red team M7): .state/ marks it as this tool's."""
        os.remove(self.box.path(S + ".layout"))
        self.box.write(S + "index.md", "# Brainstorming Index\n")
        result = self.ok("start")
        self.assertIn("marker is missing", result.text)
        self.assertNotIn("0.15 layout", result.text)

    def test_a_file_without_history_is_seeded_and_an_unknown_status_refuses(self):
        """Prevents a mixed install failing the repair (red team M7, spec
        story 48): an idea file a 0.15 skill wrote without History is named
        and gets its created line, dated from its created field before its
        last-updated; a file with no
        known status still fails the repair, named."""
        self.box.write(S + ".layout", "")
        self.box.write(S + "late-idea.md", "---\ntldr: Late.\nstatus: idea\ncreated: 2026-10-02\nlast-updated: 2026-10-12\n---\n\n# Late\n")
        self.box.write(S + "stray.md", "---\nstatus: thinking\n---\n\n# Stray\n")
        before = self.ideas_tree()
        result = self.bs("migrate", "--write")
        self.assertEqual(result.code, 1, result)
        self.assertIn("stray.md: status 'thinking'", result.text)
        self.assertEqual(self.ideas_tree(), before)
        os.remove(self.box.path(S + "stray.md"))
        result = self.ok("migrate")
        self.assertIn("would write late-idea.md, .layout:", result.text)
        self.assertIn("late-idea.md", result.text)
        result = self.ok("migrate", "--write")
        self.assertIn("late-idea.md", result.text)
        self.assertEqual(self.read(".layout"), "2\n")
        self.assertIn("## History\n\n- 2026-10-02: created\n", self.read("late-idea.md"))

    def test_a_newer_marker_is_never_stamped_back(self):
        """Prevents an old Shared copy writing 2 over a newer store's marker
        (red team D9)."""
        self.box.write(S + ".layout", "3\n")
        result = self.bs("migrate", "--write")
        self.assertEqual(result.code, 1, result)
        self.assertIn("rerun Setup", result.last)
        self.assertEqual(self.read(".layout"), "3\n")

    def test_a_dry_run_repair_reads_only_and_the_write_prints_its_recovery(self):
        """Prevents a dry run that takes the lock, settles a journal and
        creates .state/ (finding 16), and a repair whose recovery goes
        unsaid (finding 15)."""
        os.remove(self.box.path(S + ".layout"))
        shutil.rmtree(self.box.path(S + ".state"))
        before = self.all_files()
        result = self.ok("migrate")
        self.assertIn("Dry run", result.text)
        self.assertEqual(self.all_files(), before)
        self.assertFalse(self.exists(".state"))
        journal = S + ".state/journal/20261020T000000-1-000001.json"
        self.box.write(journal, '{"label": "note part-one", "pid": 1, "ops": [], "dirs": []}')
        before = self.all_files()
        result = self.ok("migrate")
        self.assertIn("migrate --write settles it first", result.text)
        self.assertEqual(self.all_files(), before)
        result = self.ok("migrate", "--write")
        self.assertIn("An interrupted write (note part-one) was finished.", result.text)
        self.assertFalse(self.exists(".state/journal/20261020T000000-1-000001.json"))
