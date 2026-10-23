"""loop fold, driven from outside: the one rewrite of a loop's commits after
the code Sign-off.

Every fold case holds: the folded tree equals the signed tree, the base
branch and every commit before the loop keep their shas, and the fold does
not stop. Each case adds its own placement. The cases port ticket 71's
scripted fold cases, every one but c10, which is coder check's."""

import os
import shutil
import subprocess
import unittest

from vddtest import PLAN_SIGNED, WINDOWS, LoopRepoTest, SceneTest

README = (
    "# Ledger\n"
    "\n"
    "Usage: ledger report [--since YYYY-MM-DD]\n"
    "\n"
    "`report` lists the entries as a table; amounts have two decimals.\n"
)
README2 = README.replace("[--since YYYY-MM-DD]\n", "[--since YYYY-MM-DD] [--format table|csv]\n")
README3 = README2.replace("as a table;", "as a table or CSV;")
README_SUBJECT = "docs(readme): show --format in the usage"

REPORT = (
    "def report(rows):\n"
    "    for row in rows:\n"
    "        print(row.date, \"%.2f\" % row.amount)\n"
)

CSV = "ledger/report_csv.py"
T01 = (
    "import csv\n"
    "\n"
    "\n"
    "def format_amount(amount):\n"
    "    return str(amount)\n"
    "\n"
    "\n"
    "def write_csv(rows, out):\n"
    "    writer = csv.writer(out)\n"
    "    for row in rows:\n"
    "        writer.writerow([row.date, format_amount(row.amount)])\n"
)
TEST_T01 = "from ledger.report_csv import write_csv\n\n\ndef test_write():\n    assert write_csv\n"
DOC_T02 = T01.replace("def format_amount(amount):\n",
                      "def format_amount(amount):\n    \"\"\"The amount as the CSV writes it.\"\"\"\n")
T01_SUBJECT = "feat(report): write the report table as CSV"

CLI = "ledger/cli.py"
CLI_T02 = (
    "import argparse\n"
    "\n"
    "\n"
    "def main(argv=None):\n"
    "    parser = argparse.ArgumentParser(prog=\"ledger\")\n"
    "    parser.add_argument(\"--format\", choices=[\"table\", \"csv\"], default=\"table\",\n"
    "                        help=\"table, csv\")\n"
    "    return parser.parse_args(argv)\n"
)
CLI_FIXED = CLI_T02.replace('help="table, csv")', 'help="table (default) or csv")')
TEST_T02 = "from ledger.cli import main\n\n\ndef test_main():\n    assert main([]).format == \"table\"\n"
T02_SUBJECT = "feat(cli): add --format csv to ledger report"


def fixed_return(text):
    return text.replace("    return str(amount)\n", "    return f\"{amount:.2f}\"\n")


