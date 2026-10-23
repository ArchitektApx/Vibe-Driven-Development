"""The helps: a group's, one command's, the usage lines they carry, and the
tool's own; and a command from each group run below the repository root."""

import os
import re
import unittest

from scenes import CC, SLUG, Staged
from test_entry import TAKES
from vddtest import REPO, ToolTest

ROOT_LINE = "Run every command from the repository root."

# Every command of a group of several, in the order its help prints them.
COMMANDS = {}
for _group, *_rest in TAKES:
    if _rest:
        COMMANDS.setdefault(_group, []).append(_rest[0])

# The options a usage line may leave out, each read from a sentence its help
# carries: (group, the commands it covers or None for all, the sentence, the
# options). A sentence that says a command takes no option is checked the
# other way: the command must refuse it.
LEFT_OUT = [
    ("brainstorm", None, "Every write needs --write", {"write"}),
    ("loop", None, "--harness names the Harness this Session runs in", {"harness"}),
    ("loop", ("set",), "The feature, the base branch and the feature branch never change.",
     {"feature", "base-branch", "feature-branch", "base", "branch"}),
]
TAKES_NONE = [
    ("orchestrator", ("start", "return", "tokens"), "start, return and tokens ring, spawn and resume nothing, "
     "and take no --write", {"write"}),
]


def body(result):
    """The help's lines without its Next: line."""
    return result.lines[:-1]


def usage(block):
    """The usage lines at the top of a command's block: every line before
    the first description line, which is indented by two spaces."""
    lines = []
    for line in block:
        if re.match(r"^  \S", line) or not line:
            break
        lines.append(line)
    return lines


def prose(lines):
    """The help's lines as one text, so a sentence wrapped over two lines
    is found whole."""
    return " ".join(line.strip() for line in lines)


