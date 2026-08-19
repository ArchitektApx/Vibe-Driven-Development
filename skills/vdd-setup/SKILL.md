---
name: vdd-setup
description: Environment check for the Vibe Driven Development workflow.
---

# VDD Setup

Verify this repository and session are ready for a Vibe Driven Development loop, fix what you can, and report the rest.

This check is machine-level and repository-level. It knows nothing about a
particular feature; `/vdd:vdd-start-loop` handles per-loop state and writes
`LOOP.md`.

Check, in order:

1. **Borrowed skills.** The Roles depend on seven skills from Matt Pocock's
   collection:

   | Borrowed skill | Invoked by | Needed by |
   |----------------|-----------|-----------|
   | `setup-matt-pocock-skills` | the user | check 2 below |
   | `grill-with-docs` | the user | Planner |
   | `improve-codebase-architecture` | the user | Planner |
   | `to-spec` | the user | Planner |
   | `to-tickets` | the user | Planner |
   | `code-review` | an agent | Code-Reviewer |
   | `writing-for-agents` | an agent | Planner, Plan-Reviewer, Code-Reviewer |

   The five user-invoked ones have `disable-model-invocation: true` in their
   frontmatter, so they never appear in your own skill list even when correctly
   installed. Your skill list is silent about those five by design, so answer
   for them on the two separate conditions below.

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
   `to-tickets/SKILL.md`, `code-review/SKILL.md` and
   `writing-for-agents/SKILL.md`. The Claude plugin route
   nests skills by category (`engineering/`, `productivity/`), so match on the
   trailing path rather than a fixed depth. The two `.claude/skills` roots are
   where the skills CLI writes when it installs for Claude Code: project scope
   lands in `./.claude/skills/<name>/`, global scope stores the files in
   `~/.agents/skills/<name>/` and symlinks `~/.claude/skills/<name>` at them.

   Use your file-search tool if you have one; otherwise:

   ```bash
   for s in setup-matt-pocock-skills grill-with-docs improve-codebase-architecture to-spec to-tickets code-review writing-for-agents; do
     find ~/.agents/skills ./.agents/skills ~/.claude/skills ./.claude/skills ~/.claude/plugins/cache \
       -name SKILL.md 2>/dev/null | grep "/$s/SKILL.md$"
   done
   ```

   Filter with `grep`, not with `-path`. Agent environments commonly replace
   `find` with a shell function around a bundled `bfs`, or route it through a
   command-rewriting proxy, and several of those answer `-path` with
   `unknown flag '-path', ignored` and then print everything under the roots,
   or nothing at all. `-name` survives both. One skill per invocation,
   also deliberately: a single `find` with compound predicates is correct POSIX
   and works in a plain shell, but the same proxies reject compound predicates
   outright. The loop is immune and costs nothing.

   Missing search roots are normal here, so their errors go to `/dev/null` and
   a non-zero exit means nothing.

   A dangling symlink still reads as absent with this loop, for the same reason
   it did with `-path`: without `-L`, `find` does not descend into a symlinked
   directory whose target is gone, so no `SKILL.md` is ever listed under it.

   **Resolvable.** Present only means the file exists somewhere; it does not
   mean this agent can run it. Answer this one from your own skill list alone,
   leaving symlink targets and other agents' directories where they are. Only
   your own resolution matters, because the user will be running the loop in
   this agent.

   Probe your own skill list for one of the collection's skills that is *not*
   user-invoked: `writing-for-agents`, `grilling`, `codebase-design`,
   `domain-modeling`, `tdd`, `research`, `prototype`, `diagnosing-bugs`,
   `resolving-merge-conflicts`. A hit means the collection is wired to this
   agent, which answers Resolvable for the five user-invoked skills and for
   `code-review`. A miss proves nothing, because these collections
   can be installed one skill at a time. On a miss across the whole list, or if
   you cannot inspect your own skill list, ask the user to type
   `/writing-for-agents` and tell you whether it resolves. That one question
   answers the collection and the seventh skill together, and a miss on it
   followed by a `/grill-with-docs` hit is the collection that predates the
   skill.

   `writing-for-agents` leads that list because it is Borrowed in its own
   right, and because Claude Code bundles nothing of that name, so a hit needs
   no reading. That same look is its own Resolvable test: it is agent-invocable,
   so a wired collection puts it in your skill list. A miss on it followed by a
   hit further down the list means the collection is Resolvable and
   `writing-for-agents` is not.

   `code-review` is agent-invocable too, so it looks like a second probe. It is
   not, because Claude Code ships an unrelated bundled `code-review` skill of
   the same bare name. Read the hit before you believe it:

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
     The install already happened, so the repair is wiring. Key it on where you
     found the file: a hit under `~/.claude/plugins/cache/` came from the Claude
     Code plugin, so the repair belongs on the plugin side (reinstall or
     re-enable `mattpocock-skills`); a hit under an `.agents/skills/` or
     `.claude/skills/` store came from the skills CLI, so tell them to re-run
     `npx skills@latest add mattpocock/skills` and select this agent. Keep each
     repair on the store its files came from: the npx route offered for a
     plugin-route install creates a second, parallel copy of the collection.
   - **Not Present.** Tell the user to install it: `/plugin install
     mattpocock-skills` in Claude Code's official marketplace, or
     `npx skills@latest add mattpocock/skills` in other agents, taking the
     whole collection.

   One shape of Not Present is an old collection rather than a missing one.
   `writing-for-agents` shipped after the six the Roles borrowed before it, so a
   user who installed the collection earlier has those six Present and this one
   absent. When that is the shape in front of you, say the installed collection
   predates the skill and give the update route for the store the six were found
   in. Installing a collection they already have is the wrong advice:

   - Found under `~/.claude/plugins/cache/`: `claude plugin marketplace update
     <marketplace>` then `claude plugin update mattpocock-skills`.
     `<marketplace>` is the first directory under `~/.claude/plugins/cache/` on
     the path the six were found at, which is the marketplace name, not the
     plugin name below it. In a Claude Code session the marketplace half is
     `/plugin marketplace update <marketplace>`.
   - Found under an `.agents/skills/` or `.claude/skills/` store:
     `npx skills update`.

   Name what a failure costs each Role, in these words. A missing or
   unresolvable `grill-with-docs`, `improve-codebase-architecture`, `to-spec` or
   `to-tickets` blocks the Planner. A missing or unresolvable `code-review`
   blocks the Code-Reviewer. A missing or unresolvable `writing-for-agents`
   degrades the Planner, the Plan-Reviewer and the Code-Reviewer instead of
   blocking them: each drops its writing pass, records that in the file it
   writes, and carries on. The Coder is the only Role that borrows nothing,
   and a user resuming mid-workflow is stopped by the `code-review` finding
   alone.

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
4. **Gitignore.** The loop's working files are scratch space, and `.gitignore`
   is what keeps them out of the user's history. Ensure `.gitignore` covers
   `LOOP.md` and `.scratch/`; add either one that is missing. `.scratch/` is
   the Borrowed tracker directory, and VDD is what invokes it here, so it is
   scratch space like the rest. It is also where the three review files are
   written, so its entry covers them.

   Then remove the four entries VDD no longer maintains: `PLAN.md`,
   `PLAN-REVIEW.md`, `FIXES.md` and `CODEREVIEW.md`. A user upgrading from an
   earlier release has them, and no file can appear at any of those paths in
   this release. Name in your report which of the four you removed, because
   this edits a file the user tracks.

   Remove a line only when the whole line, trimmed of surrounding whitespace,
   equals one of those four names. A line that merely contains one of them,
   `docs/PLAN.md` or `!PLAN.md` or `PLAN.md.bak`, is the user's own and stays:
   `PLAN.md` is a name anyone may ignore for reasons of their own.
5. **Stale working files.** If `LOOP.md` already exists from a previous loop,
   ask whether to delete it before starting fresh. Delete only between loops.
   It is the one working file you can find from here: the rest live under
   `.scratch/<slug>/`, and `/vdd:vdd-start-loop` asks about that directory once
   the user has named the slug, because from here you cannot know which feature
   is stale.

Finish with a short status report: what passed, what you fixed, what the user still has to do.
