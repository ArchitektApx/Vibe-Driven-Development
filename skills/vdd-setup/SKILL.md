---
name: vdd-setup
description: Environment check for the Vibe Driven Development workflow. Use before starting a VDD loop in a repository for the first time, or when asked to verify the VDD setup. Checks required skills and gitignore entries, and fixes what it can.
---

# VDD Setup

Verify this repository and session are ready for a Vibe Driven Development loop, fix what you can, and report the rest.

Check, in order:

1. **Borrowed skills.** The Planner depends on `grill-with-docs` and
   `improve-codebase-architecture` from Matt Pocock's collection. Both are
   user-invoked: their author set `disable-model-invocation: true`, so they
   never appear in your own skill list even when correctly installed. Do not
   check your skill list for them; that check always fails. Test two separate
   conditions.

   **Present.** Search for the files, not the directories, so that a dangling
   symlink reads as absent:

   ```
   ~/.agents/skills/*/SKILL.md
   ./.agents/skills/*/SKILL.md
   ~/.claude/plugins/cache/*/mattpocock-skills/*/skills/**/SKILL.md
   ```

   You want `grill-with-docs/SKILL.md` and
   `improve-codebase-architecture/SKILL.md`. The Claude plugin route nests
   skills by category (`engineering/`, `productivity/`), so match on the
   trailing path rather than a fixed depth. Use your file-search tool if you
   have one; otherwise:

   ```bash
   for s in grill-with-docs improve-codebase-architecture; do
     find ~/.agents/skills ./.agents/skills ~/.claude/plugins/cache \
       -path "*/$s/SKILL.md" 2>/dev/null
   done
   ```

   One predicate per invocation, deliberately. A single `find` with
   `-path A -o -path B` is correct POSIX and works in a plain shell, but
   command-rewriting proxies are common in agent environments and some of them
   reject compound predicates outright. The loop is immune and costs nothing.
   Missing search roots are normal here, so their errors go to `/dev/null` and
   a non-zero exit means nothing.

   **Resolvable.** Present only means the file exists somewhere; it does not
   mean this agent can run it. Do not try to trace symlinks backwards, and do
   not enumerate other agents' directories. Only your own resolution matters,
   because the user will be running the loop in this agent.

   Probe your own skill list for one of the collection's skills that is *not*
   user-invoked: `grilling`, `codebase-design`, `domain-modeling`, `tdd`,
   `research`, `prototype`, `diagnosing-bugs`, `code-review`,
   `resolving-merge-conflicts`. A hit means the collection is wired to this
   agent, and you are done. A miss proves nothing, because these collections
   can be installed one skill at a time. On a miss, or if you cannot inspect
   your own skill list, ask the user to type `/grill-with-docs` and tell you
   whether it resolves.

   Report the result as one of three states:

   - **Present and Resolvable.** Passed, say nothing further.
   - **Present but not Resolvable.** Installed, but not wired to this agent.
     Do not tell them to install it; they already did. Key the repair on where
     you found the file: a hit under `~/.claude/plugins/cache/` came from the
     Claude Code plugin, so the repair belongs on the plugin side (reinstall or
     re-enable `mattpocock-skills`); a hit under an `.agents/skills/` store came
     from the skills CLI, so tell them to re-run
     `npx skills@latest add mattpocock/skills` and select this agent. Do not
     offer the npx repair for a plugin-route install; it would create a second,
     parallel copy of the collection.
   - **Not Present.** Tell the user to install it: `/plugin install
     mattpocock-skills` in Claude Code's official marketplace, or
     `npx skills@latest add mattpocock/skills` in other agents, taking the
     whole collection.

   A failure in either condition blocks the Planner. Say so in those words.
   The Coder, Plan-Reviewer and Code-Reviewer have no Borrowed skill
   dependency, so a user resuming mid-workflow is not blocked by this finding.

2. **Git repository.** The workflow needs one. If this directory is not a repository, ask before running `git init`.
3. **Gitignore.** The loop's working files are scratch space and must not be committed. Ensure `.gitignore` covers `PLAN.md`, `PLAN-REVIEW.md`, `FIXES.md`, and `CODEREVIEW.md`; add missing entries.
4. **Stale working files.** If any of those files already exist from a previous loop, ask whether to delete them before starting fresh. Never delete them mid-loop.

Finish with a short status report: what passed, what you fixed, what the user still has to do.
