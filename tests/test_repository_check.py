"""The repository check against a clean copy staged in a temporary git
repository: each Invariant's test breaks the copy one way and expects the
check to refuse it, and the clean copy passes."""

import os
import subprocess
import sys
import tempfile
import unittest

from vddtest import REPO, remove_tree

SCRIPT = os.path.join(REPO, ".github", "scripts", "check_repository.py")

# Copied from this repository, so the mutations below run on the real files.
COPIED = (
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".codex-plugin/plugin.json",
    ".github/workflows/verify.yml",
    ".github/workflows/release.yml",
)

START = "An Orchestrator hosts this Workflow."
HOSTED_CHECK = 'If the prompt that started you does not say "%s", stop.\n' % START

CLEAN = {
    "README.md": "# x\n",
    "AGENTS.md": "# x\n",
    "CLAUDE.md": "@AGENTS.md\n",
    "LICENSE": "MIT\n",
    ".gitignore": ".scratch/\n",
    "tests/test_x.py": "import json\n",
    "skills/vdd-orchestrator/SKILL.md": (
        "---\nname: vdd-orchestrator\ndescription: hosts\ndisable-model-invocation: true\n---\n\n"
        "You are the <Role> in a Vibe Driven Development loop. %s\n\n"
        "Read [the template](references/<slug>.md) and [the guide](references/guide.md#top).\n\n"
        "## Harnesses\n\n"
        "- Claude Code: [`references/harness-claude-code.md`](references/harness-claude-code.md)\n"
        "- Codex: [`references/harness-codex.md`](references/harness-codex.md)\n\n"
        "## Next\n" % START
    ),
    "skills/vdd-orchestrator/references/guide.md": "See [the Codex file](harness-codex.md) and [the site](https://example.com).\n",
    "skills/vdd-orchestrator/references/harness-claude-code.md": "x\n",
    "skills/vdd-orchestrator/references/harness-codex.md": "x\n",
    "skills/vdd-orchestrator/agents/openai.yaml": (
        "# policy\ninterface:\n  display_name: x\npolicy:\n  allow_implicit_invocation: false\n"
    ),
    "skills/vdd-plan-reviewer/SKILL.md": "---\nname: vdd-plan-reviewer\ndescription: x\n---\n\n" + HOSTED_CHECK,
    "skills/vdd-coder/SKILL.md": "---\nname: vdd-coder\ndescription: x\n---\n\n" + HOSTED_CHECK,
    "skills/vdd-code-reviewer/SKILL.md": (
        "---\nname: vdd-code-reviewer\ndescription: x\n---\n\n" + HOSTED_CHECK + "\n## Harnesses\n\n"
        "- Claude Code: none: the inline text is complete\n"
        "- Codex: [`references/harness-codex.md`](references/harness-codex.md)\n"
    ),
    "skills/vdd-code-reviewer/references/harness-codex.md": "x\n",
    "skills/vdd-setup/SKILL.md": "---\nname: vdd-setup\ndescription: x\n---\n\nRun [the tool](scripts/vdd.py).\n",
    "skills/vdd-setup/scripts/vdd.py": "import sys\n",
}


