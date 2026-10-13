"""Seam 1: the setup command, driven from outside."""

import os
import shutil
import stat
import subprocess
import unittest

from vddtest import SCRIPTS, WINDOWS, ToolTest
import vddtest

SKILLS = (
    "setup-matt-pocock-skills", "grill-with-docs", "improve-codebase-architecture", "to-spec",
    "to-tickets", "wayfinder", "code-review", "writing-for-agents", "grilling", "domain-modeling",
    "codebase-design", "research", "prototype",
)
INSTALL_CLAUDE = "/plugin marketplace add mattpocock/skills"


class SetupTest(ToolTest):
    def setUp(self):
        ToolTest.setUp(self)
        subprocess.run(["git", "init", "-q"], cwd=self.box.proj, check=True)

    def setup(self, harness="claude-code", listed="", glossary="absent", *extra, env=None, cwd=None):
        args = ["setup", "--harness", harness, "--listed", listed, "--glossary-named", glossary] + list(extra)
        return self.box.run(*args, env=env, cwd=cwd)

    def skills_in(self, store, names=SKILLS):
        for name in names:
            self.box.write(os.path.join(store, name, "SKILL.md"), "---\nname: %s\n---\n" % name, base=self.box.root)

    def store(self, *parts):
        """A path under the sandbox's home, relative to the sandbox root."""
        return os.path.join("home", *parts)

    def proj_files(self):
        return sorted(os.listdir(self.box.proj))

    def route_lines(self, result):
        return [t for t in result.tells() if "npx skills" in t or "/plugin" in t or "plugin " in t]

    # --- Borrowed skills ---

    def test_nothing_present_nothing_listed_gives_one_install_route_and_changes_nothing(self):
        result = self.setup()
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("Not Present: " + ", ".join(SKILLS), result.text)
        installs = [t for t in result.tells() if INSTALL_CLAUDE in t]
        self.assertEqual(len(installs), 1, result)
        self.assertTrue(any("blocks the Planner" in t for t in result.tells()))
        self.assertTrue(any("docs/agents/issue-tracker.md" in l for l in result.lines))
        self.assertTrue(any("Code-Reviewer (code-review) are blocked" in t for t in result.tells()))
        self.assertIn("Planned change: .gitignore adds LOOP.md", result.text)
        self.assertIn("Planned change: .gitignore adds .scratch/", result.text)
        self.assertIn("Planned change: install the VDD tool", result.text)
        self.assertNext(result, "--write")
        self.assertEqual(self.proj_files(), [".git"])
        self.assertEqual(os.listdir(self.box.data), [])

    def test_writing_for_agents_listed_with_no_hit_is_resolvable_in_one_line(self):
        """Resolvable with no search hit passes: the collection resolves from a
        store Setup does not search, and gets no repair (180854c)."""
        for listed in ("writing-for-agents", "mattpocock-skills:writing-for-agents"):
            with self.subTest(listed=listed):
                result = self.setup(listed=listed, glossary="yes")
                lines = [t for t in result.tells() if "Resolvable from a store Setup does not search" in t]
                self.assertEqual(len(lines), 1, result)
                self.assertTrue(lines[0].startswith(", ".join(SKILLS) + ":"), result)
                self.assertTrue(lines[0].endswith("Passed."), result)
                self.assertEqual(self.route_lines(result), [], result)
                self.assertNotIn("Not Present", result.text)

    def test_nothing_listed_survives_a_shell_that_drops_the_empty_argument(self):
        """Windows PowerShell 5.1 drops an empty argument to a native program,
        so --listed '' arrives as --listed --glossary-named absent."""
        dropped = self.box.run("setup", "--harness", "claude-code", "--listed", "--glossary-named", "absent")
        self.assertNotEqual(dropped.code, 0, dropped)
        self.assertContract(dropped)
        self.assertIn("--listed has no value: the next argument is --glossary-named.", dropped.text)
        self.assertNotIn("Unexpected argument", dropped.text)
        empty = self.setup(listed="")
        for listed in ("none", "", "="):
            with self.subTest(listed=listed):
                if listed == "=":
                    result = self.box.run("setup", "--harness", "claude-code", "--listed=", "--glossary-named", "absent")
                else:
                    result = self.setup(listed=listed)
                self.assertEqual(result.code, 0, result)
                self.assertEqual(result.text, empty.text)
                self.assertNext(result, " --listed none --glossary-named absent ")

    def test_a_sibling_hit_answers_for_all_but_writing_for_agents(self):
        result = self.setup(listed="grilling")
        self.assertIn("Not Present: writing-for-agents.", result.text)
        self.assertTrue(any(INSTALL_CLAUDE in t for t in result.tells()), result)

    def test_present_and_resolvable_passes_with_no_repair(self):
        self.skills_in(self.store(".claude", "skills"))
        result = self.setup(listed="writing-for-agents", glossary="yes")
        self.assertIn("Borrowed skills: all 13 Present and Resolvable. Passed.", result.text)
        self.assertEqual(self.route_lines(result), [], result)

    def test_present_with_nothing_listed_asks_the_user_to_invoke_writing_for_agents(self):
        self.skills_in(self.store(".claude", "skills"))
        result = self.setup()
        self.assertNext(result, "/writing-for-agents", "--user-answer resolves", "does-not-resolve")
        self.assertEqual(self.route_lines(result), [], result)

    def test_the_users_answer_resolves(self):
        self.skills_in(self.store(".claude", "skills"))
        result = self.setup("claude-code", "", "absent", "--user-answer", "resolves")
        self.assertIn("all 13 Present and Resolvable", result.text)

    def test_present_but_not_resolvable_gives_the_route_for_the_store(self):
        self.skills_in(self.store(".claude", "skills"))
        result = self.setup("claude-code", "", "absent", "--user-answer", "does-not-resolve")
        self.assertIn("Present but not Resolvable, under ~/.claude/skills", result.text)
        self.assertEqual(
            self.route_lines(result),
            ["Re-run the install and select Claude Code: npx skills@latest add -g mattpocock/skills, "
             "then start a new Claude Code Session."],
        )

    def test_project_store_route_drops_the_g(self):
        self.skills_in(os.path.join("proj", ".claude", "skills"))
        result = self.setup("claude-code", "", "absent", "--user-answer", "does-not-resolve")
        self.assertIn("under ./.claude/skills", result.text)
        self.assertTrue(any("npx skills@latest add mattpocock/skills (no -g" in t for t in result.tells()), result)

    def test_plugin_cache_route_names_the_marketplace(self):
        self.skills_in(self.store(".claude", "plugins", "cache", "mattpocock", "mattpocock-skills", "1.3.1", "skills", "engineering"))
        result = self.setup("claude-code", "", "absent", "--user-answer", "does-not-resolve")
        self.assertTrue(any("claude plugin enable mattpocock-skills@mattpocock" in t for t in result.tells()), result)

    def test_temp_git_clone_in_the_claude_cache_never_counts(self):
        """Claude Code stages a marketplace clone as cache/temp_git_*, laid out
        as the collection's own repository; the cache root stops at
        */mattpocock-skills so that copy is not Present (180854c)."""
        self.skills_in(self.store(".claude", "plugins", "cache", "temp_git_123", "skills", "engineering"))
        result = self.setup()
        self.assertIn("Not Present: " + ", ".join(SKILLS), result.text)

    def test_a_symlinked_skills_cli_install_counts(self):
        """A global skills-CLI install for Claude Code writes the real copy to
        ~/.agents/skills and a symlink at ~/.claude/skills; the search follows
        it (180854c, find -L)."""
        self.skills_in(self.store(".agents", "skills"))
        os.makedirs(os.path.join(self.box.home, ".claude", "skills"))
        for name in SKILLS:
            try:
                os.symlink(
                    os.path.join(self.box.home, ".agents", "skills", name),
                    os.path.join(self.box.home, ".claude", "skills", name),
                    target_is_directory=True,
                )
            except (OSError, NotImplementedError) as error:
                self.skipTest("cannot create a symlink here: %s" % error)
        result = self.setup(listed="writing-for-agents", glossary="yes")
        self.assertIn("all 13 Present and Resolvable", result.text)

    def test_a_dangling_symlink_reads_as_absent(self):
        os.makedirs(os.path.join(self.box.home, ".claude", "skills"))
        try:
            os.symlink(os.path.join(self.box.root, "gone"), os.path.join(self.box.home, ".claude", "skills", "grilling"))
        except (OSError, NotImplementedError) as error:
            self.skipTest("cannot create a symlink here: %s" % error)
        result = self.setup()
        self.assertIn("Not Present: " + ", ".join(SKILLS), result.text)

    def test_claude_config_dir_moves_the_user_store_and_the_cache(self):
        """CLAUDE_CONFIG_DIR and CLAUDE_CODE_PLUGIN_CACHE_DIR move what Claude
        Code reads, and the search moves with them (180854c)."""
        self.skills_in(os.path.join("cfg", "skills"))
        env = self.box.env(CLAUDE_CONFIG_DIR=os.path.join(self.box.root, "cfg"))
        result = self.setup("claude-code", "writing-for-agents", "yes", env=env)
        self.assertIn("all 13 Present and Resolvable", result.text)
        self.skills_in(self.store(".claude", "skills"))
        result = self.setup("claude-code", "", "absent", "--user-answer", "does-not-resolve", env=env)
        self.assertNotIn("~/.claude/skills", result.text)
        shutil.rmtree(os.path.join(self.box.home, ".claude"))
        cache = os.path.join(self.box.root, "pc")
        self.skills_in(os.path.join("pc", "cache", "mk", "mattpocock-skills", "x"))
        env = self.box.env(CLAUDE_CODE_PLUGIN_CACHE_DIR=cache)
        result = self.setup("claude-code", "", "absent", "--user-answer", "does-not-resolve", env=env)
        self.assertTrue(any("mattpocock-skills@mk" in t for t in result.tells()), result)

    def test_copilot_home_unset_reads_the_agents_store(self):
        """Copilot CLI reads ~/.agents/skills only while COPILOT_HOME is unset
        (180854c)."""
        self.skills_in(self.store(".agents", "skills"))
        result = self.setup("copilot-cli", "writing-for-agents", "yes")
        self.assertIn("all 13 Present and Resolvable", result.text)

    def test_copilot_home_set_skips_the_agents_store_and_adds_it_by_hand(self):
        """With COPILOT_HOME set, ~/.agents/skills is not read, and the -g
        install route adds copilot skill add with the path expanded (180854c,
        5638eda)."""
        self.skills_in(self.store(".agents", "skills"))
        env = self.box.env(COPILOT_HOME=os.path.join(self.box.root, "copilot"))
        result = self.setup("copilot-cli", "", "absent", env=env)
        self.assertIn("Not Present: " + ", ".join(SKILLS), result.text)
        route = [t for t in result.tells() if "npx skills" in t]
        self.assertEqual(len(route), 1, result)
        self.assertIn("copilot skill add '%s'" % os.path.join(self.box.home, ".agents", "skills"), route[0])
        self.skills_in(os.path.join("copilot", "skills"))
        result = self.setup("copilot-cli", "writing-for-agents", "yes", env=env)
        self.assertIn("all 13 Present and Resolvable", result.text)

    def test_copilot_plugin_routes(self):
        self.skills_in(self.store(".copilot", "installed-plugins", "mk", "mattpocock-skills", "skills"))
        result = self.setup("copilot-cli", "", "absent", "--user-answer", "does-not-resolve")
        self.assertTrue(any("copilot plugin enable mattpocock-skills@mk" in t for t in result.tells()), result)

    def test_copilot_direct_plugin_route(self):
        self.skills_in(self.store(".copilot", "installed-plugins", "_direct", "src-1", "skills"))
        result = self.setup("copilot-cli", "", "absent", "--user-answer", "does-not-resolve")
        self.assertTrue(any("copilot plugin enable src-1" in t for t in result.tells()), result)

    def test_codex_home_and_the_codex_plugin_route(self):
        self.skills_in(os.path.join("ch", "plugins", "cache", "mk", "mattpocock-skills", "1.0", "skills"))
        env = self.box.env(CODEX_HOME=os.path.join(self.box.root, "ch"))
        result = self.setup("codex", "", "absent", "--user-answer", "does-not-resolve", env=env)
        self.assertTrue(any("codex plugin add mattpocock-skills@mk" in t for t in result.tells()), result)
        self.assertTrue(any("$vdd:vdd-setup" in t for t in result.tells()), result)

    def test_typed_forms_per_harness(self):
        cursor = self.setup("cursor")
        self.assertTrue(any("/vdd-setup" in t and "/vdd:" not in t for t in cursor.tells()), cursor)
        self.assertTrue(any("Invoke /setup-matt-pocock-skills" in t for t in cursor.tells()), cursor)
        codex = self.setup("codex")
        self.assertTrue(any("$vdd:vdd-setup" in t for t in codex.tells()), codex)
        self.assertTrue(any("Invoke $setup-matt-pocock-skills" in t for t in codex.tells()), codex)

    def test_cursor_does_not_read_claude_stores_and_continues_the_no_hit_line(self):
        self.skills_in(self.store(".claude", "skills"))
        result = self.setup("cursor", "writing-for-agents", "yes")
        line = [t for t in result.tells() if "Resolvable from a store Setup does not search" in t]
        self.assertEqual(len(line), 1, result)
        self.assertIn("third-party import", line[0])

    def test_generic_searches_every_harness_s_roots(self):
        self.skills_in(self.store(".cursor", "skills"))
        self.assertIn("Not Present: " + ", ".join(SKILLS), self.setup("claude-code").text)
        result = self.setup("generic", "writing-for-agents", "yes")
        self.assertIn("all 13 Present and Resolvable", result.text)

    def test_unknown_harness_names_the_five(self):
        result = self.setup("nonsense")
        self.assertNotEqual(result.code, 0)
        self.assertIn("claude-code, codex, cursor, copilot-cli, generic", result.text)
        self.assertContract(result)

    def test_old_collection_from_the_description_gives_one_update_route(self):
        """A collection from before the glossary rename gets the update route
        for its store, in place of any install route (a483e69)."""
        self.skills_in(self.store(".claude", "skills"))
        result = self.setup("claude-code", "writing-for-agents", "no")
        self.assertTrue(any(t.startswith("Warning: your copy of Matt Pocock's collection") for t in result.tells()))
        self.assertEqual(self.route_lines(result), ["Update it: npx skills update -g"], result)

    def test_old_collection_from_writing_for_agents_alone_missing(self):
        self.skills_in(self.store(".claude", "skills"), [s for s in SKILLS if s != "writing-for-agents"])
        result = self.setup("claude-code", "grilling", "absent")
        self.assertIn("Not Present: writing-for-agents.", result.text)
        self.assertEqual(self.route_lines(result), ["Update it: npx skills update -g"], result)

    def test_old_collection_from_anthropic_s_marketplace_switches(self):
        self.skills_in(self.store(".claude", "plugins", "cache", "claude-plugins-official", "mattpocock-skills", "1.0"))
        result = self.setup("claude-code", "writing-for-agents", "no")
        self.assertTrue(any("claude plugin uninstall mattpocock-skills@claude-plugins-official" in t for t in result.tells()))

    # --- the repository checks ---

    def test_tracker_present(self):
        self.box.write("docs/agents/issue-tracker.md", "# Issue tracker: Local Markdown\n")
        result = self.setup()
        self.assertIn("configures local markdown. Passed.", result.text)
        self.box.write("docs/agents/issue-tracker.md", "# Issue tracker: GitHub\n")
        result = self.setup()
        self.assertTrue(any("not local markdown" in t for t in result.tells()), result)

    def test_repository_before_the_glossary_rename(self):
        self.box.write("docs/agents/domain.md", "Read CONTEXT-MAP.md\n")
        self.box.write("CONTEXT.md", "x\n")
        self.box.write("CONTEXT-MAP.md", "- [ordering](src/ordering/CONTEXT.md)\n")
        self.box.write("src/ordering/CONTEXT.md", "x\n")
        self.box.write("src/ordering/GLOSSARY.md", "x\n")
        self.box.write("AGENTS.md", "## Agent skills\nSee docs/agents/domain.md\n")
        result = self.setup()
        tells = result.tells()
        self.assertIn("git mv CONTEXT.md GLOSSARY.md", tells)
        self.assertIn("git mv CONTEXT-MAP.md GLOSSARY-MAP.md", tells)
        self.assertIn(
            "Merge the terms of src/ordering/CONTEXT.md into src/ordering/GLOSSARY.md, then remove src/ordering/CONTEXT.md.",
            tells,
        )
        self.assertIn("Edit docs/agents/domain.md and AGENTS.md so they name the new files.", tells)
        self.assertEqual(result.code, 0)

    def test_no_git_repository_asks_before_git_init(self):
        plain = os.path.join(self.box.root, "plain")
        os.makedirs(plain)
        result = self.setup(cwd=plain)
        self.assertNext(result, "git init")
        self.assertFalse(os.path.exists(os.path.join(plain, ".git")))

    def test_a_run_below_the_repository_root_changes_nothing_and_names_the_root(self):
        """Every check and write is relative to the working directory, so a
        run from a subdirectory planned a .gitignore there (finding 20 of the
        round 4 review)."""
        sub = self.box.path("sub", "dir")
        os.makedirs(sub)
        for extra in ((), ("--write",)):
            with self.subTest(extra=extra):
                result = self.setup("claude-code", "writing-for-agents", "yes", *extra, cwd=sub)
                self.assertNotEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertNotIn(".gitignore", result.text)
                self.assertIn("The repository root: " + self.box.proj, result.text)
                self.assertNext(result, "Change to the repository root, " + self.box.proj)
                self.assertNext(result, "setup --harness claude-code", *extra)
                self.assertEqual(os.listdir(sub), [])
                self.assertEqual(self.proj_files(), [".git", "sub"])
                self.assertFalse(os.path.exists(self.box.shared))

    def test_stale_loop_file_asks_before_deleting(self):
        self.box.write("LOOP.md", "x\n")
        result = self.setup()
        self.assertIn("LOOP.md: one from an earlier loop is here.", result.text)
        self.assertNext(result, "delete LOOP.md")
        self.assertTrue(os.path.exists(self.box.path("LOOP.md")))

    # --- --write ---

    def test_write_makes_the_changes_and_a_second_run_changes_nothing(self):
        result = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(self.box.read(".gitignore"), "LOOP.md\n.scratch/\n")
        self.assertEqual(vddtest_tree(SCRIPTS), vddtest_tree(self.box.shared))
        before = (self.box.read(".gitignore"), vddtest_tree(self.box.shared))
        again = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertIn("Nothing left to change.", again.text)
        self.assertEqual((self.box.read(".gitignore"), vddtest_tree(self.box.shared)), before)

    def test_update_swaps_the_tree_and_keeps_every_other_file(self):
        """Setup replaces vdd.py and vdd/ whole and leaves every other file in
        the Shared directory, so a Codex install still on 0.15 mid-loop keeps
        its scripts (spec, user story 12)."""
        self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.box.write("doorbell-wait.sh", "x\n", base=self.box.shared)
        with open(os.path.join(self.box.shared, "vdd.py"), "a") as handle:
            handle.write("# old\n")
        self.box.write(os.path.join("vdd", "stale.py"), "x = 1\n", base=self.box.shared)
        result = self.setup("claude-code", "writing-for-agents", "yes")
        self.assertIn("Planned change: update the VDD tool", result.text)
        result = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertIn("Shared copy of the VDD tool: checked.", result.text)
        self.assertEqual(vddtest_tree(SCRIPTS), vddtest_tree(self.box.shared))
        self.assertEqual(sorted(os.listdir(self.box.shared)), ["doorbell-wait.sh", "vdd", "vdd.py"])

    def test_gitignore_removes_only_whole_retired_lines(self):
        """A line goes only when the whole line, trimmed, is a retired entry:
        docs/PLAN.md and !PLAN.md are the user's own (6106fb6)."""
        self.box.write(".gitignore", "PLAN.md\ndocs/PLAN.md\n!PLAN.md\n  FIXES.md  \n")
        result = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertIn("Changed: .gitignore removes PLAN.md", result.text)
        self.assertIn("Changed: .gitignore removes FIXES.md", result.text)
        self.assertEqual(self.box.read(".gitignore"), "docs/PLAN.md\n!PLAN.md\nLOOP.md\n.scratch/\n")

    def test_gitignore_keeps_crlf_and_a_missing_last_newline(self):
        self.box.write(".gitignore", "node_modules\r\n/dist")
        self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertEqual(self.box.read(".gitignore"), "node_modules\r\n/dist\r\nLOOP.md\r\n.scratch/\r\n")

    def test_a_gitignore_that_starts_with_a_bom(self):
        """A leading byte order mark is not part of line 1, so LOOP.md on line
        1 counts and a retired entry there goes (finding 21 of the round 4
        review)."""
        self.box.write(".gitignore", b"\xef\xbb\xbfLOOP.md\n.scratch/\n")
        result = self.setup("claude-code", "writing-for-agents", "yes")
        self.assertIn(".gitignore: covers LOOP.md and .scratch/. Passed.", result.text)
        self.assertNotIn(".gitignore adds", result.text)
        self.box.write(".gitignore", b"\xef\xbb\xbfPLAN.md\r\nLOOP.md\r\n")
        result = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertIn("Changed: .gitignore removes PLAN.md", result.text)
        self.assertNotIn(".gitignore adds LOOP.md", result.text)
        self.assertEqual(self.box.read(".gitignore"), "LOOP.md\r\n.scratch/\r\n")

    def test_dry_run_leaves_gitignore_alone(self):
        self.box.write(".gitignore", "PLAN.md\n")
        self.setup()
        self.assertEqual(self.box.read(".gitignore"), "PLAN.md\n")

    @unittest.skipIf(WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0), "needs a POSIX permission bit")
    def test_a_refused_write_exits_non_zero_and_names_the_escalation(self):
        os.chmod(self.box.data, stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, self.box.data, stat.S_IRWXU)
        result = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("Not changed: the Shared copy of the VDD tool", result.text)
        self.assertNext(result, "outside the sandbox")


def vddtest_tree(base):
    out = {}
    for directory, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            path = os.path.join(directory, name)
            rel = os.path.relpath(path, base)
            if rel.split(os.sep)[0] not in ("vdd.py", "vdd"):
                continue
            with open(path, "rb") as handle:
                out[rel] = handle.read()
    return out


if __name__ == "__main__":
    unittest.main()