class FoldTest(SceneTest):
    def stage_scene(self):
        self.box.init_git("main")
        for key, value in (("user.name", "VDD Test"), ("user.email", "test@example.com"),
                           ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
            self.git("config", key, value)
        self.commit_files({".gitignore": ".scratch/\n", "README.md": README, "ledger/report.py": REPORT}, "chore: the ledger")
        self.git("checkout", "-q", "-b", "demo")
        self.box.write_loop("demo", extra=(PLAN_SIGNED,))
        self.rounds = 0
        self.main_sha = self.sha("main")
        self.main_history = self.out("rev-list", "main")

    # --- git ---

    def commit_files(self, files, message, date=None):
        """The fold's variant of commit: several files, and an author date
        and name when date is set."""
        for name, text in files.items():
            self.box.write(name, text)
        self.git("add", "-A")
        env = dict(os.environ)
        if date:
            env.update(GIT_AUTHOR_DATE=date, GIT_AUTHOR_NAME="Coder", GIT_AUTHOR_EMAIL="coder@example.com")
        self.git("commit", "-q", "-m", message, env=env)
        return self.sha()

    def code_round(self, commits, open_after=1, steps=(), reviewed=True):
        """One code round: its commits (files, message), then its recorded
        start and end and a review leaving open_after findings open (0 signs
        off). steps run git before the commits."""
        self.rounds += 1
        start = self.sha()
        for step in steps:
            step()
        for files, message in commits:
            self.commit_files(files, message)
        self.stage("code %d start %s" % (self.rounds, start), "code %d end %s" % (self.rounds, self.sha()))
        if not reviewed:
            return self.sha()
        if open_after:
            self.stage("code %d reviewed open 1 counts 0 0 %d next 2 new 1 closed 0 checks code-review ran"
                       % (self.rounds, open_after))
        else:
            self.stage("code %d reviewed signed-off - counts 0 0 0 next 2 new 0 closed 1 checks code-review ran"
                       % self.rounds)
        return self.sha()

    def round_one(self, t02_extra=None, open_after=1):
        t02 = {CLI: CLI_T02, "tests/test_cli.py": TEST_T02}
        t02.update(t02_extra or {})
        return self.code_round([({CSV: T01, "tests/test_report_csv.py": TEST_T01}, T01_SUBJECT),
                                (t02, T02_SUBJECT)], open_after)

    def fold(self, write=True, env=None):
        return self.box.run("loop", "fold", "--slug", "demo", "--harness", "claude-code",
                            *(["--write"] if write else []), env=env)

    def subjects(self):
        return self.out("log", "--reverse", "--format=%s", "main..demo").split("\n")

    def commit_of(self, subject):
        for line in self.out("log", "--format=%H %s", "main..demo").split("\n"):
            sha, _, text = line.partition(" ")
            if text == subject:
                return sha
        self.fail("no commit %s in %s" % (subject, self.subjects()))

    def at(self, subject, path):
        """The file's text in the folded commit with this subject, empty when
        it has none."""
        return subprocess.run(["git", "show", "%s:%s" % (self.commit_of(subject), path)], cwd=self.box.proj,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode()

    def touched(self, subject):
        return sorted(self.out("show", "--name-only", "--format=", self.commit_of(subject)).split())

    def recap(self):
        return self.box.read(os.path.join(".scratch", "demo", "RECAP.md"))

    def folded(self, signed, result):
        """What every fold holds."""
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertTrue(any(line.startswith("Folded demo: ") for line in result.lines), result)
        self.assertEqual(self.sha("demo^{tree}"), self.sha(signed + "^{tree}"), result)
        self.assertEqual(self.sha("main"), self.main_sha)
        self.assertEqual(self.out("rev-list", "main"), self.main_history)
        self.assertEqual(self.out("merge-base", "main", "demo"), self.main_sha)
        # The checked-out feature branch moved with its tree unchanged, so the
        # working tree matches it.
        self.assertEqual(self.out("status", "--porcelain"), "")
        tells = result.tells()
        self.assertEqual(len(tells), 1, result)
        self.assertIn("Folded demo: ", tells[0])
        self.assertIn("The tree equals the signed tree; RECAP.md lists the commits.", tells[0])
        self.assertIn("fold folded %s" % self.sha("demo"), self.state())
        return self.subjects()


class FoldCaseTest(FoldTest):
    """Ticket 71's fold cases. They replace the guardrails of the Coder's
    per-round fold: 0c8a25a (find the owning commit, leave no fixup! commit)
    and 0a606c2 (PowerShell's sequence editor), now the tree check and these
    placements."""

    def test_c01_a_fix_to_lines_a_later_ticket_changed_stays_on_top(self):
        self.round_one({CSV: DOC_T02})
        self.code_round([({CSV: fixed_return(DOC_T02)}, "fix(report): write amounts with two decimals")])
        original = self.out("log", "-1", "--format=%an|%ae|%ad")
        signed = self.code_round([], 0)
        result = self.fold()
        subjects = self.folded(signed, result)
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT, "fix(report): write amounts with two decimals"])
        self.assertIn("folding it would conflict", result.text)
        self.assertEqual(self.out("log", "-1", "--format=%an|%ae|%ad", "demo"), original)

    def test_c02_a_fix_to_lines_nothing_later_touched_folds_into_its_ticket(self):
        self.round_one()
        self.code_round([({CSV: fixed_return(T01)}, "fix(report): two decimals")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])
        self.assertIn('f"{amount:.2f}"', self.at(T01_SUBJECT, CSV))

    def test_a_fix_to_a_non_ascii_file_folds_into_its_ticket(self):
        """git C-quotes a non-ASCII path in a name list by default, so the
        fold missed the file and kept its fix on top as owned by no commit."""
        name = "ledger/übersicht.py"
        self.code_round([({name: T01, "tests/test_report_csv.py": TEST_T01}, T01_SUBJECT),
                         ({CLI: CLI_T02, "tests/test_cli.py": TEST_T02}, T02_SUBJECT)])
        self.code_round([({name: fixed_return(T01)}, "fix(report): two decimals")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])
        self.assertIn('f"{amount:.2f}"', self.at(T01_SUBJECT, name))

    @unittest.skipIf(WINDOWS, "Windows allows no quote or backslash in a file name")
    def test_a_fix_to_a_file_with_a_quote_in_its_name_folds_into_its_ticket(self):
        """git C-quotes a path with a quote or a backslash in a name list even
        with core.quotePath=false, so its fix stayed on top as owned by no
        commit."""
        name = 'ledger/say "hi" \\ there.py'
        self.code_round([({name: T01, "tests/test_report_csv.py": TEST_T01}, T01_SUBJECT),
                         ({CLI: CLI_T02, "tests/test_cli.py": TEST_T02}, T02_SUBJECT)])
        self.code_round([({name: fixed_return(T01)}, "fix(report): two decimals")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])
        self.assertIn('f"{amount:.2f}"', self.at(T01_SUBJECT, name))

    def test_a_blame_ignore_revs_file_that_is_missing_does_not_stop_the_fold(self):
        """A blame.ignoreRevsFile naming no file, set globally as it usually
        is, made every blame fail, so every fold skipped with a git error."""
        self.box.write(".gitconfig", "[blame]\n\tignoreRevsFile = .git-blame-ignore-revs\n", base=self.box.home)
        self.round_one()
        self.code_round([({CSV: fixed_return(T01)}, "fix(report): two decimals")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])
        self.assertIn('f"{amount:.2f}"', self.at(T01_SUBJECT, CSV))

    def test_an_inter_hunk_context_does_not_merge_two_owners_hunks(self):
        """With diff.interHunkContext=5 a fix to Ticket 01's line went into
        Ticket 02's commit with the Ticket 02 line beside it."""
        self.git("config", "diff.interHunkContext", "5")
        self.round_one({CSV: DOC_T02})
        fixed = DOC_T02.replace("import csv\n", "import csv  # stdlib\n").replace(
            "as the CSV writes it.", "as the CSV file holds it.")
        self.code_round([({CSV: fixed}, "fix(report): the import and the docstring")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])
        self.assertIn("# stdlib", self.at(T01_SUBJECT, CSV))
        self.assertNotIn("file holds", self.at(T01_SUBJECT, CSV))
        self.assertIn("file holds", self.at(T02_SUBJECT, CSV))

    def test_a_textconv_does_not_move_the_fix(self):
        """A diff textconv changed the line counts the fold placed a hunk
        by."""
        self.git("config", "diff.twice.textconv", "awk '{ print; print }'")
        self.box.write(os.path.join(".git", "info", "attributes"), "*.py diff=twice\n")
        self.round_one()
        self.code_round([({CSV: fixed_return(T01)}, "fix(report): two decimals")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])
        self.assertIn('f"{amount:.2f}"', self.at(T01_SUBJECT, CSV))

    def test_c03_a_fix_after_a_later_ticket_renamed_the_file(self):
        start = self.sha()
        self.commit_files({CSV: T01, "tests/test_report_csv.py": TEST_T01}, T01_SUBJECT)
        self.git("mv", CSV, "ledger/csv_writer.py")
        self.commit_files({CLI: CLI_T02, "tests/test_cli.py": TEST_T02}, T02_SUBJECT)
        self.rounds = 1
        self.stage("code 1 start %s" % start, "code 1 end %s" % self.sha(),
                   "code 1 reviewed open 1 counts 0 0 1 next 2 new 1 closed 0 checks code-review ran")
        self.code_round([({"ledger/csv_writer.py": fixed_return(T01)}, "fix(report): two decimals")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertIn(len(subjects), (2, 3))

    def test_c04_a_fix_to_a_line_the_later_ticket_wrote_folds_into_that_ticket(self):
        t02 = T01.replace("def format_amount(amount):\n    return str(amount)\n\n\n", "").replace(
            "format_amount(row.amount)", "str(row.amount)")
        self.round_one({CSV: t02})
        self.code_round([({CSV: t02.replace("str(row.amount)", "f\"{row.amount:.2f}\"")}, "fix(report): two decimals")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])
        self.assertIn("{row.amount:.2f}", self.at(T02_SUBJECT, CSV))
        self.assertNotIn("{row.amount:.2f}", self.at(T01_SUBJECT, CSV))

    def test_c05_a_readme_fix_stays_on_top_and_a_second_fix_folds_into_it(self):
        self.round_one()
        self.code_round([({"README.md": README2}, README_SUBJECT)])
        self.code_round([({"README.md": README3}, "docs(readme): say csv too")])
        signed = self.code_round([], 0)
        result = self.fold()
        subjects = self.folded(signed, result)
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT, README_SUBJECT])
        self.assertIn("no commit of the loop wrote its lines", result.text)

    def test_c06_lines_of_two_commits_mixed_with_a_ticket_fix_each_go_home(self):
        self.round_one({CSV: DOC_T02})
        self.code_round([({"README.md": README2}, README_SUBJECT),
                         ({CSV: fixed_return(DOC_T02), "README.md": README3}, "fix(report): two decimals, README too")])
        self.code_round([({"README.md": README3 + "\nCSV amounts have two decimals.\n"},
                          "docs(readme): note the CSV amounts")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT, README_SUBJECT, "fix(report): two decimals, README too"])
        self.assertEqual(self.touched("fix(report): two decimals, README too"), [CSV])
        self.assertIn("CSV amounts have two decimals.", self.at(README_SUBJECT, "README.md"))

    def test_c07_a_fix_to_an_on_top_fix_folds_into_it_never_past_it(self):
        self.round_one({CSV: DOC_T02})
        self.code_round([({CSV: fixed_return(DOC_T02)}, "fix(report): write amounts with two decimals")])
        third = fixed_return(DOC_T02).replace('f"{amount:.2f}"', 'f"{amount:.2f}" if amount is not None else ""')
        self.code_round([({CSV: third}, "fix(report): blank for no amount")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT, "fix(report): write amounts with two decimals"])
        self.assertNotIn("is not None", self.at(T01_SUBJECT, CSV))

    def test_c08_six_rounds_of_fixes_all_fold_home(self):
        self.round_one()
        texts = [fixed_return(T01)]
        texts.append(texts[-1].replace('f"{amount:.2f}"', 'f"{amount:.2f}" if amount is not None else ""'))
        texts.append(texts[-1].replace("def format_amount(amount):", "def format_amount(amount):\n    # two decimals"))
        texts.append(texts[-1].replace("# two decimals", "# two decimals, dot separator"))
        texts.append(texts[-1].replace('if amount is not None else ""', 'if amount is not None else "0.00"'))
        clis = [CLI_FIXED, CLI_T02.replace('help="table, csv")', 'help="%(default)s (default) or csv")')]
        plan = [[({CSV: texts[0]}, "fix: a")],
                [({CSV: texts[1]}, "fix: b"), ({CLI: clis[0]}, "fix: c")],
                [({CSV: texts[2]}, "fix: d")],
                [({CLI: clis[1]}, "fix: e"), ({CSV: texts[3]}, "fix: f")],
                [({CSV: texts[4]}, "fix: g")]]
        for commits in plan:
            self.code_round(commits)
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])

    def test_c09_a_fix_to_code_from_before_the_loop_stays_on_top(self):
        self.round_one()
        report = REPORT.replace('"%.2f" % row.amount', '"%.2f" % row.amount if row.amount is not None else ""')
        self.code_round([({"ledger/report.py": report}, "fix(report): print an empty amount as blank")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects[-1], "fix(report): print an empty amount as blank")
        self.assertEqual(len(subjects), 3)

    def test_a_commit_that_stays_on_top_unchanged_keeps_its_sha(self):
        """A commit with its tree and parent unchanged was made again, so the
        branch moved, the committer date changed and a hand-signed commit
        lost its signature. A later committer date stands for the gap the
        tests' same-second fold hid."""
        self.round_one()
        report = REPORT.replace('"%.2f" % row.amount', '"%.2f" % row.amount if row.amount is not None else ""')
        self.code_round([({"ledger/report.py": report}, "fix(report): print an empty amount as blank")])
        signed = self.code_round([], 0)
        result = self.fold(env=self.box.env(GIT_COMMITTER_DATE="2100-01-01T00:00:00Z"))
        self.folded(signed, result)
        self.assertEqual(self.sha("demo"), signed)
        self.assertIn("Folded demo: 3 commits into 3.", result.lines)

    def test_a_commit_before_round_one_keeps_its_sha(self):
        """The chain started at the merge base, so a commit made on the
        feature branch before the loop was labelled round 1 and rewritten
        when a later fix touched its lines."""
        wip = self.commit_files({"README.md": README2}, "wip: my own work before the loop")
        self.round_one()
        self.code_round([({"README.md": README3}, "docs(readme): say csv too")])
        signed = self.code_round([], 0)
        result = self.fold()
        subjects = self.folded(signed, result)
        self.assertEqual(subjects, ["wip: my own work before the loop", T01_SUBJECT, T02_SUBJECT,
                                    "docs(readme): say csv too"])
        self.assertEqual(self.commit_of("wip: my own work before the loop"), wip)
        self.assertIn("Folded demo: 3 commits into 3.", result.lines)
        self.assertIn("no commit of the loop wrote its lines", result.text)
        self.assertNotIn("wip: my own work before the loop", result.text)

    def test_c11_a_round_committed_after_a_dirty_tree_refusal_folds(self):
        """The round's fix committed after coder check refused it
        uncommitted, through the Coder's own commands."""
        self.round_one()
        self.box.write(os.path.join(".scratch", "demo", "CODEREVIEW.md"),
                       "# Code review, round 1\n\n## New findings\n\n### 1. minor (open): ledger/report_csv.py:5\n\n"
                       "Two decimals.\n")
        started = self.box.run("coder", "start", "--slug", "demo", "--write")
        self.assertEqual(started.code, 0, started)
        self.box.write(os.path.join(".scratch", "demo", "FIXES.md"),
                       "# Fixes, round 2\n\n## Finding 1. minor: ledger/report_csv.py:5\n\nAnswer: fixed\nWhy:\n")
        self.box.write(CSV, fixed_return(T01))
        dirty = self.box.run("coder", "check", "--slug", "demo", "--write")
        self.assertNotEqual(dirty.code, 0, dirty)
        self.assertIn("uncommitted changes", dirty.text)
        self.git("commit", "-q", "-am", "fix(report): two decimals")
        checked = self.box.run("coder", "check", "--slug", "demo", "--write")
        self.assertEqual(checked.code, 0, checked)
        self.rounds = 2
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])

    def test_c12_one_commit_fixing_two_tickets_is_split_home(self):
        self.round_one()
        self.code_round([({CSV: fixed_return(T01), CLI: CLI_FIXED}, "fix: two decimals and the help")])
        signed = self.code_round([], 0)
        result = self.fold()
        subjects = self.folded(signed, result)
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])
        self.assertIn('f"{amount:.2f}"', self.at(T01_SUBJECT, CSV))
        self.assertNotIn("(default)", self.at(T01_SUBJECT, CLI))
        self.assertIn("(default)", self.at(T02_SUBJECT, CLI))

    def test_c13_a_conflicting_part_stays_on_top_with_the_coder_s_message(self):
        self.round_one({CSV: DOC_T02})
        self.code_round([({CSV: fixed_return(DOC_T02), CLI: CLI_FIXED}, "fix: two decimals and the help")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT, "fix: two decimals and the help"])
        self.assertEqual(self.touched("fix: two decimals and the help"), [CSV])
        self.assertIn("(default)", self.at(T02_SUBJECT, CLI))

    def test_c14_a_new_file_joins_its_commit_s_single_target(self):
        self.round_one()
        test = "from ledger.report_csv import format_amount\n\n\ndef test_two():\n    assert format_amount(1)\n"
        self.code_round([({CSV: fixed_return(T01), "tests/test_amounts.py": test}, "fix(report): two decimals")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])
        self.assertIn("tests/test_amounts.py", self.touched(T01_SUBJECT))

    def test_c15_a_ticket_part_folds_and_a_pre_loop_part_stays_on_top(self):
        self.round_one()
        self.code_round([({CSV: fixed_return(T01), "README.md": README2}, "fix: two decimals, README usage")])
        signed = self.code_round([], 0)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT, "fix: two decimals, README usage"])
        self.assertEqual(self.touched("fix: two decimals, README usage"), ["README.md"])


