"""Seam 1: the setup command, driven from outside."""

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
        Code reads, and the search moves with them (180854c)."""
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
        """Copilot CLI reads ~/.agents/skills only while COPILOT_HOME is unset
        (180854c)."""
        self.skills_in(self.store(".agents", "skills"))
        result = self.setup("copilot-cli", "writing-for-agents", "yes")
        self.assertIn("all 11 Present and Resolvable", result.text)

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

    def test_outside_a_repository_the_shared_copy_is_still_installed(self):
        """Prevents a Brainstormer left without its tool by a failed git
        check (ticket 97's decision: Setup installs the tool before its git
        gate): --write outside a repository installs the Shared copy."""
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
        docs/PLAN.md and !PLAN.md are the user's own (6106fb6)."""
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
        self.assertTrue(result.last.startswith("Next: If a sandbox refused it"), result)

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
    """Setup on Codex: the hooks.json migration and the trust check."""

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
        self.assertIn("Trust VDD's hook in /hooks.", result.tells())
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
        result = self.setup("--write")
        self.assertIn("naming vdd-codex-stop that Setup did not write stays: python3 /mine/vdd-codex-stop.py", result.text)
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

    def test_a_registration_in_config_toml_is_reported(self):
        self.config('[[hooks.Stop]]\n[[hooks.Stop.hooks]]\ncommand = "sh /x/vdd-codex-stop.sh"\n')
        self.assertIn("a registration naming vdd-codex-stop stays", self.setup().text)

    def test_trust_key_present_prints_no_trust_line(self):
        """The trust check looks for the hooks.state key of VDD's hook and
        never claims the hook is trusted."""
        for text in (
            '[hooks.state."vdd@anything:plugin.json#hooks[0]:stop:0:0"]\ntrusted_hash = "sha256:x"\n',
            '[hooks.state]\n"vdd@mk:plugin.json#hooks[0]:stop:0:0" = { trusted_hash = "sha256:x" }\n',
            '[hooks]\nstate."vdd@mk:plugin.json#hooks[0]:stop:0:0".trusted_hash = "sha256:x"\n',
            'model = "o"\n[hooks.state."/x/hooks.json:stop:0:0"]\ntrusted_hash = "a"\n'
            '[hooks.state."vdd@mk:plugin.json#hooks[0]:stop:0:0"]\ntrusted_hash = "b"\n',
        ):
            with self.subTest(text=text):
                self.config(text)
                result = self.setup()
                self.assertNotIn("Trust VDD's hook in /hooks.", result.tells())
                self.assertFalse(any("unknown" in l for l in result.lines), result)

    def test_a_hook_switched_off_in_hooks_is_named(self):
        """Switching VDD's hook off in /hooks keeps its hooks.state key and
        adds enabled = false; Setup read that as a trust entry, and on the
        Windows VM the Codex Doorbells would have waited for a paste."""
        for text in (
            '[hooks.state."vdd@vibe-driven-development:plugin.json#hooks[0]:stop:0:0"]\n'
            'trusted_hash = "sha256:x"\nenabled = false\n',
            '[hooks.state]\n"vdd@mk:plugin.json#hooks[0]:stop:0:0" = { trusted_hash = "x", enabled = false }\n',
            '[hooks]\nstate."vdd@mk:plugin.json#hooks[0]:stop:0:0".enabled = false\n',
        ):
            with self.subTest(text=text):
                self.config(text)
                result = self.setup()
                self.assertIn("VDD's hook is switched off in Codex: turn it on in /hooks, or every Doorbell "
                              "waits for a paste.", result.tells())
                self.assertNotIn("Trust VDD's hook in /hooks.", result.tells())
                self.assertFalse(any("a trust entry is in" in l for l in result.lines), result)
        self.config('[hooks.state."vdd@mk:plugin.json#hooks[0]:stop:0:0"]\ntrusted_hash = "x"\nenabled = true\n')
        self.assertIn("a trust entry is in", self.setup().text)

    def test_trust_key_absent_prints_the_trust_line(self):
        for text in ("", '[hooks.state."/x/hooks.json:stop:0:0"]\ntrusted_hash = "a"\n',
                     '[hooks.state."other@mk:plugin.json#hooks[0]:stop:0:0"]\n',
                     'notes = """\n[hooks.state."vdd@mk:plugin.json#hooks[0]:stop:0:0"]\n"""\n'):
            with self.subTest(text=text):
                self.config(text)
                self.assertIn("Trust VDD's hook in /hooks.", self.setup().tells())

    def test_an_unparsable_config_says_unknown_and_asks(self):
        self.config('[hooks.state\nx = "y\n')
        result = self.setup()
        self.assertNotIn("Trust VDD's hook in /hooks.", result.tells())
        self.assertTrue(any("could not tell whether VDD's hook is trusted" in t for t in result.tells()), result)

    def test_codex_home_moves_the_files(self):
        home = os.path.join(self.box.root, "ch")
        os.makedirs(home)
        with open(os.path.join(home, "hooks.json"), "w") as handle:
            json.dump({"hooks": {"Stop": [self.vdd_group()]}}, handle)
        result = self.box.run("setup", "--harness", "codex", "--listed", "writing-for-agents",
                              "--glossary-named", "yes", env=self.box.env(CODEX_HOME=home))
        self.assertIn("removes VDD's old Stop hook entry", result.text)

    def test_other_harnesses_skip_the_codex_steps(self):
        self.hooks({"hooks": {"Stop": [self.vdd_group()]}})
        result = self.setup(harness="claude-code")
        self.assertNotIn("hooks.json", result.text)
        self.assertNotIn("Trust VDD's hook", result.text)


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
        the loop (ticket 97's decision: Setup installs the tool before its
        git gate): --write with git 2.39 fails Setup and installs the Shared
        copy."""
        real = shutil.which("git")
        self.box.stub("git", "if [ \"$1\" = --version ]; then echo 'git version 2.39.5'; exit 0; fi\nexec '%s' \"$@\"\n"
                      % real)
        result = self.box.run("setup", "--harness", "claude-code", "--listed", "none", "--glossary-named", "absent",
                              "--write", env=self.box.stub_env())
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("git version: 2.39.5, older than the 2.40 VDD needs. Failed.", result.lines)
        self.assertEqual(vddtest_tree(SCRIPTS), vddtest_tree(self.box.shared))

    def test_2_40_and_vendor_suffixed_versions_pass(self):
        """Prevents a vendor suffix (Apple's, Git for Windows') read as part
        of the version and failing a git that is new enough."""
        for version in ("git version 2.40.0", "git version 2.54.0 (Apple Git-157)", "git version 2.55.0.windows.2"):
            result = self.setup_with(version)
            shown = version[len("git version "):]
            self.assertIn("git version: %s. Passed." % shown, result.lines, result)
            self.assertNotIn("older than the 2.40", result.text)
            self.assertNotIn("stop: no loop can start", result.last)
