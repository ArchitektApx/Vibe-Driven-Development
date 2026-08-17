---
name: vdd-setup
description: Environment check for the Vibe Driven Development workflow. Use before starting a VDD loop in a repository for the first time, or when asked to verify the VDD setup. Checks the borrowed skills, the Matt Pocock issue-tracker setup, and that LOOP.md, .scratch/ and the review files are gitignored, and fixes what it can.
---

# VDD Setup

Verify this repository and session are ready for a Vibe Driven Development loop, fix what you can, and report the rest.

This check is machine-level and repository-level. It knows nothing about a
particular feature; `/vdd:vdd-start-loop` handles per-loop state and writes
`LOOP.md`.

Check, in order:

1. **Borrowed skills.** The Roles depend on six skills from Matt Pocock's
   collection:

   | Borrowed skill | Invoked by | Needed by |
   |----------------|-----------|-----------|
   | `setup-matt-pocock-skills` | the user | check 2 below |
   | `grill-with-docs` | the user | Planner |
   | `improve-codebase-architecture` | the user | Planner |
   | `to-spec` | the user | Planner |
   | `to-tickets` | the user | Planner |
   | `code-review` | an agent | Code-Reviewer |

   The five user-invoked ones have `disable-model-invocation: true` in their
   frontmatter, so they never appear in your own skill list even when correctly
   installed. Do not check your skill list for them; that check always fails.
   Test two separate conditions instead.

   **Present.** Search for the files, not the directories, so that a dangling
   symlink reads as absent:

   ```
   ~/.agents/skills/*/SKILL.md
   ./.agents/skills/*/SKILL.md
   ~/.claude/skills/*/SKILL.md
   ./.claude/skills/*/SKILL.md
   ~/.claude/plugins/cache/*/mattpocock-skills/*/skills/**/SKILL.md
   ```

   You want `setup-matt-pocock-skills/SKILL.md`, `grill-with-docs/SKILL.md`,
   `improve-codebase-architecture/SKILL.md`, `to-spec/SKILL.md`,
   `to-tickets/SKILL.md` and `code-review/SKILL.md`. The Claude plugin route
   nests skills by category (`engineering/`, `productivity/`), so match on the
   trailing path rather than a fixed depth. The two `.claude/skills` roots are
   where the skills CLI writes when it installs for Claude Code: project scope
   lands in `./.claude/skills/<name>/`, global scope stores the files in
   `~/.agents/skills/<name>/` and symlinks `~/.claude/skills/<name>` at them.

   Use your file-search tool if you have one; otherwise:

   ```bash
   for s in setup-matt-pocock-skills grill-with-docs improve-codebase-architecture to-spec to-tickets code-review; do
     find ~/.agents/skills ./.agents/skills ~/.claude/skills ./.claude/skills ~/.claude/plugins/cache \
       -name SKILL.md 2>/dev/null | grep "/$s/SKILL.md$"
   done
   ```

   Filter with `grep`, not with `-path`. Agent environments commonly replace
   `find` with a shell function around a bundled `bfs`, or route it through a
   command-rewriting proxy, and several of those answer `-path` with
   `unknown flag '-path', ignored` and then print every `SKILL.md` on the
   machine, or nothing at all. `-name` survives both. One skill per invocation,
   also deliberately: a single `find` with compound predicates is correct POSIX
   and works in a plain shell, but the same proxies reject compound predicates
   outright. The loop is immune and costs nothing.

   Missing search roots are normal here, so their errors go to `/dev/null` and
   a non-zero exit means nothing.

   A dangling symlink still reads as absent with this loop, for the same reason
   it did with `-path`: without `-L`, `find` does not descend into a symlinked
   directory whose target is gone, so no `SKILL.md` is ever listed under it.

   **Resolvable.** Present only means the file exists somewhere; it does not
   mean this agent can run it. Do not try to trace symlinks backwards, and do
   not enumerate other agents' directories. Only your own resolution matters,
   because the user will be running the loop in this agent.

   Probe your own skill list for one of the collection's skills that is *not*
   user-invoked: `grilling`, `codebase-design`, `domain-modeling`, `tdd`,
   `research`, `prototype`, `diagnosing-bugs`, `resolving-merge-conflicts`. A
   hit means the collection is wired to this agent, and you are done. A miss
   proves nothing, because these collections can be installed one skill at a
   time. On a miss, or if you cannot inspect your own skill list, ask the user
   to type `/grill-with-docs` and tell you whether it resolves.

   `code-review` is the collection's sixth Borrowed skill and is itself
   agent-invocable, so it looks like the obvious probe. It is not, because
   Claude Code ships an unrelated bundled `code-review` skill of the same bare
   name. Read the hit before you believe it:

   - A hit on `mattpocock-skills:code-review` is the Claude Code plugin
     install. It proves the collection is Resolvable.
   - A bare `code-review` whose description names the two axes "Standards" and
     "Spec" is a skills-CLI install, where the collection is the only source of
     that name, and in Claude Code a project or personal skill of that name
     replaces the bundled one. It proves the collection is Resolvable too.
   - A bare `code-review` with any other description is Claude Code's bundled
     `code-review` skill. It proves nothing. Ignore it and fall through to the
     sibling names above.

   Report the result as one of three states:

   - **Present and Resolvable.** Passed, say nothing further.
   - **Present but not Resolvable.** Installed, but not wired to this agent.
     Do not tell them to install it; they already did. Key the repair on where
     you found the file: a hit under `~/.claude/plugins/cache/` came from the
     Claude Code plugin, so the repair belongs on the plugin side (reinstall or
     re-enable `mattpocock-skills`); a hit under an `.agents/skills/` or
     `.claude/skills/` store came from the skills CLI, so tell them to re-run
     `npx skills@latest add mattpocock/skills` and select this agent. Do not
     offer the npx repair for a plugin-route install; it would create a second,
     parallel copy of the collection.
   - **Not Present.** Tell the user to install it: `/plugin install
     mattpocock-skills` in Claude Code's official marketplace, or
     `npx skills@latest add mattpocock/skills` in other agents, taking the
     whole collection.

   Name which Roles a failure blocks, in these words. A missing or unresolvable
   `grill-with-docs`, `improve-codebase-architecture`, `to-spec` or
   `to-tickets` blocks the Planner. A missing or unresolvable `code-review`
   blocks the Code-Reviewer. The Coder and the Plan-Reviewer have no Borrowed
   skill dependency, so a user resuming mid-workflow is not blocked by this
   finding.

