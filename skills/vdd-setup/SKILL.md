---
name: vdd-setup
description: Environment check for the Vibe Driven Development workflow. Use before starting a VDD loop in a repository for the first time, or when asked to verify the VDD setup. Checks required skills and gitignore entries, and fixes what it can.
---

# VDD Setup

Verify this repository and session are ready for a Vibe Driven Development loop, fix what you can, and report the rest.

Check, in order:

1. **Required skills.** The planner depends on `grill-with-docs` and `improve-codebase-architecture` from Matt Pocock's skills collection. Check whether they appear in your available skills. If they are missing, tell the user how to install them (`/plugin install mattpocock-skills` in Claude Code's official marketplace, `npx skills@latest add mattpocock/skills` in other agents) and restart the check. Do not continue a VDD loop without them.
2. **Git repository.** The workflow needs one. If this directory is not a repository, ask before running `git init`.
3. **Gitignore.** The loop's working files are scratch space and must not be committed. Ensure `.gitignore` covers `PLAN.md`, `PLAN-REVIEW.md`, `FIXES.md`, and `CODEREVIEW.md`; add missing entries.
4. **Stale working files.** If any of those files already exist from a previous loop, ask whether to delete them before starting fresh. Never delete them mid-loop.

Finish with a short status report: what passed, what you fixed, what the user still has to do.