class FoldCommandTest(FoldTest):
    def two_fixes(self):
        """Round-1 commits for two Tickets and a round-2 fix to each."""
        self.round_one()
        self.code_round([({CSV: fixed_return(T01)}, "fix(report): two decimals"),
                         ({CLI: CLI_FIXED}, "fix(cli): name the default")])
        return self.code_round([], 0)

    def test_a_dry_run_changes_nothing_and_write_folds(self):
        signed = self.two_fixes()
        before = self.state()
        dry = self.fold(write=False)
        self.assertEqual(dry.code, 0, dry)
        self.assertContract(dry)
        self.assertIn("Would fold demo: 4 commits into 2.", dry.lines)
        self.assertEqual(self.sha("demo"), signed)
        self.assertEqual(self.state(), before)
        self.assertNext(dry, "loop fold --slug demo --harness claude-code --write")
        result = self.fold()
        subjects = self.folded(signed, result)
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])
        self.assertIn("Folded demo: 4 commits into 2. The tree equals the signed tree; RECAP.md lists the commits.",
                      result.tells())
        self.assertNext(result, "Invoke the vdd-create-pr skill in your own Session")

    def test_the_recap_lists_the_commits_between_findings_and_not_carried(self):
        self.round_one({CSV: DOC_T02})
        self.code_round([({CLI: CLI_FIXED}, "fix(cli): name the default"),
                         ({CSV: fixed_return(DOC_T02)}, "fix(report): two decimals")])
        signed = self.code_round([], 0)
        fix_cli = self.out("log", "-1", "--format=%h", "HEAD~1")
        self.folded(signed, self.fold())
        recap = self.recap()
        self.assertLess(recap.index("## Code findings"), recap.index("## Commits"))
        self.assertLess(recap.index("## Commits"), recap.index("## Not carried"))
        commits = recap.split("## Commits")[1].split("## Not carried")[0]
        self.assertIn("Folded demo: 4 commits into 3; the folded tree equals the signed tree (%s)." % signed[:7],
                      commits)
        self.assertIn(" %s (round 1)" % T01_SUBJECT, commits)
        self.assertIn("    + %s fix(cli): name the default: %s" % (fix_cli, CLI), commits)
        self.assertIn("fix(report): two decimals, its own commit: folding it would conflict", commits)
        self.assertIn("Code Loop: 3 rounds, signed off in round 3; folded.", recap)

    def test_a_loop_signed_off_in_round_one_is_recorded_as_folded(self):
        signed = self.round_one(open_after=0)
        result = self.fold()
        self.folded(signed, result)
        self.assertEqual(self.sha("demo"), signed)
        self.assertIn("## Commits", self.recap())
        self.assertIn("Folded demo: 2 commits into 2", self.recap())

    def test_a_second_fold_writes_nothing(self):
        """A repeated call, on a folded loop and on a skipped one, says which
        and changes nothing."""
        self.two_fixes()
        self.assertEqual(self.fold().code, 0)
        before = (self.state(), self.recap(), self.sha("demo"))
        again = self.fold()
        self.assertEqual(again.code, 0, again)
        self.assertIn("already folded", again.text)
        self.assertEqual((self.state(), self.recap(), self.sha("demo")), before)
        self.assertNext(again, "vdd-create-pr")
        self.commit_files({"x.txt": "x\n"}, "chore: after")
        self.box.write_loop("demo", extra=(PLAN_SIGNED,))
        self.stage(*[line for line in before[0].split("\n")[2:] if line and not line.startswith("fold ")])
        self.assertEqual(self.fold().code, 0)
        before = (self.state(), self.recap(), self.sha("demo"))
        again = self.fold()
        self.assertIn("already skipped", again.text)
        self.assertEqual((self.state(), self.recap(), self.sha("demo")), before)

    def test_no_temporary_index_is_left(self):
        self.round_one()
        self.code_round([({CSV: fixed_return(T01), CLI: CLI_FIXED}, "fix: both")])
        self.code_round([], 0)
        self.assertEqual(self.fold().code, 0)
        left = []
        for directory in (self.box.path(".scratch", "demo"), self.box.path(".git")):
            for here, _, names in os.walk(directory):
                left += [os.path.join(here, n) for n in names if "fold-index" in n]
        self.assertEqual(left, [])

    def test_pr_no_names_loop_close_and_the_stop_line(self):
        self.two_fixes()
        text = self.box.read(os.path.join(".scratch", "demo", "loop.md")).replace("PR: ask at sign-off", "PR: no")
        self.box.write(os.path.join(".scratch", "demo", "loop.md"), text)
        result = self.fold()
        self.assertNext(result, "loop close --slug demo --write", "`PR: no`: `demo` stays local, nothing pushed.",
                        "stop")
        self.assertNotIn("vdd-create-pr", result.last)

    def test_a_loop_not_signed_off_is_refused(self):
        self.round_one()
        result = self.fold()
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("The code Loop is not signed off", result.text)
        self.assertNotIn("fold ", self.state())