class HelpTest(ToolTest):
    def help(self, *argv):
        result = self.box.run(*argv, "--help")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        return result

    def blocks(self, group):
        """Each command's help without the group-wide lines every command's
        help ends with (after a blank line), and those lines."""
        outputs = {name: body(self.help(group, name)) for name in COMMANDS[group]}
        if len(outputs) == 1:
            return outputs, []
        size = 0
        while all(len(lines) > size for lines in outputs.values()) and len(
                {tuple(lines[len(lines) - size - 1:]) for lines in outputs.values()}) == 1:
            size += 1
        tail = next(iter(outputs.values()))[-size:] if size else []
        return {name: lines[:len(lines) - size] for name, lines in outputs.items()}, tail

    @staticmethod
    def own(lines, rest):
        """lines split into the command's own block, as the group's help
        prints it in rest, and the group-wide lines that follow it. The
        block ends at the first blank line that a usage or description line
        does not follow, so the last block stops where the group-wide lines
        begin."""
        start = rest.index(lines[0])
        group = lines[0].split()[0] + " "
        size = 0
        while size < len(lines) and start + size < len(rest) and lines[size] == rest[start + size]:
            if size and not lines[size] and size + 1 < len(lines) and not lines[size + 1].startswith((" ", group)):
                break
            size += 1
        if size < len(lines) and not lines[size - 1]:
            size -= 1
        return lines[:size], lines[size:]

    def test_a_command_s_help_prints_its_block_the_group_wide_lines_and_its_next(self):
        """A Role read a whole group's help, every command of it, to run one;
        a command's help prints that command alone, then the group-wide
        lines that apply to it, each one a group-wide line or a part of them
        worded for that command alone, and the group's help stays the sum of
        the blocks and the group-wide lines."""
        tool = self.tool()
        for group, names in COMMANDS.items():
            with self.subTest(group=group):
                whole = body(self.help(group))
                outputs, tail = self.blocks(group)
                rest = whole[:len(whole) - len(tail)]
                blocks = {}
                for name in names:
                    result = self.help(group, name)
                    block, scoped = self.own(outputs[name], rest)
                    blocks[name] = block
                    self.assertTrue(block[0].startswith("%s %s" % (group, name)), result)
                    others = [n for n in names if n != name]
                    self.assertFalse([line for line in block if re.match(r"^%s (%s)\b" % (
                        group, "|".join(map(re.escape, others))), line)] if others else [], result)
                    if scoped:
                        self.assertEqual(scoped[0], "", result)
                    self.assertEqual(result.last, "Next: Run %s %s %s with the options above." % (tool, group, name),
                                     result)
                if tail:
                    self.assertEqual(tail[0], "", group)
                    self.assertEqual(whole[len(whole) - len(tail):], tail, group)
                joined = [line for name in names for line in blocks[name]]
                apart = [line for index, name in enumerate(names) for line in [""] * bool(index) + blocks[name]]
                printed = joined if rest[:len(joined)] == joined else apart
                self.assertEqual(rest[:len(printed)], printed, group)
                wide = rest[len(printed):]
                if wide:
                    self.assertEqual(wide[0], "", group)
                said = " ".join(wide)
                for name in names:
                    scoped = self.own(outputs[name], rest)[1]
                    self.assertFalse([line for line in scoped if line and line not in wide
                                      and line.rstrip(".;") not in said], (group, name))

    def test_a_group_wide_line_about_other_commands_stays_out_of_a_command_s_help(self):
        """loop close --help printed the accepted values of --minors, --pr
        and --harness-line, options close does not take, and doorbell take
        --help said ring and wait refuse on a closed loop; a group-wide line
        that names commands is printed in their help alone."""
        self.assertNotIn("Accepted values", self.help("loop", "close").text)
        self.assertNotIn("Accepted values", self.help("loop", "show").text)
        self.assertIn("Accepted values", self.help("loop", "new").text)
        self.assertIn("Accepted values", self.help("loop", "set").text)
        self.assertIn("Accepted values", self.help("loop").text)
        self.assertNotIn("refuse on a closed loop", self.help("doorbell", "take").text)
        self.assertIn("refuse on a closed loop", self.help("doorbell", "ring").text)
        self.assertIn("refuse on a closed loop", self.help("doorbell").text)

    def test_a_command_s_help_names_no_option_or_command_it_does_not_take(self):
        """loop new --help listed the accepted values of --harness-line,
        which loop new refuses, and orchestrator respawn --help said what
        start, return and tokens do; the group's help still prints both."""
        self.assertNotIn("--harness-line", self.help("loop", "new").text)
        self.assertIn("--harness-line", self.help("loop", "set").text)
        self.assertIn("--harness-line", self.help("loop").text)
        respawn = self.help("orchestrator", "respawn").text
        self.assertNotIn("start, return and tokens", respawn)
        self.assertIn("--slug names the loop; pass it on every call.", respawn)
        self.assertIn("start, return and tokens", self.help("orchestrator").text)
        self.assertIn("start, return and tokens", self.help("orchestrator", "tokens").text)

    def test_help_refuses_a_value_outside_its_choices(self):
        """A printed line with a mistyped choice passed the check that runs
        every printed command with --help, and was refused only when a Role
        ran it; --help still needs no required option."""
        result = self.box.run("pr", "open", "--path", "opne", "--help")
        self.assertNotEqual(result.code, 0, result)
        self.assertEqual(result.lines[0], "--path takes open, push-only or existing, not opne.", result)
        self.help("pr", "open")

    def tool(self):
        """The tool's path as the tool prints it, the interpreter included."""
        result = self.help()
        found = re.match(r"Next: Run (.*?) <group> --help", result.last)
        self.assertIsNotNone(found, result)
        assert found is not None
        return found.group(1)

    def test_no_group_help_says_to_run_from_the_repository_root_but_setup_s(self):
        """Every group finds the repository itself, so a help that told the
        Role to run from the root stated a false rule; Setup refuses below
        the root, so its line stays."""
        for group in COMMANDS:
            with self.subTest(group=group):
                self.assertNotIn(ROOT_LINE, prose(body(self.help(group))))
        self.assertIn("Run it from the repository root.", prose(body(self.help("setup"))))

    def test_each_usage_line_names_exactly_the_options_its_command_takes(self):
        """A usage line is written by hand, beside a spec that parses: the
        orchestrator's respawn and tokens took --harness while their usage
        lines left it out. Every option a command takes is on its usage
        line, or left out by a sentence the help says it in."""
        for group, names in COMMANDS.items():
            blocks, tail = self.blocks(group)
            text = prose(body(self.help(group)))
            for name in names:
                with self.subTest(command="%s %s" % (group, name)):
                    takes = set(TAKES[(group, name)].split())
                    named = set(re.findall(r"--([a-z][a-z-]*)", " ".join(usage(blocks[name]))))
                    left = set()
                    for where, commands, sentence, options in LEFT_OUT:
                        if where == group and (commands is None or name in commands):
                            self.assertIn(sentence, text)
                            left |= options & takes
                    for where, commands, sentence, options in TAKES_NONE:
                        if where == group and name in commands:
                            self.assertIn(sentence, text)
                            self.assertFalse(options & takes, name)
                    self.assertEqual(named - takes, set(), "named on the usage line, not taken")
                    self.assertEqual(takes - named - left, set(), "taken, not on the usage line")

    def test_the_tool_s_help_names_a_group_s_and_a_command_s_help(self):
        """The top-level Next: sent a Role to "the group your skill names",
        a group no skill names once the skills point at a command's help."""
        result = self.help()
        self.assertIn('vdd.py" <group> --help', result.last)
        self.assertIn('vdd.py" <group> <command> --help', result.last)
        self.assertNotIn("your skill names", result.last)

    def test_a_refusal_names_its_command_s_help(self):
        result = self.box.run("loop", "new", *CC)
        self.assertNotEqual(result.code, 0, result)
        self.assertIn('vdd.py" loop new --help for this command\'s usage.', result.last)


