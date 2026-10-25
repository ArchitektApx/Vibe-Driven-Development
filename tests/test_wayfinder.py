"""The wayfinder command group, driven from outside: the Wayfinder's start."""

import os
import shutil
import unittest

from vddtest import REPO, ToolTest

SKILL_DIR = os.path.join(REPO, "skills", "vdd-wayfinder")

# The briefing block as the Wayfinder's SKILL.md carried it before the tool
# printed it, its placeholders unfilled.
BRIEFING = """Briefing for the wayfinding of <effort>:

- This project uses Vibe Driven Development (VDD). Each loop is one coherent
  change: a Planner grills the user and writes a Spec and Tickets, a
  Plan-Reviewer reviews the plan in rounds, a Coder implements, a
  Code-Reviewer reviews the code in rounds, each in its own context. Every
  loop does its own grilling and planning. The wayfinding settles the big
  picture and nothing about a loop's inner workings.
- Destination: the handoffs under .scratch/<effort>/handoffs/, one
  00-overview.md from <path to overview-template.md> and one NN-<slug>.md per
  loop from <path to handoff-template.md>. The map is done when those files
  exist and nothing is left to decide before loop 01 starts.
- Loops are cut by coherence, the way to-tickets cuts tickets: what belongs
  together lands together. Size is not the cut; a loop that turns out too
  large is caught by its Planner, who asks the user to split it.
- Carry these three points into the map's Notes section, so every later
  wayfinding session reads them."""