class SkipTest(FoldTest):
    """Each case leaves the branch exactly as signed, records the skip, says
    why in one Tell line and goes on to the PR step."""

    def skipped(self, signed, result, reason):
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertEqual(self.sha("demo"), signed)
        tells = result.tells()
        self.assertEqual(len(tells), 1, result)
        self.assertIn("Not folded: demo stays exactly as the Code-Reviewer signed it off", tells[0])
        self.assertIn(reason, tells[0])
        self.assertIn("fold skipped %s " % signed, self.state())
        self.assertNext(result, "vdd-create-pr")
        commits = self.recap().split("## Commits")[1].split("## Not carried")[0]
        self.assertIn("Not folded: demo stays at the signed commit %s, because" % signed[:7], commits)
        self.assertIn("not folded: ", self.recap())

    def signed_loop(self):
        self.round_one()
        self.code_round([({CSV: fixed_return(T01)}, "fix(report): two decimals")])
        return self.code_round([], 0)

    @unittest.skipIf(WINDOWS, "a stubbed git is a POSIX sh script, as in PreflightTest")
    def test_git_older_than_2_40(self):
        signed = self.signed_loop()
        real = shutil.which("git")
        self.box.stub("git", "if [ \"$1\" = --version ]; then echo 'git version 2.39.5'; exit 0; fi\n"
                             "exec '%s' \"$@\"\n" % real)
        self.skipped(signed, self.fold(env=self.box.stub_env()), "git 2.39.5 is older than the 2.40")

    def test_a_commit_after_the_signed_commit(self):
        """Unreviewed work is never folded into reviewed commits."""
        signed = self.signed_loop()
        moved = self.commit_files({"x.txt": "x\n"}, "chore: after Sign-off")
        result = self.fold()
        self.assertEqual(self.sha("demo"), moved)
        self.assertIn("the branch moved after Sign-off", result.tells()[0])
        self.assertIn("fold skipped ", self.state())
        self.assertNext(result, "vdd-create-pr")
        self.assertEqual(signed, self.out("rev-parse", "demo~1"))

    def test_a_merge_commit_in_the_loop(self):
        self.round_one()
        self.git("checkout", "-q", "-b", "side")
        self.commit_files({"side.txt": "s\n"}, "feat: side")
        self.git("checkout", "-q", "demo")
        signed = self.code_round([], 0, steps=[lambda: self.git("merge", "-q", "--no-ff", "-m", "merge side", "side")])
        self.skipped(signed, self.fold(), "merge commit")

    def test_round_one_s_end_rewritten_away(self):
        """A loop started before this release, whose Coder folded each
        round, lands here and still reaches its PR."""
        self.round_one()
        self.git("commit", "-q", "--amend", "-m", T02_SUBJECT + " (amended)")
        self.code_round([({CSV: fixed_return(T01)}, "fix(report): two decimals")])
        signed = self.sha()
        lines = [line for line in self.state().split("\n") if line.startswith("code 2 ")]
        self.stage("code 2 reviewed signed-off - counts 0 0 0 next 2 new 0 closed 1 checks code-review ran")
        self.assertTrue(lines)
        self.skipped(signed, self.fold(), "round 1's end")

    def restart(self, start):
        """The state with round 1's start line replaced by start, or dropped
        when start is None."""
        path = self.box.path(".scratch", "demo", "loop-state")
        lines = [line for line in self.state().split("\n") if line and not line.startswith("code 1 start ")]
        if start:
            lines.append("code 1 start %s" % start)
        with open(path, "w") as handle:
            handle.write("".join(line + "\n" for line in lines))

    def test_round_one_s_start_not_recorded(self):
        """A loop with a lost start would rewrite commits from before it."""
        signed = self.signed_loop()
        self.restart(None)
        self.skipped(signed, self.fold(), "round 1's start is not recorded")

    def test_round_one_s_start_off_the_base_branch(self):
        """A start off the base branch's history would rewrite commits from
        before the loop."""
        signed = self.signed_loop()
        stray = self.out("commit-tree", "HEAD^{tree}", "-m", "stray")
        self.restart(stray)
        self.skipped(signed, self.fold(),
                     "round 1's start %s does not descend from the base branch's merge base" % stray[:7])

    def test_an_upstream_set(self):
        """Replaces the Coder's upstream test before its fold: a branch
        someone may have fetched is not rewritten under them."""
        signed = self.signed_loop()
        self.git("branch", "--set-upstream-to=main", "demo")
        self.skipped(signed, self.fold(), "has an upstream")

    def test_a_branch_pushed_without_an_upstream(self):
        """A branch pushed by hand without -u has no upstream, yet someone may
        have fetched it, and a rewrite would reject the next push."""
        signed = self.signed_loop()
        self.box.bare_origin(push=("main", "demo"))
        self.assertEqual(self.out("branch", "--format=%(upstream)", "--list", "demo"), "")
        self.skipped(signed, self.fold(), "demo was pushed to origin")

    def test_a_remote_branch_of_the_same_name_outside_the_loop_folds(self):
        """The acceptance run's origin held an older, unrelated branch of the
        loop's name, and the fold skipped as if the loop had been pushed."""
        signed = self.signed_loop()
        self.git("remote", "add", "origin", "https://example.invalid/demo.git")
        stray = self.out("commit-tree", "%s^{tree}" % self.out("merge-base", "main", signed), "-m", "unrelated")
        self.git("update-ref", "refs/remotes/origin/demo", stray)
        self.folded(signed, self.fold())

    def test_a_skip_on_pr_no_says_the_branch_stays_local(self):
        """The Tell line said the loop goes on to the PR while the Next: line
        closed the loop with nothing pushed."""
        signed = self.signed_loop()
        text = self.box.read(os.path.join(".scratch", "demo", "loop.md")).replace("PR: ask at sign-off", "PR: no")
        self.box.write(os.path.join(".scratch", "demo", "loop.md"), text)
        self.git("branch", "--set-upstream-to=main", "demo")
        result = self.fold()
        self.assertEqual(self.sha("demo"), signed)
        tells = result.tells()
        self.assertEqual(len(tells), 1, result)
        self.assertIn("The branch stays local.", tells[0])
        self.assertNotIn("goes on to the PR", tells[0])
        self.assertNext(result, "loop close --slug demo --write")

    @unittest.skipIf(WINDOWS, "a stubbed git is a POSIX sh script, as in PreflightTest")
    def test_a_tree_that_would_differ(self):
        """Replaces 0c8a25a's guardrail: the fold never moves the branch to a
        tree other than the one the Code-Reviewer signed off."""
        signed = self.signed_loop()
        real = shutil.which("git")
        self.box.stub("git", "if [ \"$1\" = diff-tree ] && [ \"$3\" = -r ]; then printf 'README.md\\0'; exit 0; fi\n"
                             "exec '%s' \"$@\"\n" % real)
        self.skipped(signed, self.fold(env=self.box.stub_env()), "would differ from the signed tree in: README.md")