class RepositoryCheck(unittest.TestCase):
    """A staged repository the check runs against as its own process."""

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="vdd-repo-check-")
        self.addCleanup(remove_tree, self.repo)
        self.repo_git("init", "-q")
        for path in COPIED:
            with open(os.path.join(REPO, path), "rb") as handle:
                self.add(path, handle.read())
        for path, text in CLEAN.items():
            self.add(path, text)

    def repo_git(self, *args, data=None):
        return subprocess.run(
            ["git", "-c", "core.autocrlf=false"] + list(args),
            cwd=self.repo,
            input=data,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout

    def add(self, path, data):
        full = os.path.join(self.repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(data.encode("utf-8") if isinstance(data, str) else data)
        self.repo_git("add", "--", path)

    def read(self, path):
        """The file as text with LF line ends, so an edit matches on a Windows
        checkout, whose core.autocrlf wrote the copied files with CRLF."""
        with open(os.path.join(self.repo, path), "rb") as handle:
            return handle.read().decode("utf-8").replace("\r\n", "\n")

    def edit(self, path, old, new):
        text = self.read(path)
        self.assertIn(old, text, "the fixture no longer holds the text the test edits")
        self.add(path, text.replace(old, new, 1))

    def check(self):
        proc = subprocess.run(
            [sys.executable, "-B", SCRIPT, self.repo],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")

    def assertPasses(self):
        code, text = self.check()
        self.assertEqual(code, 0, text)

    def assertFails(self, *needles):
        code, text = self.check()
        self.assertEqual(code, 1, text)
        for needle in needles:
            self.assertIn(needle, text)


class CleanCopyTest(RepositoryCheck):
    def test_the_clean_copy_passes(self):
        self.assertPasses()

    def test_this_repository_passes(self):
        """Prevents a check that refuses the repository it guards."""
        proc = subprocess.run(
            [sys.executable, "-B", SCRIPT, REPO], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.assertEqual(proc.returncode, 0, proc.stdout.decode() + proc.stderr.decode())

    def test_gitignored_files_never_count(self):
        """Prevents an untracked scratch file from failing the check: this
        checkout holds thousands under .scratch/."""
        os.makedirs(os.path.join(self.repo, "skills", "x"))
        with open(os.path.join(self.repo, "skills", "x", "notes.txt"), "w") as handle:
            handle.write("x\n")
        self.assertPasses()


class ManifestsTest(RepositoryCheck):
    def test_version_drift_fails(self):
        """Prevents a release whose manifests name two versions."""
        self.edit(".codex-plugin/plugin.json", '"version": "', '"version": "9')
        self.assertFails(".codex-plugin/plugin.json version differs")

    def test_a_marketplace_version_drift_fails(self):
        """Prevents a marketplace entry that installs another version."""
        self.edit(".claude-plugin/marketplace.json", '"version": "', '"version": "9')
        self.assertFails("version drift: marketplace")

    def test_a_source_other_than_this_repository_fails(self):
        """Prevents a marketplace entry that installs from elsewhere."""
        self.edit(".claude-plugin/marketplace.json", '"source": "./"', '"source": "./x"')
        self.assertFails('expected "./"')

    def test_a_drifted_shared_field_fails(self):
        """Prevents a field Codex reads from its own manifest drifting."""
        self.edit(".codex-plugin/plugin.json", '"license": "MIT"', '"license": "GPL"')
        self.assertFails(".codex-plugin/plugin.json license differs")

    def test_a_missing_repeated_field_fails(self):
        self.edit(".codex-plugin/plugin.json", '"license": "MIT",', "")
        self.assertFails("license is missing from .codex-plugin/plugin.json")

    def test_invalid_json_fails(self):
        """Prevents a manifest that breaks install for every user."""
        self.add(".claude-plugin/plugin.json", "{")
        self.assertFails("missing or invalid JSON: .claude-plugin/plugin.json")


class FrontmatterTest(RepositoryCheck):
    def test_a_skill_without_frontmatter_fails(self):
        """Prevents a skill no Harness can find."""
        self.add("skills/vdd-setup/SKILL.md", "# vdd-setup\n")
        self.assertFails("missing frontmatter: skills/vdd-setup/SKILL.md")

    def test_a_missing_description_fails(self):
        self.add("skills/vdd-setup/SKILL.md", "---\nname: vdd-setup\n---\n")
        self.assertFails("missing description in the frontmatter: skills/vdd-setup/SKILL.md")

    def test_a_name_only_in_the_body_fails(self):
        """Prevents a body line passing for the frontmatter's name."""
        self.add("skills/vdd-setup/SKILL.md", "---\ndescription: x\n---\n\nname: vdd-setup\n")
        self.assertFails("missing name in the frontmatter: skills/vdd-setup/SKILL.md")

    def test_a_byte_order_mark_is_read(self):
        """Prevents a SKILL.md saved with a BOM from reading as one without
        frontmatter."""
        self.add("skills/vdd-setup/SKILL.md", "\ufeff---\nname: vdd-setup\ndescription: x\n---\n")
        self.assertPasses()

    def test_crlf_line_ends_are_read(self):
        self.add("skills/vdd-setup/SKILL.md", "---\r\nname: vdd-setup\r\ndescription: x\r\n---\r\n")
        self.assertPasses()

    def test_a_leading_space_fence_fails(self):
        """Prevents an indented fence, which a Harness does not read as
        frontmatter, passing for one."""
        self.add("skills/vdd-setup/SKILL.md", "  ---\nname: vdd-setup\ndescription: x\n---\n")
        self.assertFails("missing frontmatter: skills/vdd-setup/SKILL.md")

    def test_a_trailing_space_fence_fails(self):
        """Prevents a padded closing fence passing for one."""
        self.add("skills/vdd-setup/SKILL.md", "---\nname: vdd-setup\ndescription: x\n--- \n")
        self.assertFails("missing frontmatter: skills/vdd-setup/SKILL.md")


class UniqueNamesTest(RepositoryCheck):
    def test_a_duplicate_name_fails(self):
        """Prevents `npx skills add` clobbering one skill with another."""
        self.edit("skills/vdd-setup/SKILL.md", "name: vdd-setup", "name: vdd-coder")
        self.assertFails("duplicate skill name vdd-coder")

    def test_a_body_name_line_in_two_skills_is_no_duplicate(self):
        """Prevents a body line `name: x` counting as a skill name."""
        self.add("skills/vdd-setup/SKILL.md", CLEAN["skills/vdd-setup/SKILL.md"] + "\nname: x\n")
        self.add("skills/vdd-coder/SKILL.md", CLEAN["skills/vdd-coder/SKILL.md"] + "\nname: x\n")
        self.assertPasses()


class RelativeLinksTest(RepositoryCheck):
    def test_a_broken_link_in_a_reference_file_fails(self):
        """Prevents a link that strands its reader."""
        self.edit("skills/vdd-orchestrator/references/guide.md", "harness-codex.md", "harness-gone.md")
        self.assertFails("skills/vdd-orchestrator/references/guide.md: link resolves to nothing: harness-gone.md")

    def test_a_link_to_an_untracked_file_fails(self):
        """Prevents a link to a file on the maintainer's disk that does not
        ship."""
        with open(os.path.join(self.repo, "skills", "vdd-setup", "local.md"), "w") as handle:
            handle.write("x\n")
        self.edit("skills/vdd-setup/SKILL.md", "Run [the tool]", "See [local](local.md). Run [the tool]")
        self.assertFails("skills/vdd-setup/SKILL.md: link resolves to nothing: local.md")


class ReferenceLinksTest(RepositoryCheck):
    def test_an_unlinked_reference_file_fails(self):
        """Prevents a Reference file no reader is sent to."""
        self.add("skills/vdd-setup/references/orphan.md", "x\n")
        self.assertFails("skills/vdd-setup/references/orphan.md: no direct link from skills/vdd-setup/SKILL.md")

    def test_a_link_from_another_reference_file_is_not_enough(self):
        self.edit("skills/vdd-orchestrator/SKILL.md", "- Codex: [`references/harness-codex.md`](references/harness-codex.md)\n", "- Codex: none: the inline text is complete\n")
        self.assertFails("skills/vdd-orchestrator/references/harness-codex.md: no direct link")

    def test_a_skill_directory_without_a_skill_file_fails(self):
        self.add("skills/stray/references/x.md", "x\n")
        self.assertFails("skills/stray: no SKILL.md")


class ReferenceSizeTest(RepositoryCheck):
    def test_a_reference_file_over_8_kb_fails(self):
        """Prevents a Reference file a Harness truncates."""
        self.add("skills/vdd-orchestrator/references/guide.md", "x" * 8193)
        self.assertFails("skills/vdd-orchestrator/references/guide.md: 8193 bytes, over 8 KB")

    def test_a_reference_file_of_8_kb_passes(self):
        self.add("skills/vdd-orchestrator/references/guide.md", "x" * 8192)
        self.assertPasses()


class HarnessIndexTest(RepositoryCheck):
    def test_a_harness_left_out_fails(self):
        """Prevents a Harness file that sends one Harness's reader nowhere."""
        self.add("skills/vdd-code-reviewer/references/harness-cursor.md", "x\n")
        self.edit(
            "skills/vdd-code-reviewer/SKILL.md",
            "## Harnesses\n\n",
            "## Harnesses\n\n- Cursor: [`references/harness-cursor.md`](references/harness-cursor.md)\n",
        )
        self.assertFails("skills/vdd-orchestrator/SKILL.md: ## Harnesses has no entry for cursor")

    def test_a_missing_harnesses_section_fails(self):
        self.edit("skills/vdd-code-reviewer/SKILL.md", "## Harnesses", "## Hosts")
        self.assertFails("skills/vdd-code-reviewer/SKILL.md: ships a Harness file and has no ## Harnesses section")


class UserInvokedPairsTest(RepositoryCheck):
    def test_the_frontmatter_half_alone_fails(self):
        """Prevents a skill model-invocable on Codex."""
        self.edit("skills/vdd-orchestrator/agents/openai.yaml", "false", "true")
        self.assertFails("skills/vdd-orchestrator: disable-model-invocation: true but")

    def test_the_policy_half_alone_fails(self):
        """Prevents a skill model-invocable on Claude Code."""
        self.edit("skills/vdd-orchestrator/SKILL.md", "disable-model-invocation: true\n", "")
        self.assertFails("but the frontmatter lacks disable-model-invocation: true")

    def test_no_policy_file_fails(self):
        self.repo_git("rm", "-q", "--cached", "skills/vdd-orchestrator/agents/openai.yaml")
        self.assertFails("skills/vdd-orchestrator: disable-model-invocation: true and no agents/openai.yaml")

    def test_a_mixed_ending_skill_with_a_broken_pair_fails(self):
        """Prevents a CRLF line hiding the frontmatter, and with it the half
        it holds."""
        self.add(
            "skills/vdd-orchestrator/SKILL.md",
            CLEAN["skills/vdd-orchestrator/SKILL.md"].replace("---\nname", "---\r\nname", 1).replace("true\n", "true\r\n", 1),
        )
        self.edit("skills/vdd-orchestrator/agents/openai.yaml", "false", "true")
        self.assertFails("skills/vdd-orchestrator: disable-model-invocation: true but")

    def test_a_mixed_ending_skill_with_a_whole_pair_passes(self):
        self.add(
            "skills/vdd-orchestrator/SKILL.md",
            CLEAN["skills/vdd-orchestrator/SKILL.md"].replace("---\nname", "---\r\nname", 1).replace("true\n", "true\r\n", 1),
        )
        self.assertPasses()


class StartSentenceTest(RepositoryCheck):
    def test_a_changed_spawn_prompt_fails(self):
        """Prevents every spawn refusing to start."""
        self.edit("skills/vdd-orchestrator/SKILL.md", START, "An Orchestrator runs this Workflow.")
        self.assertFails("skills/vdd-orchestrator/SKILL.md: the Spawn prompt lacks")

    def test_a_changed_start_check_fails(self):
        self.edit("skills/vdd-coder/SKILL.md", START, "An Orchestrator runs this Workflow.")
        self.assertFails("skills/vdd-coder/SKILL.md: the start check lacks")


class ClaudeMdTest(RepositoryCheck):
    def test_a_house_rule_in_claude_md_fails(self):
        """Prevents a rule Claude Code reads that other Harnesses never see."""
        self.add("CLAUDE.md", "@AGENTS.md\n\nNever merge.\n")
        self.assertFails("CLAUDE.md must contain exactly the line: @AGENTS.md")

    def test_a_byte_order_mark_fails(self):
        """Prevents a CLAUDE.md that is not the one line @AGENTS.md byte for
        byte."""
        self.add("CLAUDE.md", b"\xef\xbb\xbf@AGENTS.md\n")
        self.assertFails("CLAUDE.md must contain exactly the line: @AGENTS.md")

    def test_a_crlf_line_end_fails(self):
        self.add("CLAUDE.md", b"@AGENTS.md\r\n")
        self.assertFails("CLAUDE.md must contain exactly the line: @AGENTS.md")

    def test_a_crlf_checkout_of_the_tracked_line_passes(self):
        """Prevents the check refusing a Windows checkout: core.autocrlf
        writes CLAUDE.md with CRLF while git holds the one line."""
        with open(os.path.join(self.repo, "CLAUDE.md"), "wb") as handle:
            handle.write(b"@AGENTS.md\r\n")
        self.assertPasses()


class ExecutableSurfaceTest(RepositoryCheck):
    def test_an_executable_file_fails(self):
        """Prevents an executable on every installer's machine. Mode from the
        git index, so the fixture works on Windows too."""
        self.repo_git("update-index", "--chmod=+x", "tests/test_x.py")
        self.assertFails("executable in distributed content: tests/test_x.py")

    def test_a_symlink_fails(self):
        blob = self.repo_git("hash-object", "-w", "--stdin", data=b"README.md").decode().strip()
        self.repo_git("update-index", "--add", "--cacheinfo", "120000,%s,docs/link.md" % blob)
        self.assertFails("symlink in distributed content: docs/link.md")

    def test_a_hook_in_the_claude_manifest_fails(self):
        self.edit(".claude-plugin/plugin.json", '"license"', '"hooks": {}, "license"')
        self.assertFails(".claude-plugin/plugin.json declares hooks or MCP servers")

    def test_an_mcp_config_file_fails(self):
        self.add("docs/.mcp.json", "{}\n")
        self.assertFails("unexpected hook or MCP config: docs/.mcp.json")

    def test_a_file_under_skills_not_at_644_fails(self):
        """Prevents a shipped file that runs as a program of its own."""
        self.repo_git("update-index", "--chmod=+x", "skills/vdd-setup/scripts/vdd.py")
        self.assertFails("mode 100755, not 100644, under skills/: skills/vdd-setup/scripts/vdd.py")


class CodexHookTest(RepositoryCheck):
    def test_a_changed_hook_command_fails(self):
        """Prevents a hook every Codex user has to trust again."""
        self.edit(".codex-plugin/plugin.json", '"timeout": 2760', '"timeout": 60')
        self.assertFails("hooks is not exactly the one Codex Stop hook in its fixed form")

    def test_an_mcp_server_fails(self):
        self.edit(".codex-plugin/plugin.json", '"license"', '"mcpServers": {}, "license"')
        self.assertFails(".codex-plugin/plugin.json declares MCP servers")


class SkillHooksTest(RepositoryCheck):
    def test_a_hooks_key_in_a_skill_frontmatter_fails(self):
        """Prevents a second hook: Claude Code registers a skill's frontmatter
        hooks when the skill runs, plugin skills included."""
        for text in (
            "---\nname: vdd-setup\ndescription: x\nhooks:\n  Stop:\n    - hooks: []\n---\n",
            "---\r\nname: vdd-setup\r\ndescription: x\r\n'hooks': {}\r\n---\r\n",
            "\ufeff---\nname: vdd-setup\ndescription: x\nmetadata:\n  hooks: x\n---\n",
        ):
            with self.subTest(text=text):
                self.add("skills/vdd-setup/SKILL.md", text)
                self.assertFails("skills/vdd-setup/SKILL.md:", "hooks key in the frontmatter")

    def test_hooks_below_the_frontmatter_pass(self):
        self.add("skills/vdd-setup/SKILL.md", "---\nname: vdd-setup\ndescription: x\n---\n\nhooks: the word in the body\n")
        self.assertPasses()


class PolicyKeysTest(RepositoryCheck):
    def test_a_dependencies_key_fails(self):
        """Prevents a policy file that declares tools or MCP servers."""
        self.edit("skills/vdd-orchestrator/agents/openai.yaml", "policy:", "dependencies:\n  tools: []\npolicy:")
        self.assertFails("top-level key other than interface and policy: dependencies:")

    def test_an_indented_first_key_fails(self):
        self.edit("skills/vdd-orchestrator/agents/openai.yaml", "interface:", "  interface:")
        self.assertFails("top-level keys must start at column 0")


class FileKindsTest(RepositoryCheck):
    def test_a_js_file_under_skills_fails(self):
        """Prevents shipped code that runs without a named interpreter."""
        self.add("skills/vdd-setup/scripts/helper.js", "console.log(1)\n")
        self.assertFails("file kind not allowed under skills/ (only .md, agents/openai.yaml and .py): skills/vdd-setup/scripts/helper.js")

    def test_a_shell_script_under_skills_fails(self):
        """The 0.15 .sh and .ps1 scripts went with the Codex hook's move; new
        shipped code is .py."""
        self.add("skills/vdd-setup/references/wait.sh", "echo x\n")
        self.add("skills/vdd-setup/references/wait.ps1", "exit 0\n")
        self.assertFails("wait.sh", "wait.ps1")

    def test_a_txt_file_at_the_root_fails(self):
        self.add("notes.txt", "x\n")
        self.assertFails("file kind not allowed: notes.txt")


class WriteAccessTest(RepositoryCheck):
    VERIFY = ".github/workflows/verify.yml"
    RELEASE = ".github/workflows/release.yml"

    # T60's five mutations of verify.yml.

    def test_pull_request_target_fails(self):
        """Prevents verify.yml running PR-head content with write access and
        secrets."""
        self.edit(self.VERIFY, "  pull_request:\n", "  pull_request_target:\n")
        self.assertFails("verify.yml: names pull_request_target", "expected push and pull_request")

    def test_the_permissions_block_removed_fails(self):
        """Prevents verify.yml falling back to the repository's default
        token permissions."""
        self.edit(self.VERIFY, "permissions:\n  contents: read\n", "")
        self.assertFails("verify.yml: workflow-level permissions are None")

    def test_pull_requests_write_fails(self):
        """Prevents a write scope other than contents slipping in."""
        self.edit(self.VERIFY, "  contents: read\n", "  contents: read\n  pull-requests: write\n")
        self.assertFails("verify.yml:", "grants write access", "pull-requests: write")

    def test_a_quoted_contents_write_fails(self):
        """Prevents a quoted value hiding a write grant from the text check."""
        self.edit(self.VERIFY, "  contents: read\n", '  contents: "write"\n')
        self.assertFails('contents: "write"', "expected contents: read alone")

    def test_push_narrowed_to_master_fails(self):
        """Prevents a branch showing no check before its PR exists."""
        self.edit(self.VERIFY, "branches: ['**']", "branches: [master]")
        self.assertFails("verify.yml: push filters are")

    # The release workflow.

    def test_a_job_level_write_in_verify_fails(self):
        self.edit(self.VERIFY, "    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    permissions: { contents: write }\n")
        self.assertFails("verify.yml:", "grants write access")

    def test_a_pull_request_trigger_in_release_fails(self):
        """Prevents release.yml running PR-head content with write access."""
        self.edit(self.RELEASE, "  workflow_dispatch:\n", "  workflow_dispatch:\n  pull_request:\n")
        self.assertFails("release.yml: names a pull_request trigger", "expected push and workflow_dispatch")

    def test_a_push_to_branches_in_release_fails(self):
        self.edit(self.RELEASE, "    tags: ['v*.*.*']\n", "    tags: ['v*.*.*']\n    branches: [master]\n")
        self.assertFails("release.yml: push filters are")

    def test_a_write_in_the_notes_job_fails(self):
        """Prevents write access outside the release job."""
        self.edit(self.RELEASE, "    timeout-minutes: 5\n    outputs:", "    timeout-minutes: 5\n    permissions:\n      contents: write\n    outputs:")
        self.assertFails("release.yml:", "which only release.yml's release job may")

    def test_a_workflow_level_write_in_release_fails(self):
        self.edit(self.RELEASE, "permissions:\n  contents: read\n", "permissions:\n  contents: write\n")
        self.assertFails("release.yml: workflow-level permissions are", "which only release.yml's release job may")

    def test_a_second_write_scope_in_the_release_job_fails(self):
        self.edit(self.RELEASE, "      contents: write\n", "      contents: write\n      packages: write\n")
        self.assertFails("expected contents: write alone")

    def test_write_all_fails(self):
        self.edit(self.RELEASE, "      contents: write\n", "      contents: write\n    permissions: write-all\n")
        self.assertFails("grants every permission at once")

    def test_a_write_in_another_workflow_fails(self):
        self.add(".github/workflows/other.yml", "on: push\npermissions:\n  contents: read\njobs:\n  x:\n    permissions:\n      issues: 'write'\n")
        self.assertFails("other.yml:7: grants write access")

    def test_a_write_on_the_next_line_in_verify_fails(self):
        """Prevents `contents:` then `write`, which YAML reads as contents:
        write, passing the one-line check."""
        self.edit(self.VERIFY, "permissions:\n  contents: read\n", "permissions:\n  contents: read\n  pull-requests:\n    write\n")
        self.assertFails("verify.yml:", "write the scope and its value on one line", "pull-requests:")

    def test_a_block_scalar_write_in_verify_fails(self):
        """Prevents a block scalar hiding a write grant."""
        self.edit(self.VERIFY, "permissions:\n  contents: read\n", "permissions:\n  contents: read\n  pull-requests: >-\n    write\n")
        self.assertFails("verify.yml:", "write the scope and its value on one line", "pull-requests: >-")

    def test_a_write_on_the_next_line_in_the_notes_job_fails(self):
        """Prevents a split write grant outside release.yml's release job."""
        self.edit(self.RELEASE, "    timeout-minutes: 5\n    outputs:", "    timeout-minutes: 5\n    permissions:\n      contents:\n        write\n    outputs:")
        self.assertFails("release.yml:", "write the scope and its value on one line")

    def test_a_block_scalar_write_in_the_notes_job_fails(self):
        self.edit(self.RELEASE, "    timeout-minutes: 5\n    outputs:", "    timeout-minutes: 5\n    permissions:\n      contents: |\n        write\n    outputs:")
        self.assertFails("release.yml:", "write the scope and its value on one line", "contents: |")

    def test_a_flow_mapping_split_over_lines_fails(self):
        """Prevents `permissions: {` with `contents:` and `write }` on later
        lines, which YAML reads as contents: write."""
        split = "    permissions: {\n      contents:\n        write }\n"
        self.edit(self.VERIFY, "    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n" + split)
        self.assertFails("verify.yml:", "permissions is not a plain value", "permissions: {")

    def test_a_flow_mapping_split_over_lines_in_the_notes_job_fails(self):
        self.edit(self.RELEASE, "    timeout-minutes: 5\n    outputs:",
                  "    timeout-minutes: 5\n    permissions: {\n      contents:\n        write }\n    outputs:")
        self.assertFails("release.yml:", "permissions is not a plain value", "permissions: {")

    def test_a_quoted_permissions_key_with_a_split_write_fails(self):
        """Prevents a quoted key hiding a split grant from the key match."""
        self.edit(self.VERIFY, "    runs-on: ubuntu-latest\n",
                  "    runs-on: ubuntu-latest\n    \"permissions\":\n      contents:\n        write\n")
        self.assertFails("verify.yml:", "write the scope and its value on one line", "contents:")

    def test_a_quoted_permissions_key_with_a_split_write_in_the_notes_job_fails(self):
        self.edit(self.RELEASE, "    timeout-minutes: 5\n    outputs:",
                  "    timeout-minutes: 5\n    'permissions':\n      contents:\n        write\n    outputs:")
        self.assertFails("release.yml:", "write the scope and its value on one line", "contents:")

    def test_a_one_line_flow_mapping_read_passes(self):
        self.edit(self.VERIFY, "    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    permissions: { contents: read }\n")
        self.assertPasses()

    def test_a_commented_write_passes(self):
        """The checks read the lines that are not comments."""
        self.edit(self.VERIFY, "permissions:\n", "# contents: write\npermissions:\n")
        self.assertPasses()


class ReleaseHardeningTest(RepositoryCheck):
    RELEASE = ".github/workflows/release.yml"

    def test_the_version_check_removed_fails(self):
        """Prevents a version holding a newline adding a line to GITHUB_ENV."""
        self.edit(self.RELEASE, "          if [[ ! $version =~ $pattern ]]; then\n", "          if false; then\n")
        self.assertFails("release.yml: the version check before GITHUB_ENV lacks: if [[ ! $version =~ $pattern ]]")

    def test_a_beta_allowed_on_a_tag_push_fails(self):
        """Prevents a beta version being published from a tag push."""
        self.edit(self.RELEASE, r"push) pattern='^[0-9]+\.[0-9]+\.[0-9]+$'", r"push) pattern='^[0-9]+\.[0-9]+\.[0-9]+(-beta\.[0-9]+)?$'")
        self.assertFails("the version check before GITHUB_ENV lacks: push) pattern=")

    def test_the_version_check_after_github_env_fails(self):
        """Prevents a check that runs once the version is already written."""
        text = self.read(self.RELEASE)
        line = '          echo "VERSION=$version" >> "$GITHUB_ENV"\n'
        self.assertIn(line, text)
        text = text.replace(line, "").replace("          case \"$GITHUB_EVENT_NAME\" in\n", line + "          case \"$GITHUB_EVENT_NAME\" in\n", 1)
        self.add(self.RELEASE, text)
        self.assertFails("the version check before GITHUB_ENV lacks")

    def test_a_fixed_delimiter_fails(self):
        """Prevents a CHANGELOG line equal to the delimiter ending the notes
        early."""
        self.edit(
            self.RELEASE,
            '{ echo "notes<<$delimiter"; cat notes.md; echo "$delimiter"; }',
            "{ echo 'notes<<VDD_RELEASE_NOTES_EOF'; cat notes.md; echo 'VDD_RELEASE_NOTES_EOF'; }",
        )
        self.assertFails("the release notes' delimiter is not VDD_NOTES_ and random hex from /dev/urandom")

    def test_a_delimiter_without_randomness_fails(self):
        self.edit(self.RELEASE, "/dev/urandom", "/dev/null")
        self.assertFails("the release notes' delimiter is not VDD_NOTES_")


class TestMatrixTest(RepositoryCheck):
    VERIFY = ".github/workflows/verify.yml"

    def test_a_dropped_leg_fails(self):
        """Prevents a matrix that stops testing native Windows on 3.9, where
        users run the tool."""
        self.edit(self.VERIFY, "          - { os: windows-latest, python: '3.9' }\n", "")
        self.assertFails("verify.yml: the test matrix lacks windows against Python 3.9")

    def test_a_dropped_newest_python_fails(self):
        self.edit(self.VERIFY, "          - { os: macos-latest, python: '3.x' }\n", "")
        self.assertFails("verify.yml: the test matrix lacks macos against Python 3.x")

    def test_a_fixed_runner_fails(self):
        """Prevents every leg running on Ubuntu while the matrix still names
        all three systems."""
        self.edit(self.VERIFY, "    runs-on: ${{ matrix.os }}\n", "    runs-on: ubuntu-latest\n")
        self.assertFails("verify.yml: the test job runs on ['ubuntu-latest'], expected ${{ matrix.os }} alone")

    def test_a_fixed_python_fails(self):
        """Prevents every leg running on one Python while the matrix still
        names 3.9 and 3.x."""
        self.edit(self.VERIFY, "          python-version: ${{ matrix.python }}\n", "          python-version: '3.x'\n")
        self.assertFails("verify.yml: the test job sets up Python [\"'3.x'\"], expected ${{ matrix.python }} alone")


if __name__ == "__main__":
    unittest.main()