SKILL_DIR = os.path.join(REPO, "skills", "vdd-wayfinder")


def wayfinder_map(t):
    t.repo()
    t.box.write(os.path.join(".scratch", "demo", "map.md"), "# Map\n")


def pr_template(t):
    """Code signed off on PR: no, with a PR template, so pr check reads no
    PR history through gh."""
    t.code_signed(pr="no")
    t.box.write(os.path.join(".github", "pull_request_template.md"), "## Summary\n")


def planner_rang(t):
    t.plan()
    t.run_ok("doorbell", "ring", "--role", "Planner", *CC, *SLUG, "--write")


S = Staged

# One read-only command per group, (group, scene, argv). setup refuses below
# the root and has its own test; codex-stop has no command a Role runs.
BELOW_ROOT = [
    ("loop", S.plan, ("loop", "show", *SLUG)),
    ("doorbell", S.plan, ("doorbell", "ring", "--role", "Planner", *CC, *SLUG)),
    ("pr", pr_template, ("pr", "check", *SLUG, *CC)),
    ("coder", S.signed, ("coder", "start", *SLUG)),
    ("review", planner_rang, ("review", "start", "--role", "Plan-Reviewer", *SLUG)),
    ("orchestrator", S.plan, ("orchestrator", "respawn", "--role", "Coder", "--once", *SLUG)),
    ("wayfinder", wayfinder_map, ("wayfinder", "start", "--effort", "demo", "--skill-dir", SKILL_DIR)),
    ("brainstorm", S.store, ("brainstorm", "start")),
]


class BelowRootTest(Staged):
    def check_below(self, scene, argv):
        scene(self)
        sub = self.box.path("src", "deep")
        os.makedirs(sub)
        at_root = self.box.run(*argv)
        self.assertEqual(at_root.code, 0, at_root)
        below = self.box.run(*argv, cwd=sub)
        self.assertEqual(below.code, 0, below)
        self.assertEqual(below.text, at_root.text)
        self.assertFalse(os.path.exists(os.path.join(sub, ".scratch")))

    def test_setup_refuses_below_the_root(self):
        """Setup's checks and writes are relative to the working directory,
        so it refuses below the root and names the root."""
        self.repo()
        sub = self.box.path("src", "deep")
        os.makedirs(sub)
        result = self.box.run("setup", *CC, "--listed", "none", "--glossary-named", "absent", cwd=sub)
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("The repository root: " + self.box.proj, result.text)


def make_below(row):
    group, scene, argv = row

    def test(self):
        self.check_below(scene, argv)

    test.__doc__ = ("Prevents a %s command that acts on the working directory instead of the repository: run "
                    "below the root, it prints what it prints at the root." % group)
    return test


for _row in BELOW_ROOT:
    setattr(BelowRootTest, "test_a_%s_command_below_the_root_acts_as_at_the_root" % _row[0], make_below(_row))

del S


if __name__ == "__main__":
    unittest.main()