@unittest.skipIf(WINDOWS, "stubbed git and gpg are POSIX sh scripts, as in PreflightTest")
class SandboxAndSigningTest(FoldTest):
    def signed_loop(self):
        self.round_one()
        self.code_round([({CSV: fixed_return(T01)}, "fix(report): two decimals"),
                         ({"README.md": README2}, README_SUBJECT)])
        return self.code_round([], 0)

    def gpg(self, body):
        path = self.box.stub("gpg", body)
        self.git("config", "commit.gpgSign", "true")
        self.git("config", "gpg.program", path)
        self.git("config", "user.signingKey", "TESTKEY")

    def assertRerun(self, result, signed):
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("A sandbox refused", result.text)
        self.assertNext(result, "Rerun", "loop fold --slug demo --harness claude-code --write", "outside the sandbox")
        self.assertEqual(self.sha("demo"), signed)
        self.assertNotIn("fold ", self.state())

    def test_a_refused_object_write_in_german_gets_the_rerun_line(self):
        """Acceptance, Codex on Windows: its sandbox refused the fold's object
        write with git's "insufficient permission", which git translates; on
        a German system that refusal read as a git error and the fold
        skipped."""
        signed = self.signed_loop()
        objects = os.path.join(self.box.proj, ".git", "objects")
        dirs = [root for root, _, _ in os.walk(objects)]
        for path in dirs:
            os.chmod(path, 0o555)
        try:
            result = self.fold(env=self.box.env(LANG="de_DE.UTF-8", LC_ALL="de_DE.UTF-8"))
        finally:
            for path in dirs:
                os.chmod(path, 0o755)
        self.assertRerun(result, signed)

    def test_a_signing_repository_keeps_every_folded_commit_signed(self):
        signed = self.signed_loop()
        originals = self.out("rev-list", "main..demo").split("\n")
        log = os.path.join(self.box.root, "gpg.log")
        self.gpg("cat >/dev/null\necho \"$@\" >> '%s'\n"
                 "printf '\\n[GNUPG:] SIG_CREATED D 1 8 00 0 0 0 X\\n' >&2\n"
                 "printf -- '-----BEGIN PGP SIGNATURE-----\\nfake\\n-----END PGP SIGNATURE-----\\n'\n" % log)
        result = self.fold()
        self.folded(signed, result)
        made = [sha for sha in self.out("rev-list", "main..demo").split("\n") if sha not in originals]
        self.assertTrue(made)
        for sha in made:
            self.assertIn("\ngpgsig ", self.out("cat-file", "commit", sha))
        with open(log) as handle:
            self.assertEqual(len(handle.read().strip().split("\n")), len(made))

    def test_a_refused_signature_gets_the_rerun_line(self):
        signed = self.signed_loop()
        self.gpg("cat >/dev/null\necho 'gpg: signing failed: Operation not permitted' >&2\nexit 2\n")
        result = self.fold()
        self.assertRerun(result, signed)
        self.assertIn("A sandbox refused git commit-tree inside the tool: ", result.text)
        self.assertNext(result, "tell the user git commit-tree was refused, and stop.")

    def test_another_signing_failure_is_a_skip(self):
        signed = self.signed_loop()
        self.gpg("cat >/dev/null\necho 'gpg: signing failed: No secret key' >&2\nexit 2\n")
        result = self.fold()
        self.assertEqual(result.code, 0, result)
        self.assertEqual(self.sha("demo"), signed)
        self.assertIn("signing a folded commit failed", result.tells()[0])
        self.assertIn("fold skipped ", self.state())

    def test_a_refused_update_ref_gets_the_rerun_line_in_lower_case(self):
        signed = self.signed_loop()
        real = shutil.which("git")
        self.box.stub("git", "if [ \"$1\" = update-ref ]; then\n"
                             "  echo 'fatal: cannot lock ref: operation not permitted' >&2; exit 1\nfi\n"
                             "exec '%s' \"$@\"\n" % real)
        result = self.fold(env=self.box.stub_env())
        self.assertRerun(result, signed)
        self.assertIn("A sandbox refused git update-ref inside the tool: ", result.text)
        self.assertNext(result, "tell the user git update-ref was refused, and stop.")

    def test_an_upper_case_refusal_marker_too(self):
        signed = self.signed_loop()
        real = shutil.which("git")
        self.box.stub("git", "if [ \"$1\" = update-ref ]; then\n"
                             "  echo 'fatal: Unable to create lock: Permission denied' >&2; exit 128\nfi\n"
                             "exec '%s' \"$@\"\n" % real)
        self.assertRerun(self.fold(env=self.box.stub_env()), signed)


