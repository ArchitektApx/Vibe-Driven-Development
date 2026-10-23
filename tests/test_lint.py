"""The open-findings search every command shares, and the lint collector of
the framed Working files, driven through vdd.py."""

import unittest

from scenes import FINDINGS, SLUG, Staged


class MissingFinding(Staged):
    """Each command words its own refusal for an open finding whose text the
    review file and the carried file have both lost."""

    def refused(self, argv, fragment):
        result = self.box.run(*argv, env=self.env())
        self.assertEqual(result.code, 1, result)
        self.assertIn(fragment, result.lines[0])
        self.assertTrue(result.last.startswith("Next: "), result)
        return result

    def test_coder_start(self):
        """Prevents coder start framing a round with no entry for an open
        finding."""
        self.round_two()
        self.put("CODEREVIEW.md", self.read("CODEREVIEW.md").replace("### 1. major (open): a.txt:1\n", ""))
        self.refused(("coder", "start", *SLUG, "--write"), "CODEREVIEW.md has no heading for finding 1")

    def test_review_start(self):
        """Prevents review start carrying a finding whose text is gone."""
        self.code_round_two_answered()
        self.put("CODEREVIEW.md", self.read("CODEREVIEW.md").replace("### 1. major (open): a.txt:1\n", ""))
        self.refused(("review", "start", "--role", "Code-Reviewer", *SLUG, "--write"),
                     ".scratch/demo/CODEREVIEW.md no longer holds finding 1")

    def test_review_add(self):
        """Prevents a second add rewriting CODEREVIEW.md without a finding of
        the open user entry."""
        self.folded()
        self.box.write("findings.md", FINDINGS)
        self.run_ok("review", "add", *SLUG, "--from", "findings.md", "--write")
        self.put("CODEREVIEW.md", self.read("CODEREVIEW.md").replace("### 1. major (open): docs/a.md:3\n", ""))
        self.box.write("more.md", "### blocker: src/c.py:1\n\nIt crashes.\n")
        self.refused(("review", "add", *SLUG, "--from", "more.md", "--write"),
                     ".scratch/demo/CODEREVIEW.md no longer holds the heading of finding 1")


class LintOrder(Staged):
    def test_problems_in_line_order_with_file_and_line(self):
        """Prevents a linter printing its problems in the order it found
        them: line 9's problem is found first, line 3's printed first."""
        self.coder_started()
        self.put("FIXES.md", "# Fixes, round 1\n\n## Ticket 01: 01-one.md\n\nChange: a\nVerified: b\n\ntext\n"
                 "## Bogus heading\n\n## Ticket 02: 02-two.md\n\nFiles: a\nChange: b\nVerified: c\n")
        result = self.box.run("coder", "check", *SLUG, "--write", env=self.env())
        self.assertEqual(result.code, 1, result)
        self.assertTrue(result.lines[0].startswith("FIXES.md line 3: Ticket 01 has no Files: line."), result)
        self.assertTrue(result.lines[1].startswith('FIXES.md line 9: "## Bogus heading" is not an entry'), result)
        self.assertEqual(result.lines[2], "Nothing written.")


if __name__ == "__main__":
    unittest.main()
