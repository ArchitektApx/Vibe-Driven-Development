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

    def start(self, effort="demo", skill_dir=SKILL_DIR):
        return self.box.run("wayfinder", "start", "--effort", effort, "--skill-dir", skill_dir)

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
        found = self.install(".claude", "plugins", "cache", "x")
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
        """Acceptance: the Feature-slug check refused beta-0.16.0-work, an
        effort whose map the Wayfinder on beta still opened. A slug that
        could leave .scratch/ stays refused."""
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