STDLIB = T01.replace("import csv\n", "import csv  # stdlib\n")
NOTES = "ledger/notes.py"
USER_FINDINGS = "### minor: ledger/report_csv.py:1\n\nName the module's import.\n"
SIGNED_REVIEW = "# Code review, round 2\n\nSIGNED OFF. Nothing open.\n\n## New findings\n"
FOLDED_AFTER = "(folded after round 2)"


class SecondFoldTest(FoldTest):
    """A loop reopened by the user's findings folds again at its next Sign-off
    (loop 06 left its grading fixes on top as commits because the fold ran
    once, and the reopened round's review range showed the whole loop)."""

    def folded_once(self):
        """Round 1, a round-2 fix signed off, folded, and the user's finding
        added through the tool."""
        self.round_one()
        self.code_round([({CSV: fixed_return(T01)}, "fix(report): two decimals")], 0)
        signed = self.sha()
        first = self.fold()
        self.folded(signed, first)
        self.first_tip = self.sha("demo")
        self.box.write(os.path.join(".scratch", "demo", "CODEREVIEW.md"), SIGNED_REVIEW)
        self.box.write("findings.md", USER_FINDINGS)
        added = self.box.run("review", "add", "--slug", "demo", "--from", "findings.md", "--write")
        self.assertEqual(added.code, 0, added)
        return signed

    def round_three(self, files, message, reviewed=False, steps=()):
        """The reopened round, started through the tool, with its commit."""
        started = self.box.run("coder", "start", "--slug", "demo", "--write")
        self.assertEqual(started.code, 0, started)
        # coder start recorded the round's start; the commit and the end
        # follow as the Coder's work does.
        self.commit_files(files, message)
        self.stage("code 3 end %s" % self.sha())
        if reviewed:
            self.stage("code 3 reviewed signed-off - counts 0 0 0 next 3 new 0 closed 1 checks code-review ran")
        return self.sha()

    def test_the_second_fold_folds_the_reopened_rounds_fixes_into_their_tickets(self):
        self.folded_once()
        signed = self.round_three({CSV: STDLIB, NOTES: "VALUE = 1\n"}, "fix(report): name the import",
                                  reviewed=True)
        result = self.fold()
        subjects = self.folded(signed, result)
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])
        self.assertIn("# stdlib", self.at(T01_SUBJECT, CSV))
        self.assertIn("VALUE = 1", self.at(T01_SUBJECT, NOTES))
        self.assertIn(FOLDED_AFTER, result.text)
        self.assertIn("fold folded %s signed %s" % (self.sha("demo"), signed), self.state())
        commits = self.recap().split("## Commits")[1].split("## Not carried")[0]
        self.assertEqual(commits.count("Folded demo: "), 2, commits)
        self.assertIn(FOLDED_AFTER, commits)
        again = self.fold()
        self.assertIn("The loop demo is already folded", again.text)

    def test_the_reopened_round_is_reviewed_on_its_own_fixes_from_the_folded_tip(self):
        signed_two = self.folded_once()
        self.round_three({CSV: STDLIB}, "fix(report): name the import")
        started = self.box.run("review", "start", "--role", "Code-Reviewer", "--slug", "demo", "--write")
        self.assertEqual(started.code, 0, started)
        self.assertNotEqual(self.first_tip, signed_two)
        self.assertIn("Fixed point: %s, the branch as folded after round 2's Sign-off." % self.first_tip,
                      started.lines)
        self.assertTrue(any(line.startswith("Review range: %s...demo" % self.first_tip) for line in started.lines),
                        started)
        self.assertNotIn("No commits in this round's range", started.text)

    def test_a_fix_no_loop_commit_owns_stays_on_top_with_the_coders_message(self):
        self.folded_once()
        signed = self.round_three({"README.md": README3}, README_SUBJECT, reviewed=True)
        subjects = self.folded(signed, self.fold())
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT, README_SUBJECT])

    def test_a_branch_with_an_upstream_skips_the_second_fold(self):
        self.folded_once()
        signed = self.round_three({CSV: STDLIB}, "fix(report): name the import", reviewed=True)
        self.git("branch", "--set-upstream-to=main", "demo")
        result = self.fold()
        self.assertEqual(result.code, 0, result)
        self.assertEqual(self.sha("demo"), signed)
        self.assertIn("has an upstream", result.text)
        self.assertIn("fold skipped %s " % signed, self.state())

    def test_pr_open_and_the_orchestrator_wait_for_the_second_fold(self):
        self.folded_once()
        self.round_three({CSV: STDLIB}, "fix(report): name the import", reviewed=True)
        opened = self.box.run("pr", "open", "--slug", "demo", "--harness", "claude-code", "--path", "open",
                              "--write")
        self.assertNotEqual(opened.code, 0, opened)
        self.assertIn("The fold's outcome is not recorded for the code Sign-off", opened.text)
        self.stage("respawn Coder never", "orchestrator session 1", "spawn Code-Reviewer 3 session 1")
        placed = self.box.run("orchestrator", "return", "--role", "Code-Reviewer", "--slug", "demo",
                              "--harness", "claude-code")
        self.assertEqual(placed.code, 0, placed)
        self.assertIn("Fold: not run yet.", placed.lines)
        self.assertNext(placed, "loop fold --slug demo --harness claude-code --write")
        self.fold()
        opened = self.box.run("pr", "open", "--slug", "demo", "--harness", "claude-code", "--path", "open",
                              "--write")
        self.assertNotIn("The fold's outcome is not recorded", opened.text)

    def test_a_loop_whose_first_fold_skipped_folds_from_round_ones_end(self):
        self.round_one()
        self.code_round([({CSV: fixed_return(T01)}, "fix(report): two decimals")], 0)
        self.git("branch", "--set-upstream-to=main", "demo")
        first = self.fold()
        self.assertIn("fold skipped", self.state())
        self.git("branch", "--unset-upstream", "demo")
        self.box.write(os.path.join(".scratch", "demo", "CODEREVIEW.md"), SIGNED_REVIEW)
        self.box.write("findings.md", USER_FINDINGS)
        self.assertEqual(self.box.run("review", "add", "--slug", "demo", "--from", "findings.md", "--write").code, 0)
        signed = self.round_three({CSV: STDLIB}, "fix(report): name the import", reviewed=True)
        result = self.fold()
        subjects = self.folded(signed, result)
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])
        self.assertIn("(round 1)", result.text)
        self.assertNotIn(FOLDED_AFTER, result.text)
        self.assertIn("Not folded: ", first.text)

    def test_a_fold_after_a_skipped_one_folds_from_the_last_folded_tip(self):
        """A skip after a fold left the chain at round 1's pre-fold end, gone
        from the history, so every later fold skipped with a wrong reason."""
        self.folded_once()
        skipped = self.round_three({CSV: STDLIB}, "fix(report): name the import", reviewed=True)
        self.git("branch", "--set-upstream-to=main", "demo")
        self.fold()
        self.assertIn("fold skipped %s " % skipped, self.state())
        self.git("branch", "--unset-upstream", "demo")
        self.box.write(os.path.join(".scratch", "demo", "CODEREVIEW.md"),
                       SIGNED_REVIEW.replace("round 2", "round 3"))
        self.box.write("findings.md", USER_FINDINGS.replace("Name the module's import.", "Say why."))
        added = self.box.run("review", "add", "--slug", "demo", "--from", "findings.md", "--write")
        self.assertEqual(added.code, 0, added)
        started = self.box.run("coder", "start", "--slug", "demo", "--write")
        self.assertEqual(started.code, 0, started)
        self.commit_files({NOTES: "VALUE = 1\n"}, "fix(report): add the notes")
        signed = self.sha()
        self.stage("code 4 end %s" % signed,
                   "code 4 reviewed signed-off - counts 0 0 0 next 4 new 0 closed 1 checks code-review ran")
        result = self.fold()
        subjects = self.folded(signed, result)
        self.assertEqual(subjects, [T01_SUBJECT, T02_SUBJECT])
        self.assertIn("VALUE = 1", self.at(T01_SUBJECT, NOTES))
        self.assertIn(FOLDED_AFTER, result.text)


if __name__ == "__main__":
    unittest.main()