class WayfinderTest(ToolTest):
    def setUp(self):
        ToolTest.setUp(self)
        self.box.init_git("main")

    def start(self, effort="demo", skill_dir=SKILL_DIR, env=None):
        return self.box.run("wayfinder", "start", "--effort", effort, "--skill-dir", skill_dir, env=env)

    def install(self, *parts):
        path = os.path.join(self.box.home, *(list(parts) + ["wayfinder", "SKILL.md"]))
        self.box.write(path, "---\nname: wayfinder\n---\n", base=self.box.root)
        return path

    def briefing(self, result):
        start = result.lines.index("Briefing for the wayfinding of demo:")
        return "\n".join(result.lines[start:-1])

    def test_found_with_no_map_prints_the_filled_briefing(self):
        """The Wayfinder searched six store roots and filled both template
        paths by hand; the tool does both, and the briefing has one source."""
        found = self.install(".claude", "plugins", "cache", "mattpocock", "mattpocock-skills", "1.0.0", "skills")
        result = self.start()
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("Map: .scratch/demo/map.md does not exist.", result.lines)
        self.assertIn("wayfinder: %s" % found, result.lines)
        overview = os.path.join(SKILL_DIR, "references", "overview-template.md")
        handoff = os.path.join(SKILL_DIR, "references", "handoff-template.md")
        for path in (overview, handoff):
            self.assertTrue(os.path.isabs(path) and os.path.isfile(path))
        expected = BRIEFING.replace("<effort>", "demo").replace("<path to overview-template.md>", overview).replace(
            "<path to handoff-template.md>", handoff)
        self.assertEqual(self.briefing(result), expected)
        self.assertNext(result, "Ask the user what the effort is")
        self.assertEqual(result.tells(), [])

    def test_a_map_is_reported_and_the_briefing_still_printed(self):
        self.install(".agents", "skills")
        self.box.write(os.path.join(".scratch", "demo", "map.md"), "# Map\n")
        result = self.start()
        self.assertEqual(result.code, 0, result)
        self.assertIn("Map: .scratch/demo/map.md exists.", result.lines)
        self.assertIn("Briefing for the wayfinding of demo:", result.lines)
        self.assertNext(result, "## Notes of .scratch/demo/map.md", "three points")

    def test_a_project_store_counts(self):
        found = os.path.join(self.box.proj, ".claude", "skills", "wayfinder", "SKILL.md")
        self.box.write(found, "x\n")
        result = self.start()
        self.assertIn("wayfinder: %s" % found, result.lines)

    def test_found_in_every_store_setup_searches(self):
        """The Wayfinder searched six roots of its own and told the user to
        stop for a wayfinder Setup reported as Present: one in Cursor's or
        Copilot's store, in a plugin cache, or under a relocation variable."""
        root = self.box.root
        cache = ("plugins", "cache", "mk", "mattpocock-skills", "1.0", "skills")
        places = [
            ("~", (".claude", "skills"), None),
            (".", (".claude", "skills"), None),
            ("~", (".claude",) + cache, None),
            (root, ("cfg", "skills"), {"CLAUDE_CONFIG_DIR": os.path.join(root, "cfg")}),
            (root, ("pc", "cache", "mk", "mattpocock-skills", "1.0", "skills"),
             {"CLAUDE_CODE_PLUGIN_CACHE_DIR": os.path.join(root, "pc")}),
            ("~", (".agents", "skills"), None),
            (".", (".agents", "skills"), None),
            ("~", (".codex", "skills"), None),
            (".", (".codex", "skills"), None),
            ("~", (".codex",) + cache, None),
            (root, ("ch", "skills"), {"CODEX_HOME": os.path.join(root, "ch")}),
            (root, ("ch",) + cache, {"CODEX_HOME": os.path.join(root, "ch")}),
            ("~", (".cursor", "skills"), None),
            (".", (".cursor", "skills"), None),
            ("~", (".cursor",) + cache, None),
            ("~", (".copilot", "skills"), None),
            (".", (".github", "skills"), None),
            ("~", (".copilot", "installed-plugins", "mk", "mattpocock-skills", "skills"), None),
            (root, ("cp", "skills"), {"COPILOT_HOME": os.path.join(root, "cp")}),
            (root, ("cp", "installed-plugins", "_direct", "src-1", "skills"),
             {"COPILOT_HOME": os.path.join(root, "cp")}),
        ]
        for base, parts, variables in places:
            directory = self.box.home if base == "~" else self.box.proj if base == "." else base
            found = os.path.join(directory, *(parts + ("wayfinder", "SKILL.md")))
            with self.subTest(store=found):
                self.box.write(found, "---\nname: wayfinder\n---\n", base=self.box.root)
                try:
                    result = self.start(env=self.box.env(**(variables or {})))
                    self.assertEqual(result.code, 0, result)
                    self.assertIn("wayfinder: %s" % found, result.lines)
                    self.assertEqual(result.tells(), [])
                finally:
                    os.remove(found)

    def test_claude_code_s_staged_clone_is_no_install(self):
        """Claude Code stages a marketplace clone as cache/temp_git_*; Setup
        does not count it, so the Wayfinder does not either."""
        self.install(".claude", "plugins", "cache", "temp_git_1", "skills", "engineering")
        result = self.start()
        self.assertEqual(len(result.tells()), 1, result)
        self.assertIn("~/.claude/plugins/cache/*/mattpocock-skills", result.text)

    def test_the_refusal_names_the_roots_it_searched(self):
        result = self.start(env=self.box.env(CODEX_HOME=os.path.join(self.box.root, "ch")))
        line = [line for line in result.lines if line.startswith("wayfinder: not installed: ")]
        self.assertEqual(len(line), 1, result)
        for root in ("~/.claude/skills", "./.agents/skills", "~/.cursor/plugins/cache", "./.github/skills",
                     "~/.copilot/installed-plugins", os.path.join(self.box.root, "ch", "plugins", "cache")):
            self.assertIn(root, line[0])
        self.assertNotIn("~/.codex/", line[0])

    def test_no_wayfinder_tells_the_user_to_invoke_vdd_setup(self):
        result = self.start()
        self.assertContract(result)
        tells = result.tells()
        self.assertEqual(len(tells), 1, result)
        self.assertIn("vdd-setup", tells[0])
        self.assertIn("Briefing for the wayfinding of demo:", result.lines)

    def test_a_missing_template_is_refused_by_name(self):
        copy = os.path.join(self.box.root, "wayfinder-skill")
        shutil.copytree(SKILL_DIR, copy)
        os.remove(os.path.join(copy, "references", "handoff-template.md"))
        self.install(".agents", "skills")
        result = self.start(skill_dir=copy)
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("references/handoff-template.md", result.text)
        self.assertNotIn("Briefing for the wayfinding", result.text)

    def test_an_effort_slug_with_a_space_is_refused(self):
        result = self.start(effort="two words")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("Not an effort slug: two words", result.text)

    def test_an_effort_named_with_a_version_finds_its_map(self):
        """Prevents an effort named with a version, with dots between its
        words, refused although an older Wayfinder opened its map. A slug
        that could leave .scratch/ stays refused."""
        self.install(".agents", "skills")
        self.box.write(os.path.join(".scratch", "beta-0.16.0-work", "map.md"), "# Map\n")
        result = self.start(effort="beta-0.16.0-work")
        self.assertEqual(result.code, 0, result)
        self.assertIn("Map: .scratch/beta-0.16.0-work/map.md exists.", result.lines)
        for bad in ("..", "../x", ".hidden", "a..b", "a."):
            with self.subTest(effort=bad):
                result = self.start(effort=bad)
                self.assertNotEqual(result.code, 0, result)
                self.assertIn("Not an effort slug", result.text)

    def test_it_writes_nothing(self):
        self.install(".agents", "skills")
        before = sorted(os.listdir(self.box.proj))
        self.start()
        self.assertEqual(sorted(os.listdir(self.box.proj)), before)


if __name__ == "__main__":
    unittest.main()