2. **Tracker configured.** `to-spec`, `to-tickets` and `code-review` all read
   `docs/agents/issue-tracker.md` to learn where specs and tickets live, and
   point at `/setup-matt-pocock-skills` when it is missing. Check that the file
   exists at the repository root.

   If it is missing, tell the user to type `/setup-matt-pocock-skills` and to
   recommend Local markdown when it asks which tracker to use. You cannot run
   it yourself: it is user-invoked, like the rest of the collection. Say that
   this blocks the Planner (`to-spec`, `to-tickets`) and the Code-Reviewer
   (`code-review`).

   If it exists but describes something other than the local-markdown tracker,
   note it and continue. VDD works with any tracker the collection supports,
   but the Roles are written for local markdown under `.scratch/<slug>/`.

3. **Git repository.** The workflow needs one. If this directory is not a repository, ask before running `git init`.
4. **Gitignore.** The loop's working files are scratch space and must not be committed. Ensure `.gitignore` covers `LOOP.md`, `.scratch/`, `PLAN.md`, `PLAN-REVIEW.md`, `FIXES.md`, and `CODEREVIEW.md`; add missing entries. `.scratch/` is the Borrowed tracker directory, and VDD is what invokes it here, so it is scratch space like the rest. `PLAN.md` is not written by any current Role and stays on the list for one release, for users who still have one from a 0.2.0 loop.
5. **Stale working files.** If `LOOP.md`, or any of the other files from the previous check, already exists from a previous loop, ask whether to delete it before starting fresh. Never delete anything mid-loop. Do not check `.scratch/` here: you cannot know which feature is stale, and `/vdd:vdd-start-loop` asks about `.scratch/<slug>/` once the user has named the slug.

Finish with a short status report: what passed, what you fixed, what the user still has to do.
