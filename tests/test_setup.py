"""The setup command, driven from outside."""

import json
import os
import shutil
import stat
import subprocess
import unittest

from vddtest import SCRIPTS, WINDOWS, ToolTest
import vddtest

SKILLS = (
    "setup-matt-pocock-skills", "grill-with-docs", "to-spec",
    "to-tickets", "wayfinder", "code-review", "writing-for-agents", "grilling", "domain-modeling",
    "research", "prototype",
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
        self.assertNotIn("LOOP.md", result.text)
        self.assertIn("Planned change: .gitignore adds .scratch/", result.text)
        self.assertIn("Planned change: install the VDD tool", result.text)
        self.assertNext(result, "--write")
        self.assertEqual(self.proj_files(), [".git"])
        self.assertEqual(os.listdir(self.box.data), [])

    def test_writing_for_agents_listed_with_no_hit_is_resolvable_in_one_line(self):
        """Prevents a repair offered to a collection that resolves from a store
        Setup does not search: Resolvable with no search hit passes and gets
        no repair."""
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

    def test_codebase_design_still_proves_the_collection_wired(self):
        """improve-codebase-architecture and codebase-design left the Borrowed
        skills, but codebase-design stays a sibling whose hit proves the
        collection is wired."""
        result = self.setup(listed="codebase-design")
        self.assertIn("Not Present: writing-for-agents.", result.text)
        for name in ("improve-codebase-architecture", "codebase-design", "general-improvement"):
            self.assertNotIn(name, result.text.replace("--listed codebase-design", ""))
        self.assertNotIn("improve-codebase-architecture", self.box.run("setup", "--help").text)

    def test_present_and_resolvable_passes_with_no_repair(self):
        self.skills_in(self.store(".claude", "skills"))
        result = self.setup(listed="writing-for-agents", glossary="yes")
        self.assertIn("Borrowed skills: all 11 Present and Resolvable. Passed.", result.text)
        self.assertEqual(self.route_lines(result), [], result)

    def test_present_with_nothing_listed_asks_the_user_to_invoke_writing_for_agents(self):
        self.skills_in(self.store(".claude", "skills"))
        result = self.setup()
        self.assertNext(result, "/writing-for-agents", "--user-answer resolves", "does-not-resolve")
        self.assertEqual(self.route_lines(result), [], result)

    def test_the_users_answer_resolves(self):
        self.skills_in(self.store(".claude", "skills"))
        result = self.setup("claude-code", "", "absent", "--user-answer", "resolves")
        self.assertIn("all 11 Present and Resolvable", result.text)

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
        */mattpocock-skills so that copy is not counted as an installed one."""
        self.skills_in(self.store(".claude", "plugins", "cache", "temp_git_123", "skills", "engineering"))
        result = self.setup()
        self.assertIn("Not Present: " + ", ".join(SKILLS), result.text)

    def test_a_symlinked_skills_cli_install_counts(self):
        """A global skills-CLI install for Claude Code writes the real copy to
        ~/.agents/skills and a symlink at ~/.claude/skills; the search follows
        it, so such an install does not read as Not Present."""
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
        self.assertIn("all 11 Present and Resolvable", result.text)

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
        Code reads, and the search moves with them, so skills installed there
        do not read as Not Present."""
        self.skills_in(os.path.join("cfg", "skills"))
        env = self.box.env(CLAUDE_CONFIG_DIR=os.path.join(self.box.root, "cfg"))
        result = self.setup("claude-code", "writing-for-agents", "yes", env=env)
        self.assertIn("all 11 Present and Resolvable", result.text)
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
        """Copilot CLI reads ~/.agents/skills only while COPILOT_HOME is unset,
        so the search neither misses that store nor counts it when set."""
        self.skills_in(self.store(".agents", "skills"))
        result = self.setup("copilot-cli", "writing-for-agents", "yes")
        self.assertIn("all 11 Present and Resolvable", result.text)

    def test_copilot_home_set_skips_the_agents_store_and_adds_it_by_hand(self):
        """Prevents ~/.agents/skills counted while COPILOT_HOME is set, and a
        -g install route without the expanded path: it is not read, and the
        route adds copilot skill add with the path expanded."""
        self.skills_in(self.store(".agents", "skills"))
        env = self.box.env(COPILOT_HOME=os.path.join(self.box.root, "copilot"))
        result = self.setup("copilot-cli", "", "absent", env=env)
        self.assertIn("Not Present: " + ", ".join(SKILLS), result.text)
        route = [t for t in result.tells() if "npx skills" in t]
        self.assertEqual(len(route), 1, result)
        self.assertIn("copilot skill add '%s'" % os.path.join(self.box.home, ".agents", "skills"), route[0])
        self.skills_in(os.path.join("copilot", "skills"))
        result = self.setup("copilot-cli", "writing-for-agents", "yes", env=env)
        self.assertIn("all 11 Present and Resolvable", result.text)

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
        self.assertIn("all 11 Present and Resolvable", result.text)

    def test_unknown_harness_names_the_five(self):
        result = self.setup("nonsense")
        self.assertNotEqual(result.code, 0)
        self.assertIn("claude-code, codex, cursor, copilot-cli, generic", result.text)
        self.assertContract(result)

    def test_the_loop_file_spelling_names_the_same_harness(self):
        """The Loop file's Harness: line spells the Harness "Claude Code", and
        three Roles passed that spelling to --harness and were refused: it
        names the same Harness as the slug."""
        for spelled, slug in (("Claude Code", "claude-code"), ("Copilot CLI", "copilot-cli"), ("Cursor", "cursor")):
            result = self.setup(spelled)
            self.assertEqual(result.code, 0, result)
            self.assertEqual(result.text, self.setup(slug).text)

    def test_old_collection_from_the_description_gives_one_update_route(self):
        """A collection from before the glossary rename gets the update route
        for its store, in place of any install route, which it does not
        need."""
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

    def test_outside_a_repository_the_shared_copy_is_still_installed(self):
        """Prevents a Brainstormer left without its tool by a failed git
        check, since Setup installs the tool before its git gate: --write outside a repository installs the Shared copy."""
        plain = os.path.join(self.box.root, "plain")
        os.makedirs(plain)
        result = self.setup("claude-code", "none", "absent", "--write", cwd=plain)
        self.assertContract(result)
        self.assertEqual(vddtest_tree(SCRIPTS), vddtest_tree(self.box.shared))

    def test_a_run_below_the_repository_root_changes_nothing_and_names_the_root(self):
        """Every check and write is relative to the working directory, so a run
        from a subdirectory planned a .gitignore there."""
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

    def test_a_run_from_the_shared_copy_is_refused(self):
        """Prevents Setup run from the Shared copy calling that copy current
        whatever the plugin ships: it compares the directory it runs from
        with the Shared directory, which are then the same."""
        os.makedirs(self.box.shared)
        shutil.copyfile(os.path.join(SCRIPTS, "vdd.py"), os.path.join(self.box.shared, "vdd.py"))
        shutil.copytree(os.path.join(SCRIPTS, "vdd"), os.path.join(self.box.shared, "vdd"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        with open(os.path.join(self.box.shared, "vdd.py"), "a") as handle:
            handle.write("# old\n")
        entry = os.path.join(self.box.shared, "vdd.py")
        before = vddtest_tree(self.box.shared)
        for extra in ((), ("--write",)):
            with self.subTest(extra=extra):
                result = self.box.run("setup", "--harness", "claude-code", "--listed", "writing-for-agents",
                                      "--glossary-named", "yes", *extra, entry=entry)
                self.assertEqual(result.code, 1, result)
                self.assertContract(result)
                self.assertIn("Setup ran from the Shared copy of the VDD tool, %s" % entry, result.text)
                self.assertIn("Nothing was checked or changed.", result.lines)
                self.assertNotIn("current", result.text)
                self.assertNext(result, "Setup runs from the copy beside the vdd-setup skill you loaded",
                                vddtest.tool_command(os.path.join("<vdd-setup skill directory>", "scripts", "vdd.py"))
                                + " setup --harness claude-code --listed writing-for-agents --glossary-named yes",
                                *extra)
                self.assertEqual(vddtest_tree(self.box.shared), before)
                self.assertEqual(self.proj_files(), [".git"])
        shipped = self.setup("claude-code", "writing-for-agents", "yes")
        self.assertIn("Planned change: update the VDD tool", shipped.text)

    def test_a_loop_md_in_lowercase_is_not_reported_as_a_root_loop_file(self):
        """Only a file named exactly LOOP.md is a format-1 Loop file; on a
        case-insensitive file system a path test would match loop.md too."""
        self.box.write("loop.md", "x\n")
        result = self.setup("claude-code", "writing-for-agents", "yes")
        self.assertEqual(result.code, 0, result)
        self.assertNotIn("LOOP.md", result.text)

    def test_a_root_loop_file_is_reported_with_its_fix_and_no_question(self):
        """A root LOOP.md is a format-1 Loop file: Setup reports it with the
        fix and asks no delete question, its other checks still run, and its
        exit code stays 0; loop new is where a loop start stops."""
        self.box.write("LOOP.md", "x\n")
        result = self.setup("claude-code", "writing-for-agents", "yes")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn(
            "Delete `LOOP.md`. To carry on the loop it belongs to, run `vdd-start-loop` with its slug and answer "
            "continue.",
            result.tells(),
        )
        self.assertNotIn("LOOP.md", result.last)
        self.assertIn("Planned change: .gitignore adds .scratch/", result.text)
        self.assertIn("Planned change: install the VDD tool", result.text)
        written = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertEqual(written.code, 0, written)
        self.assertTrue(os.path.exists(self.box.path("LOOP.md")))
        self.assertTrue(os.path.exists(self.box.shared))

    # --- --write ---

    def test_write_makes_the_changes_and_a_second_run_changes_nothing(self):
        result = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(self.box.read(".gitignore"), ".scratch/\n")
        self.assertEqual(vddtest_tree(SCRIPTS), vddtest_tree(self.box.shared))
        before = (self.box.read(".gitignore"), vddtest_tree(self.box.shared))
        again = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertIn("Nothing left to change.", again.text)
        self.assertEqual((self.box.read(".gitignore"), vddtest_tree(self.box.shared)), before)

    def test_update_swaps_the_tree_and_keeps_every_other_file(self):
        """Setup replaces vdd.py and vdd/ whole and leaves every other file in
        the Shared directory, so a Codex install still on 0.15 mid-loop keeps
        its scripts."""
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

    def test_a_copy_that_differs_by_one_byte_is_replaced_and_no_staging_is_left(self):
        """The first Setup after an update replaces a copy whose content
        differs, with no migration step, and leaves no staging or old-copy
        directory behind."""
        self.setup("claude-code", "writing-for-agents", "yes", "--write")
        entry = os.path.join(self.box.shared, "vdd.py")
        with open(entry, "rb") as handle:
            data = bytearray(handle.read())
        data[0] = ord("#") if data[0] != ord("#") else ord(" ")
        with open(entry, "wb") as handle:
            handle.write(bytes(data))
        result = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertIn("update the VDD tool", result.text)
        self.assertIn("Shared copy of the VDD tool: checked.", result.text)
        self.assertEqual(vddtest_tree(SCRIPTS), vddtest_tree(self.box.shared))
        left = [name for name in os.listdir(self.box.shared) if name.startswith((".vdd-new-", ".vdd-old-"))]
        self.assertEqual(left, [])

    @unittest.skipUnless(WINDOWS, "icacls and inherited ACL entries are Windows only")
    def test_the_installed_copy_inherits_the_shared_directory_acl(self):
        """Codex's Windows sandbox could not read a Shared copy staged in a
        tempfile directory, whose protected ACL the installed files kept, so
        every VDD call was refused and rerun escalated. Setup stages with a
        plain mkdir, so the installed files carry exactly the access entries a
        file written in the Shared directory gets. The comparison holds on a
        machine whose temporary directory hands down nothing to inherit, as
        on GitHub's Windows runners. The extra inheritable entry for Everyone
        is what a protected staging directory would not hand down."""
        granted = subprocess.run(["icacls", self.box.data, "/grant", "*S-1-1-0:(OI)(CI)(RX)"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(granted.returncode, 0, granted.stderr)
        result = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertEqual(result.code, 0, result)
        reference = os.path.join(self.box.shared, "reference.txt")
        with open(reference, "w") as handle:
            handle.write("x\n")

        def entries(path):
            proc = subprocess.run(["icacls", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = proc.stdout.decode("utf-8", "replace")
            found = []
            for number, line in enumerate(text.splitlines()):
                line = line.strip()
                if not line or line.startswith("Successfully processed"):
                    continue
                if number == 0:
                    line = line[len(path):].strip() if line.lower().startswith(path.lower()) else line
                if ":" in line and "(" in line:
                    found.append(line)
            self.assertTrue(found, text)
            return sorted(found)

        expected = entries(reference)
        self.assertTrue([entry for entry in expected if "Everyone" in entry or "S-1-1-0" in entry], expected)
        for path in (os.path.join(self.box.shared, "vdd.py"), os.path.join(self.box.shared, "vdd", "cli.py")):
            with self.subTest(path=path):
                self.assertEqual(entries(path), expected)

    def test_gitignore_removes_only_whole_retired_lines(self):
        """A line goes only when the whole line, trimmed, is a retired entry:
        docs/PLAN.md and !PLAN.md are the user's own, and Setup must not
        delete them with the retired ones."""
        self.box.write(".gitignore", "PLAN.md\ndocs/PLAN.md\n!PLAN.md\n  FIXES.md  \n")
        result = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertIn("Changed: .gitignore removes PLAN.md", result.text)
        self.assertIn("Changed: .gitignore removes FIXES.md", result.text)
        self.assertEqual(self.box.read(".gitignore"), "docs/PLAN.md\n!PLAN.md\n.scratch/\n")

    def test_gitignore_keeps_crlf_and_a_missing_last_newline(self):
        self.box.write(".gitignore", "node_modules\r\n/dist")
        self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertEqual(self.box.read(".gitignore"), "node_modules\r\n/dist\r\n.scratch/\r\n")

    def test_a_loop_md_entry_is_neither_added_nor_removed(self):
        """Setup stops adding LOOP.md and never removes an entry the user
        has, so an old root file stays out of git add."""
        result = self.setup("claude-code", "writing-for-agents", "yes")
        self.assertNotIn("LOOP.md", result.text)
        self.box.write(".gitignore", "LOOP.md\n")
        result = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(self.box.read(".gitignore"), "LOOP.md\n.scratch/\n")

    def test_a_gitignore_that_starts_with_a_bom(self):
        """A leading byte order mark is not part of line 1, so .scratch/ on
        line 1 counts and a retired entry there goes."""
        self.box.write(".gitignore", b"\xef\xbb\xbf.scratch/\n")
        result = self.setup("claude-code", "writing-for-agents", "yes")
        self.assertIn(".gitignore: covers .scratch/. Passed.", result.text)
        self.assertNotIn(".gitignore adds", result.text)
        self.box.write(".gitignore", b"\xef\xbb\xbfPLAN.md\r\n.scratch/\r\n")
        result = self.setup("claude-code", "writing-for-agents", "yes", "--write")
        self.assertIn("Changed: .gitignore removes PLAN.md", result.text)
        self.assertNotIn(".gitignore adds", result.text)
        self.assertEqual(self.box.read(".gitignore"), ".scratch/\r\n")

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
        self.assertNext(result, "outside the sandbox, rerun it once that way.", "did not land and what it was for, and stop.")
        self.assertTrue(result.last.startswith("Next: Relay every Tell the user verbatim line above unchanged; only after doing that, if a sandbox refused it"), result)

    @unittest.skipIf(WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0), "needs a POSIX permission bit")
    def test_an_unreadable_gitignore_ends_on_the_escalation_not_a_traceback(self):
        path = self.box.write(".gitignore", "node_modules\n")
        os.chmod(path, 0)
        self.addCleanup(os.chmod, path, stat.S_IRUSR | stat.S_IWUSR)
        for extra in ((), ("--write",)):
            with self.subTest(extra=extra):
                result = self.setup("claude-code", "writing-for-agents", "yes", *extra)
                self.assertNotEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertIn("Could not read .gitignore", result.text)
                self.assertNotIn("Traceback", result.text)
                self.assertNext(result, "outside the sandbox", "stop")

    # (the file Setup cannot read, what else is staged, the line printed just before the refusal)
    UNREADABLE = (
        ("docs/agents/issue-tracker.md", {}, None),
        ("docs/agents/domain.md", {}, "Tracker: docs/agents/issue-tracker.md configures local markdown. Passed."),
        ("CONTEXT-MAP.md", {"docs/agents/domain.md": "See CONTEXT-MAP.md.\n"},
         'Tell the user verbatim: "Warning: this repository was set up before Matt Pocock\'s glossary rename'),
        ("AGENTS.md", {"docs/agents/domain.md": "See CONTEXT.md.\n", "CONTEXT.md": "x\n"},
         'Tell the user verbatim: "git mv CONTEXT.md GLOSSARY.md"'),
        ("CLAUDE.md", {"docs/agents/domain.md": "See CONTEXT.md.\n", "CONTEXT.md": "x\n", "AGENTS.md": "x\n"},
         'Tell the user verbatim: "git mv CONTEXT.md GLOSSARY.md"'),
    )

    def test_an_unreadable_file_keeps_every_check_printed_before_it(self):
        """Prevents a file Setup cannot read from ending the run on the bare
        file error, which dropped every check Setup had already printed. A
        directory stands in for the unreadable file on every OS."""
        for name, staged, before in self.UNREADABLE:
            with self.subTest(file=name):
                self.box.write("docs/agents/issue-tracker.md", "Local markdown.\n")
                for path, text in staged.items():
                    self.box.write(path, text)
                unreadable = os.path.join(self.box.proj, *name.split("/"))
                if os.path.isfile(unreadable):
                    os.remove(unreadable)
                os.makedirs(unreadable)
                result = self.setup("claude-code", "writing-for-agents", "yes")
                shutil.rmtree(unreadable)
                self.assertEqual(result.code, 1, result)
                self.assertContract(result)
                self.assertNext(result, "outside the sandbox", "Setup could not read %s, and stop." % name)
                self.assertTrue(result.lines[-2].startswith("Could not read %s: " % name), result)
                printed = result.lines[:-2]
                self.assertEqual(printed[0], "Setup, Harness Claude Code (dry run, nothing is changed yet).")
                if before is not None:
                    self.assertTrue(printed[-1].startswith(before), result)
                self.assertEqual(printed, self.setup("claude-code", "writing-for-agents", "yes").lines[:len(printed)])
                for path in list(staged) + ["docs"]:
                    full = os.path.join(self.box.proj, *path.split("/"))
                    if os.path.isdir(full):
                        shutil.rmtree(full)
                    elif os.path.exists(full):
                        os.remove(full)


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


OLD_SH = 'sh "/x/vdd/vdd-codex-stop.sh" || true'
OLD_PS = "$f='C:\\Users\\a''b\\AppData\\Local\\vdd\\vdd-codex-stop.ps1';if(Test-Path -LiteralPath $f){powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f}"
USER_GROUP = {"matcher": "", "hooks": [{"type": "command", "command": "notify-send done", "timeout": 5}]}


class CodexSetupTest(ToolTest):
    """Setup on Codex: the hooks.json migration and the Codex home."""

    def setUp(self):
        ToolTest.setUp(self)
        subprocess.run(["git", "init", "-q"], cwd=self.box.proj, check=True)
        self.codex = os.path.join(self.box.home, ".codex")
        os.makedirs(self.codex)

    def setup(self, *extra, harness="codex"):
        return self.box.run("setup", "--harness", harness, "--listed", "writing-for-agents",
                            "--glossary-named", "yes", *extra)

    def hooks(self, data):
        text = json.dumps(data, indent=2) + "\n"
        with open(os.path.join(self.codex, "hooks.json"), "w") as handle:
            handle.write(text)
        return text

    def read_hooks(self):
        with open(os.path.join(self.codex, "hooks.json")) as handle:
            return handle.read()

    def config(self, text):
        with open(os.path.join(self.codex, "config.toml"), "w") as handle:
            handle.write(text)

    def vdd_group(self, command=OLD_SH, **extra):
        handler = {"type": "command", "command": command, "timeout": 2760}
        handler.update(extra)
        return {"hooks": [handler]}

    def test_removes_vdd_s_old_entry_after_showing_the_diff(self):
        """The model used to build the hooks.json entry itself. Setup no longer
        writes one; it removes the old one in code."""
        before = self.hooks({"model": "x", "hooks": {"Stop": [self.vdd_group(), USER_GROUP], "PreToolUse": []}})
        result = self.setup()
        self.assertIn("Planned change: ~/.codex/hooks.json removes VDD's old Stop hook entry", result.text)
        self.assertIn("-            \"command\": \"sh \\\"/x/vdd/vdd-codex-stop.sh\\\" || true\",", result.lines)
        self.assertTrue(any("Hooks need review" in t for t in result.tells()), result)
        self.assertEqual(self.read_hooks(), before)
        result = self.setup("--write")
        self.assertEqual(result.code, 0, result)
        after = json.loads(self.read_hooks())
        self.assertEqual(after, {"model": "x", "hooks": {"Stop": [USER_GROUP], "PreToolUse": []}})
        self.assertEqual(os.listdir(self.codex), ["hooks.json"])
        self.assertEqual(sorted(os.listdir(self.box.proj)), [".git", ".gitignore"])
        self.assertIn("Nothing left to change.", self.setup("--write").text)

    def test_the_015_windows_template_is_removed_and_the_stop_key_stays(self):
        """Only VDD's handler and its emptied group go; every other key stays,
        Stop included."""
        self.hooks({"hooks": {"Stop": [self.vdd_group(OLD_PS, commandWindows=OLD_PS)]}})
        result = self.setup("--write")
        self.assertEqual(json.loads(self.read_hooks()), {"hooks": {"Stop": []}})
        self.assertFalse(any("Hooks need review" in t for t in result.tells()))

    def test_the_diff_shows_only_vdd_s_removal_whatever_the_file_s_layout(self):
        """The dry-run diff is what the user consents to: a user's group the
        migration does not touch never shows in it."""
        user = {"hooks": [{"type": "command", "command": "echo mine"}]}
        data = {"hooks": {"PreToolUse": [user], "Stop": [self.vdd_group()]}}
        two_space = json.dumps(data, indent=2) + "\n"
        files = {
            "compact": '{"hooks": {"PreToolUse": [%s],\n "Stop": [%s]}}\n' % (
                json.dumps(user), json.dumps(self.vdd_group())),
            "two-space": two_space,
            "two-space CRLF": two_space.replace("\n", "\r\n"),
            "two-space BOM": "\ufeff" + two_space,
        }
        for name, text in files.items():
            with self.subTest(file=name):
                with open(os.path.join(self.codex, "hooks.json"), "wb") as handle:
                    handle.write(text.encode("utf-8"))
                result = self.setup()
                changed = [l for l in result.lines if l[:1] in "+-" and l[:3] not in ("+++", "---")]
                self.assertTrue(changed, result)
                self.assertFalse(any("echo mine" in l or "PreToolUse" in l for l in changed), result)
                added = [l for l in changed if l.startswith("+")]
                self.assertEqual(added, ['+    "Stop": []'], result)
                relaid = [l for l in result.lines if "rewritten in two-space JSON layout" in l]
                self.assertEqual(len(relaid), 0 if name == "two-space" else 1, result)

    def test_any_other_vdd_handler_is_reported_and_left(self):
        before = self.hooks({"hooks": {"Stop": [self.vdd_group("python3 /mine/vdd-codex-stop.py")]}})
        self.assertIn("naming vdd-codex-stop that Setup did not write stays: python3 /mine/vdd-codex-stop.py",
                      self.setup().text)
        self.setup("--write")
        self.assertEqual(self.read_hooks(), before)

    def test_an_old_template_with_another_timeout_stays(self):
        before = self.hooks({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": OLD_SH, "timeout": 60}]}]}})
        self.setup("--write")
        self.assertEqual(self.read_hooks(), before)

    def test_a_hooks_json_that_does_not_parse_is_left_and_reported(self):
        with open(os.path.join(self.codex, "hooks.json"), "w") as handle:
            handle.write("{ not json")
        result = self.setup("--write")
        self.assertTrue(any("left ~/.codex/hooks.json untouched" in t for t in result.tells()), result)
        self.assertEqual(self.read_hooks(), "{ not json")
        self.assertIn("~/.codex/hooks.json: left untouched, it does not parse as JSON (", self.setup().text)

    def test_a_hooks_json_that_cannot_be_read_names_the_reason_as_one(self):
        """The Tell line read "untouched because Permission denied.", a bare
        strerror where the user is owed a reason."""
        os.mkdir(os.path.join(self.codex, "hooks.json"))
        result = self.setup("--write")
        tells = [t for t in result.tells() if "hooks.json" in t]
        self.assertEqual(len(tells), 1, result)
        self.assertRegex(tells[0], r"^Setup left ~/\.codex/hooks\.json untouched: it could not be read \([^()]+\)\. "
                                   r"If it holds VDD's old Stop hook entry, remove that entry by hand\.$")
        self.assertRegex(self.setup().text,
                         r"~/\.codex/hooks\.json: left untouched, it could not be read \([^()]+\)\.")

    def test_a_registration_in_config_toml_is_reported(self):
        self.config('[[hooks.Stop]]\n[[hooks.Stop.hooks]]\ncommand = "sh /x/vdd-codex-stop.sh"\n')
        self.assertIn("a registration naming vdd-codex-stop stays", self.setup().text)

    def test_codex_home_moves_the_files(self):
        home = os.path.join(self.box.root, "ch")
        os.makedirs(home)
        with open(os.path.join(home, "hooks.json"), "w") as handle:
            json.dump({"hooks": {"Stop": [self.vdd_group()]}}, handle)
        result = self.box.run("setup", "--harness", "codex", "--listed", "writing-for-agents",
                              "--glossary-named", "yes", env=self.box.env(CODEX_HOME=home))
        self.assertIn("removes VDD's old Stop hook entry", result.text)

    def test_an_empty_codex_home_reads_as_unset(self):
        """CODEX_HOME is read in one place now; empty there must still mean
        ~/.codex, for the hook steps and for the skill search alike."""
        self.hooks({"hooks": {"Stop": [self.vdd_group()]}})
        self.box.write(os.path.join(self.codex, "plugins", "cache", "mk", "mattpocock-skills", "1.0", "skills",
                                    "grilling", "SKILL.md"), "x\n", base=self.box.root)
        for value in ("", None):
            with self.subTest(CODEX_HOME=value):
                result = self.box.run("setup", "--harness", "codex", "--listed", "writing-for-agents",
                                      "--glossary-named", "yes", env=self.box.env(CODEX_HOME=value))
                self.assertIn("~/.codex/hooks.json", result.text)
                self.assertIn("removes VDD's old Stop hook entry", result.text)
                self.assertIn("Borrowed skills Present and Resolvable, passed: grilling.", result.lines, result)

    def test_other_harnesses_skip_the_codex_steps(self):
        self.hooks({"hooks": {"Stop": [self.vdd_group()]}})
        result = self.setup(harness="claude-code")
        self.assertNotIn("hooks.json", result.text)
        self.assertNotIn("Trust VDD's hook", result.text)


FIXTURE = os.path.join(vddtest.REPO, "tests", "fixtures", "codex-hook-trust", "plugin")
# Codex's content hash of the fixture's plugin/ directory, written by Codex
# itself: with / between path parts on macOS and Linux, with \ on Windows.
GOLDEN = ("sha256:f598068ff9739853b66c1f75651f9d9462cf2205f6883157feddb7fd9de9de89" if WINDOWS
          else "sha256:373e6197f5e335ea64266fe459e7e0e8b1d7797ccd88bd3ccf2018c07bcf984c")
EMPTY_DIR_GOLDEN = ("sha256:00f5dfdb596446e0bb999ffc9d646b1cb86d82a2c5571770700992d65bff3c9a" if WINDOWS
                    else "sha256:b69ea080ca32ef7573b29ee0f1083636676607abd63b715b87f15c3ea1ea6adf")
NOT_TRUSTED_WAIT = "Trust VDD's hook in /hooks, then say so here, or say skip."
CHANGED_WAIT = "VDD changed since you trusted its hook. Trust it again in /hooks, then say so here, or say skip."
COULD_NOT_VERIFY = ("Setup could not verify that Codex trusts VDD's hook. If /hooks lists it for review, "
                    "trust it there.")
SWITCHED_OFF = "VDD's hook is switched off in Codex: turn it on in /hooks, or every Doorbell waits for a paste."


def hook_key(marketplace="mk"):
    return '[hooks.state."vdd@%s:plugin.json#hooks[0]:stop:0:0"]\n' % marketplace


def hook_entry(marketplace="mk", content=GOLDEN, trusted="sha256:declaration", enabled=None):
    text = hook_key(marketplace)
    if trusted is not None:
        text += 'trusted_hash = "%s"\n' % trusted
    if content is not None:
        text += 'trusted_content_hash = "%s"\n' % content
    if enabled is not None:
        text += "enabled = %s\n" % ("true" if enabled else "false")
    return text


class CodexTrustTest(ToolTest):
    """Setup on Codex: whether Codex trusts VDD's hook, the installed copy
    hashed as Codex hashes it against the hash it stored in config.toml."""

    def setUp(self):
        ToolTest.setUp(self)
        subprocess.run(["git", "init", "-q"], cwd=self.box.proj, check=True)
        self.codex = os.path.join(self.box.home, ".codex")
        os.makedirs(self.codex)
        self.settled = False

    def setup(self, *extra, harness="codex", env=None):
        """A dry run with nothing left to change, so its report lines and its
        Next: are the final run's."""
        if not self.settled:
            self.box.run("setup", "--harness", harness, "--listed", "writing-for-agents", "--glossary-named", "yes",
                         "--write", env=env)
            self.settled = True
        return self.box.run("setup", "--harness", harness, "--listed", "writing-for-agents", "--glossary-named",
                            "yes", *extra, env=env)

    def config(self, text):
        with open(os.path.join(self.codex, "config.toml"), "w") as handle:
            handle.write(text)

    def cached(self, marketplace="mk", version="1.0.0", source=FIXTURE):
        """The fixture as the installed copy Codex keeps for marketplace."""
        root = os.path.join(self.codex, "plugins", "cache", marketplace, "vdd", version)
        shutil.copytree(source, root, symlinks=True)
        return root

    def hook_lines(self, result):
        return [line for line in result.lines if line.startswith("VDD's Codex hook")]

    def codex_home(self):
        """Every entry under the Codex home with its size and modification
        time."""
        found = []
        for directory, dirs, files in os.walk(self.codex):
            for name in sorted(dirs + files):
                path = os.path.join(directory, name)
                info = os.lstat(path)
                found.append((os.path.relpath(path, self.codex), info.st_size, info.st_mtime_ns))
        return sorted(found)

    def assertTrusted(self, result):
        self.assertEqual(len(self.hook_lines(result)), 1, result)
        self.assertRegex(self.hook_lines(result)[0], r"^VDD's Codex hook: trusted, ", result)
        self.assertNotIn(CHANGED_WAIT, result.tells())
        self.assertNotIn(NOT_TRUSTED_WAIT, result.tells())
        self.assertNotIn(COULD_NOT_VERIFY, result.tells())
        self.assertIn("Setup is done", result.last, result)

    def assertChanged(self, result):
        self.assertRegex(self.hook_lines(result)[0], r"^VDD's Codex hook: changed, ", result)
        self.assertIn(CHANGED_WAIT, result.tells())

    def test_the_fixture_with_its_golden_reports_trusted(self):
        """Prevents a drift in the port of Codex's content hash: the fixture
        hashes to the value Codex itself stored on this platform."""
        self.cached()
        self.config(hook_entry())
        self.assertTrusted(self.setup())

    def test_an_empty_directory_is_hashed(self):
        """Prevents the port from skipping an empty directory Codex hashes."""
        root = self.cached()
        os.mkdir(os.path.join(root, "emptydir"))
        self.config(hook_entry(content=EMPTY_DIR_GOLDEN))
        self.assertTrusted(self.setup())

    def test_one_byte_appended_reports_changed(self):
        """Prevents an update of VDD from passing as the copy the user
        trusted."""
        root = self.cached()
        self.config(hook_entry())
        with open(os.path.join(root, "nested", "deep", "leaf.md"), "ab") as handle:
            handle.write(b"x")
        result = self.setup()
        self.assertChanged(result)
        self.assertEqual(result.tells().count(CHANGED_WAIT), 1, result)

    def test_entries_codex_skips_change_nothing(self):
        """Prevents Setup from calling a hook changed for a file Codex leaves
        out of its hash."""
        for name in ("extra.pyc", os.path.join("__pycache__", "new.pyc"), os.path.join(".venv", "bin"),
                     os.path.join("more.egg-info", "PKG-INFO")):
            with self.subTest(name=name):
                root = self.cached()
                self.config(hook_entry())
                self.box.write(os.path.join(root, name), "x\n")
                self.assertTrusted(self.setup())
                shutil.rmtree(os.path.join(self.codex, "plugins"))

    def test_dotfiles_are_hashed(self):
        """Prevents Setup from calling a copy trusted after a change Codex sees:
        .git/ and every other dotfile are in Codex's hash."""
        for name in (os.path.join(".git", "config"), ".DS_Store"):
            with self.subTest(name=name):
                root = self.cached()
                self.config(hook_entry())
                self.box.write(os.path.join(root, name), "x\n")
                self.assertChanged(self.setup())
                shutil.rmtree(os.path.join(self.codex, "plugins"))

    def test_no_entry_asks_to_trust_without_looking_for_a_copy(self):
        """Prevents a hook the user never trusted from passing silently, and a
        missing copy from changing what Setup says about it."""
        for text in ("", '[hooks.state."/x/hooks.json:stop:0:0"]\ntrusted_hash = "a"\n',
                     '[hooks.state."other@mk:plugin.json#hooks[0]:stop:0:0"]\ntrusted_hash = "a"\n',
                     'notes = """\n[hooks.state."vdd@mk:plugin.json#hooks[0]:stop:0:0"]\n"""\n',
                     hook_entry(trusted=None, content=None, enabled=True)):
            with self.subTest(text=text):
                self.config(text)
                without = self.setup()
                self.assertIn(NOT_TRUSTED_WAIT, without.tells())
                self.assertRegex(self.hook_lines(without)[0], r"^VDD's Codex hook: not trusted, ", without)
                self.cached()
                self.assertEqual(self.setup().text, without.text)
                shutil.rmtree(os.path.join(self.codex, "plugins"))

    def test_a_hook_switched_off_skips_the_hash(self):
        """Prevents a hook switched off in /hooks from being reported as
        changed, or in other words than before."""
        self.config(hook_entry(marketplace="vibe-driven-development", content="sha256:other", enabled=False))
        without = self.setup()
        self.assertEqual(self.hook_lines(without), [
            "VDD's Codex hook: switched off, ~/.codex/config.toml says enabled = false for it."])
        self.assertIn(SWITCHED_OFF, without.tells())
        self.assertNotIn(CHANGED_WAIT, without.tells())
        self.cached(marketplace="vibe-driven-development")
        self.assertEqual(self.setup().text, without.text)

    def test_no_installed_copy_cannot_be_verified(self):
        """Prevents a missing installed copy from being reported as changed or
        trusted: Setup names the path it searched and asks for nothing."""
        self.config(hook_entry())
        result = self.setup()
        self.assertEqual(self.hook_lines(result),
                         ["VDD's Codex hook: could not verify, no installed copy at ~/.codex/plugins/cache/mk/vdd."])
        self.assertEqual(result.tells().count(COULD_NOT_VERIFY), 1, result)
        self.assertNotIn(CHANGED_WAIT, result.tells())
        self.assertNotIn(NOT_TRUSTED_WAIT, result.tells())

    def test_setup_writes_nothing_in_the_codex_home(self):
        """Prevents Setup from changing the installed copy, the baseline files
        or config.toml, any of which would turn the trusted hook modified."""
        for content in (GOLDEN, "sha256:other"):
            with self.subTest(content=content):
                self.cached()
                self.config(hook_entry(content=content))
                before = self.codex_home()
                self.setup()
                self.setup("--write")
                self.assertEqual(self.codex_home(), before)
                shutil.rmtree(os.path.join(self.codex, "plugins"))

    def test_the_old_trust_entry_line_is_gone(self):
        """Prevents the line that called a stale approval trusted from coming
        back."""
        self.cached()
        self.config(hook_entry(content="sha256:other"))
        self.assertNotIn("a trust entry is in", self.setup().text)

    TRUST = hook_entry()
    SHAPES = (
        # (shape, the text staged before the trust entry, whether Setup reads the entry)
        ("an array on one line", 'model = "o"\nskills = ["a", "b"]\n', True),
        ("an array on several lines", 'skills = [\n  "a",\n  ["b", "c"],\n]\n', True),
        ("a ] inside a string", 'skills = [\n  "a]",\n  \'b]]\',\n]\n', True),
        ("a multi-line string", 'notes = """\nskills = [\n"""\n', True),
        ("an unbalanced bracket", 'skills = [\n  "a",\n', False),
    )

    def test_config_toml_shapes_beside_a_trust_entry(self):
        """Prevents a Codex user's config.toml with arrays from being misread:
        the entry is read after each well-formed shape, and an unbalanced
        bracket is not understood, never trusted or absent."""
        self.cached()
        for shape, before, read in self.SHAPES:
            with self.subTest(shape=shape):
                self.config(before + self.TRUST)
                result = self.setup()
                if read:
                    self.assertTrusted(result)
                else:
                    self.assertEqual(self.hook_lines(result), [
                        "VDD's Codex hook: could not verify, ~/.codex/config.toml was read but not understood."])
                    self.assertNotIn(NOT_TRUSTED_WAIT, result.tells())

    # --- which installed copy Setup hashes ---

    def versions(self, active, others, marketplace="mk"):
        """The fixture as the active version, and as each other version with
        an empty directory added, so it hashes to EMPTY_DIR_GOLDEN."""
        self.cached(marketplace, active)
        for version in others:
            os.mkdir(os.path.join(self.cached(marketplace, version), "emptydir"))

    def assertPicks(self, active, others):
        self.versions(active, others)
        self.config(hook_entry(content=GOLDEN))
        self.assertTrusted(self.setup())
        self.config(hook_entry(content=EMPTY_DIR_GOLDEN))
        self.assertChanged(self.setup())
        shutil.rmtree(os.path.join(self.codex, "plugins"))

    def test_the_highest_version_is_hashed(self):
        """Prevents Setup from hashing an older copy than the one Codex runs:
        versions compare as versions, a release above its prereleases."""
        for active, others in (("1.10.0", ["1.2.0"]), ("0.16.0", ["0.16.0-beta.9", "0.16.0-beta.13"]),
                               ("0.16.0-beta.13", ["0.16.0-beta.9"]), ("1.0.0-rc.1", ["1.0.0-beta", "1.0.0-alpha.1"]),
                               ("1.0.0-alpha.beta", ["1.0.0-alpha.1", "1.0.0-alpha"])):
            with self.subTest(active=active):
                self.assertPicks(active, others)

    def test_a_local_directory_wins(self):
        """Prevents Setup from hashing a version directory when Codex runs the
        local one."""
        self.assertPicks("local", ["1.10.0"])

    def test_names_codex_does_not_count_are_ignored(self):
        """Prevents a stray directory or file beside the version from making
        the copy unverifiable or hashing the wrong one, a name that ends in a
        newline included."""
        self.versions("1.0.0", ["9.9.9 copy", "_x y"] + ([] if WINDOWS else ["9.9.9\n"]))
        self.box.write(os.path.join(self.codex, "plugins", "cache", "mk", "vdd", "9.9.9"), "a file\n")
        self.config(hook_entry())
        self.assertTrusted(self.setup())

    def test_versions_codex_cannot_order_cannot_be_verified(self):
        """Prevents Setup from guessing between versions Codex orders by a
        comparison that is not a total order: a name that is not SemVer, or
        one with a build part, beside another version."""
        for active, others in (("1.9.0", ["1.9"]), ("1.0.0", ["beta"]), ("1.0.0", ["1.0.1+build.1"])):
            with self.subTest(names=[active] + others):
                self.versions(active, others)
                self.config(hook_entry())
                result = self.setup()
                names = ", ".join(sorted([active] + others))
                self.assertEqual(self.hook_lines(result), [
                    "VDD's Codex hook: could not verify, ~/.codex/plugins/cache/mk/vdd holds versions whose order "
                    "Codex does not fix: %s." % names])
                self.assertEqual(result.tells().count(COULD_NOT_VERIFY), 1, result)
                self.assertNotIn(CHANGED_WAIT, result.tells())
                shutil.rmtree(os.path.join(self.codex, "plugins"))

    def test_each_entry_gets_its_own_line(self):
        """Prevents a user with VDD from two marketplaces from seeing one
        verdict for both."""
        self.cached("one")
        self.cached("two")
        os.mkdir(os.path.join(self.cached("three"), "emptydir"))
        self.config(hook_entry("one") + hook_entry("two", content="sha256:other") + hook_entry("three", enabled=False))
        result = self.setup()
        lines = self.hook_lines(result)
        self.assertEqual(len(lines), 3, result)
        self.assertRegex(lines[0], r"^VDD's Codex hook for vdd@one: trusted, the installed copy at "
                                   r"~/\.codex/plugins/cache/one/vdd/1\.0\.0 ")
        self.assertRegex(lines[1], r"^VDD's Codex hook for vdd@two: changed, ")
        self.assertEqual(lines[2], "VDD's Codex hook for vdd@three: switched off, ~/.codex/config.toml says "
                                   "enabled = false for it.")
        self.assertIn(SWITCHED_OFF, result.tells())
        self.assertEqual(result.tells().count(CHANGED_WAIT), 1, result)

    def test_one_wait_message_in_the_words_for_the_worse_state(self):
        """Prevents a user with two entries from being asked twice, or in the
        words for the milder state."""
        for one, two, wait in ((hook_entry("one"), hook_entry("two", content="sha256:other"), CHANGED_WAIT),
                               (hook_entry("one", trusted=None, content=None, enabled=True),
                                hook_entry("two", content="sha256:other"), CHANGED_WAIT),
                               (hook_entry("one"), hook_entry("two", trusted=None, content=None, enabled=True),
                                NOT_TRUSTED_WAIT)):
            with self.subTest(wait=wait, one=one):
                self.cached("one")
                self.cached("two")
                self.config(one + two)
                tells = self.setup().tells()
                self.assertEqual(tells.count(wait), 1, tells)
                self.assertEqual(tells.count(CHANGED_WAIT) + tells.count(NOT_TRUSTED_WAIT), 1, tells)
                shutil.rmtree(os.path.join(self.codex, "plugins"))

    def test_a_marketplace_without_a_copy_never_waits(self):
        """Prevents an entry left from a removed marketplace from asking the
        user to trust a hook, or from hiding the entry beside it."""
        self.cached("one")
        self.config(hook_entry("one") + hook_entry("gone"))
        result = self.setup()
        lines = self.hook_lines(result)
        self.assertRegex(lines[0], r"^VDD's Codex hook for vdd@one: trusted, ")
        self.assertEqual(lines[1], "VDD's Codex hook for vdd@gone: could not verify, no installed copy at "
                                   "~/.codex/plugins/cache/gone/vdd.")
        self.assertEqual(result.tells().count(COULD_NOT_VERIFY), 1, result)
        self.assertNotIn(CHANGED_WAIT, result.tells())
        self.assertNotIn(NOT_TRUSTED_WAIT, result.tells())

    def test_a_switched_off_entry_beside_a_changed_one(self):
        """Prevents a switched-off entry from silencing the wait another entry
        needs."""
        self.cached("one")
        self.cached("two")
        self.config(hook_entry("one", enabled=False) + hook_entry("two", content="sha256:other"))
        result = self.setup()
        self.assertIn("VDD's Codex hook for vdd@one: switched off, ~/.codex/config.toml says enabled = false for it.",
                      self.hook_lines(result))
        self.assertIn(SWITCHED_OFF, result.tells())
        self.assertEqual(result.tells().count(CHANGED_WAIT), 1, result)


@unittest.skipIf(WINDOWS, "a stubbed git is a POSIX sh script, as in PreflightTest")
class GitVersionTest(ToolTest):
    """Setup's git version check, with git --version stubbed."""

    def setUp(self):
        ToolTest.setUp(self)
        subprocess.run(["git", "init", "-q"], cwd=self.box.proj, check=True)

    def setup_with(self, version):
        real = shutil.which("git")
        self.box.stub("git", "if [ \"$1\" = --version ]; then echo '%s'; exit 0; fi\nexec '%s' \"$@\"\n"
                      % (version, real))
        return self.box.run("setup", "--harness", "claude-code", "--listed", "none", "--glossary-named", "absent",
                            env=self.box.stub_env())

    def test_git_runs_under_the_c_locale(self):
        """Prevents a Setup git call that follows the user's locale: git
        words its messages in that language, and a marker or a line Setup
        reads would no longer match. The stub prints the LC_ALL it runs
        under as the repository root."""
        self.box.stub("git", "if [ \"$1\" = --version ]; then echo 'git version 2.45.0'; exit 0; fi\n"
                      "if [ \"$1\" = rev-parse ] && [ \"$2\" = --show-toplevel ]; then echo \"/lc-$LC_ALL\"; exit 0; fi\n"
                      "exit 1\n")
        result = self.box.run("setup", "--harness", "claude-code", "--listed", "none", "--glossary-named", "absent",
                              env=self.box.stub_env(LC_ALL="de_DE.UTF-8"))
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("The repository root: /lc-C", result.lines, result)

    def test_git_older_than_2_40_fails_setup_and_stops(self):
        """Prevents a loop that cannot fold at its end because git is too
        old: the fold needs git merge-tree --write-tree --merge-base, which
        arrived in git 2.40, so Setup stops before the Planner."""
        result = self.setup_with("git version 2.39.5")
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("git version: 2.39.5, older than the 2.40 VDD needs. Failed.", result.lines)
        tells = [t for t in result.tells() if "git 2.40" in t]
        self.assertEqual(len(tells), 1, result)
        self.assertIn("VDD needs git 2.40 or newer", tells[0])
        self.assertIn("rerun Setup", tells[0])
        self.assertNext(result, "Tell the user verbatim", "stop")

    def test_git_older_than_2_40_still_installs_the_shared_copy(self):
        """Prevents a Brainstormer left without its tool by a git too old for
        the loop, since Setup installs the tool before its git gate:
        --write with git 2.39 fails Setup and installs the Shared
        copy."""
        real = shutil.which("git")
        self.box.stub("git", "if [ \"$1\" = --version ]; then echo 'git version 2.39.5'; exit 0; fi\nexec '%s' \"$@\"\n"
                      % real)
        result = self.box.run("setup", "--harness", "claude-code", "--listed", "none", "--glossary-named", "absent",
                              "--write", env=self.box.stub_env())
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("VDD needs git 2.40 or newer, and this machine has git 2.39.5", result.text)
        self.assertEqual(vddtest_tree(SCRIPTS), vddtest_tree(self.box.shared))

    def hanging_on(self, argument):
        """Setup with a git that sleeps past a one-second timeout when
        argument is its first or second argument, and runs the real git
        otherwise."""
        real = shutil.which("git")
        self.box.stub("git", "if [ \"$1\" = %s ] || [ \"$2\" = %s ]; then exec sleep 30; fi\nexec '%s' \"$@\"\n"
                      % (argument, argument, real))
        return self.box.run("setup", "--harness", "claude-code", "--listed", "none", "--glossary-named", "absent",
                            env=self.box.stub_env(VDD_GIT_TIMEOUT_SECONDS="1"))

    def test_a_repository_check_that_hangs_says_git_did_not_answer(self):
        """Prevents a git that hangs on the repository check read as no
        repository or no git: Setup names the call and the seconds and tells
        the user to find what holds git."""
        result = self.hanging_on("--is-inside-work-tree")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("Git repository: git rev-parse timed out after 1 seconds.", result.lines)
        self.assertIn("git did not answer in time: find what holds it, then rerun Setup.", result.tells())
        self.assertNext(result, "only after doing that, show the user the planned changes above",
                        "setup --harness claude-code", "--write")

    def test_a_version_check_that_hangs_says_git_did_not_answer(self):
        """Prevents a git that hangs on --version read as a git with no
        version: Setup names the call and the seconds and tells the user to
        find what holds git."""
        result = self.hanging_on("--version")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("git version: git --version timed out after 1 seconds. Failed.", result.lines)
        self.assertIn("git did not answer in time: find what holds it, then rerun Setup.", result.tells())
        self.assertNext(result, "only after doing that, show the user the planned changes above",
                        "setup --harness claude-code", "--write")

    def test_2_40_and_vendor_suffixed_versions_pass(self):
        """Prevents a vendor suffix (Apple's, Git for Windows') read as part
        of the version and failing a git that is new enough."""
        for version in ("git version 2.40.0", "git version 2.54.0 (Apple Git-157)", "git version 2.55.0.windows.2"):
            result = self.setup_with(version)
            shown = version[len("git version "):]
            self.assertIn("git version: %s. Passed." % shown, result.lines, result)
            self.assertNotIn("older than the 2.40", result.text)
            self.assertNotIn("stop: no loop can start", result.last)


# Setup's routes, per Harness: the store each case installs the collection
# in (0 its user skill store, 1 its plugin cache, None nowhere), and the
# lines for the user the route prints after the Borrowed-skills line. Generic
# selects "your agent" and hands a plugin cache to the Harness that owns it.
CASES = {
    "present": (0, ("writing-for-agents", "yes")),
    "not present": (None, ("", "absent")),
    "reinstall": (0, ("", "absent", "--user-answer", "does-not-resolve")),
    "plugin": (1, ("", "absent", "--user-answer", "does-not-resolve")),
    "update": (0, ("writing-for-agents", "no")),
    "update plugin": (1, ("writing-for-agents", "no")),
}
CODEX_CACHE = (".codex", "plugins", "cache", "mk", "mattpocock-skills", "1.0", "skills")
CODEX_PLUGIN = ("Run codex plugin add mattpocock-skills@mk, then start a new Codex Session and rerun $vdd:vdd-setup "
                "there.")
CODEX_UPDATE = ("Update it: codex plugin marketplace upgrade mk, then codex plugin add mattpocock-skills@mk, then "
                "start a new Codex Session.")
ROUTES = {
    "claude-code": {
        "header": "Claude Code",
        "stores": ((".claude", "skills"), (".claude", "plugins", "cache", "mk", "mattpocock-skills", "1.0", "skills")),
        "not present": "Install Matt Pocock's collection: /plugin marketplace add mattpocock/skills, then /plugin "
                       "install mattpocock-skills@mattpocock, then turn on auto-update for the mattpocock marketplace "
                       "under /plugin > Marketplaces (auto-update is off by default for every marketplace but "
                       "Anthropic's own).",
        "reinstall": "Re-run the install and select Claude Code: npx skills@latest add -g mattpocock/skills, then "
                     "start a new Claude Code Session.",
        "plugin": "Run claude plugin enable mattpocock-skills@mk from the repository root, then start a new Claude "
                  "Code Session. If the plugin is enabled and still not loaded, reinstall it.",
        "update": "Update it: npx skills update -g",
        "update plugin": "Update it: claude plugin marketplace update mk, then claude plugin update mattpocock-skills "
                         "(inside a Claude Code Session the first half is /plugin marketplace update mk).",
    },
    "codex": {
        "header": "Codex",
        "stores": ((".agents", "skills"), CODEX_CACHE),
        "not present": "Install Matt Pocock's collection: npx skills@latest add -g mattpocock/skills, selecting Codex "
                       "when the installer asks which agents to install for, then start a new Codex Session: a skill "
                       "added while a Session runs appears only in a new one. Rerun $vdd:vdd-setup there.",
        "reinstall": "First start a new Codex Session: a skill added while a Session runs appears only in a new one. "
                     "If the new Session still cannot run it, re-run the install and select Codex: npx skills@latest "
                     "add -g mattpocock/skills, then start a new Codex Session and rerun $vdd:vdd-setup there.",
        "plugin": CODEX_PLUGIN,
        "update": "Update it: npx skills update -g, then start a new Codex Session.",
        "update plugin": CODEX_UPDATE,
    },
    "cursor": {
        "header": "Cursor",
        "stores": ((".cursor", "skills"), (".cursor", "plugins", "cache", "mk", "mattpocock-skills", "1.0", "skills")),
        "not present": "Install Matt Pocock's collection: npx skills@latest add -g mattpocock/skills, selecting Cursor "
                       "when the installer asks which agents to install for, then open a new chat or a new agent "
                       "Session before you rerun /vdd-setup.",
        "reinstall": "First open a new chat or a new agent Session. If that still cannot run it, re-run the install "
                     "and select Cursor: npx skills@latest add -g mattpocock/skills, then open a new chat or a new "
                     "agent Session.",
        "plugin": "Reinstall the plugin in the Cursor IDE's plugin UI, then open a new chat or a new agent Session. "
                  "Cursor has no command-line route for this.",
        "update": "Update it: npx skills update -g",
        "update plugin": "Update it: refresh the plugin in the Cursor IDE's plugin UI.",
    },
    "copilot-cli": {
        "header": "Copilot CLI",
        "stores": ((".copilot", "skills"), (".copilot", "installed-plugins", "mk", "mattpocock-skills", "skills")),
        "not present": "Install Matt Pocock's collection: npx skills@latest add -g mattpocock/skills, selecting GitHub "
                       "Copilot when the installer asks which agents to install for. Then run /skills reload or a new "
                       "copilot Session before you rerun /vdd:vdd-setup.",
        "reinstall": "First run /skills reload or a new copilot Session. If that still cannot run it, re-run the "
                     "install and select GitHub Copilot: npx skills@latest add -g mattpocock/skills. Then run "
                     "/skills reload or a new copilot Session.",
        "plugin": "Run copilot plugin enable mattpocock-skills@mk, then start a new copilot Session.",
        "update": "Update it: npx skills update -g",
        "update plugin": "Update it: copilot plugin update mattpocock-skills@mk",
    },
    "generic": {
        "header": "generic",
        "stores": ((".agents", "skills"), CODEX_CACHE),
        "not present": "Install Matt Pocock's collection: npx skills@latest add -g mattpocock/skills, selecting your "
                       "agent when the installer asks.",
        "reinstall": "Re-run the install and select your agent: npx skills@latest add -g mattpocock/skills",
        "plugin": CODEX_PLUGIN,
        "update": "Update it: npx skills update -g",
        "update plugin": CODEX_UPDATE,
    },
}


class SetupRoutesTest(ToolTest):
    """Every route each Harness's module prints, walked through Setup in one
    table. Before it only Codex's and Generic's reinstall routes were run:
    Cursor's not-present and reinstall routes, Copilot's not-present route
    and Generic's "selecting your agent" could break with no test noticing."""

    def test_every_route_of_every_harness(self):
        self.assertEqual(sorted(ROUTES), sorted(["claude-code", "codex", "cursor", "copilot-cli", "generic"]))
        for name, routes in ROUTES.items():
            for case, (store, answers) in CASES.items():
                with self.subTest(harness=name, route=case):
                    self.walk(name, routes, case, store, answers)

    def walk(self, name, routes, case, store, answers):
        box = vddtest.Sandbox()
        self.addCleanup(box.cleanup)
        subprocess.run(["git", "init", "-q"], cwd=box.proj, check=True)
        if store is not None:
            for skill in SKILLS:
                box.write(os.path.join(box.home, *(routes["stores"][store] + (skill, "SKILL.md"))),
                          "---\nname: %s\n---\n" % skill, base=box.root)
        result = box.run("setup", "--harness", name, "--listed", answers[0], "--glossary-named", answers[1],
                         *answers[2:])
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("Setup, Harness %s (dry run, nothing is changed yet)." % routes["header"], result.lines)
        tells = result.tells()
        if case == "present":
            self.assertIn("Borrowed skills: all 11 Present and Resolvable. Passed.", result.lines, result)
            self.assertFalse([t for t in tells if "Matt Pocock's collection" in t], result)
            return
        if case == "not present":
            self.assertIn("Borrowed skills Not Present: %s." % ", ".join(SKILLS), result.lines, result)
            previous = None
        elif case.startswith("update"):
            previous = next(t for t in tells if t.startswith("Warning: your copy of Matt Pocock's collection"))
        else:
            reads = "your agent" if name == "generic" else routes["header"]
            previous = next(t for t in tells if t.startswith("Matt Pocock's collection sits in "))
            self.assertIn("which %s reads, and this Session has not loaded them." % reads, previous)
        route = tells[tells.index(previous) + 1] if previous else next(t for t in tells if t.startswith("Install "))
        self.assertEqual(route, routes[case], result)
