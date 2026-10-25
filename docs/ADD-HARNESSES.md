# Adding a Harness

Running VDD on an agent it does not support yet, and the Generic instructions cause trouble? Here is how to add a Harness of your own.

A Harness is the agent a session runs in: Claude Code, Codex, Cursor, Copilot CLI, or Generic for any other. It changes how a Role types a skill, spawns a subagent and waits for a Doorbell, never the workflow. [VDD-TOOL.md](VDD-TOOL.md) explains the tool you are extending.

## 📚 Contents

- [🔎 What to find out first](#-what-to-find-out-first)
- [🐍 The Harness module](#-the-harness-module)
- [📝 The skills](#-the-skills)
- [🧪 Tests and docs](#-tests-and-docs)
- [⚠️ Common pitfalls](#-common-pitfalls)
- [🚦 Trying it](#-trying-it)

## 🔎 What to find out first

Check each from the agent's documentation and by running it:

- how a user types a skill (`/vdd:vdd-setup`, `$vdd:vdd-setup`, `/vdd-setup`)
- where it reads skills from, and which variables move those directories
- how it spawns and resumes a subagent, and whether a finished one reports its token count
- whether a background shell wakes a waiting session when it exits
- whether it sandboxes commands, and how a command asks to leave the sandbox
- how a user opens a second session for the Orchestrator

## 🐍 The Harness module

Add `skills/vdd-setup/scripts/vdd/harness/<name>.py`: one class that subclasses `Harness` from `harness/__init__.py`, ending with `HARNESS = <YourClass>()`. [`cursor.py`](../skills/vdd-setup/scripts/vdd/harness/cursor.py) is a short one to copy.

| Member | Answers |
|--------|---------|
| `name`, `label`, `display_name` | the `--harness` value and Harness file slug, the Loop file's `Harness:` line, the name a user reads |
| `borrowed_skill`, `vdd_skill` | how the user types a Matt Pocock skill and a VDD skill |
| `present_roots` | the directories it reads skills from |
| `route_*`, `no_hit_continuation` | what Setup tells the user when Matt Pocock's collection is missing, not loaded or too old |
| `orchestrator_launch` | how the user opens the Orchestrator's session |
| `wait_next` | the `Next:` step that waits for a Doorbell |
| `respawn_recommendation` | the Coder's Respawn answer it recommends |
| `reports_subagent_tokens`, `picks_up_doorbell`, `waits_through_stop_hook`, `runs_sandboxed` | what it can do |

Add the module to `every()` in `harness/__init__.py`, before Generic, imported by name. Code outside `harness/` never checks a Harness's name: a difference between agents becomes an interface member with no default, so every Harness decides it.

## 📝 The skills

- Add the new name to the `--harness` names in step 2 of [`vdd-start-loop`](../skills/vdd-start-loop/SKILL.md).
- The Planner, the Orchestrator and the Code-Reviewer each list every Harness under `## Harnesses`. Add the new one to all three. Write a `references/harness-<name>.md` and link it only if the Harness needs instructions the `SKILL.md` does not already cover; otherwise its entry reads `none: the inline text is complete`.
- A Harness file holds only what differs on that agent, in the shape of the existing ones: typed skill names, spawn and resume, the wait, a resume after a restart, a refused command. It ends with "Trust your live tools over this file when they disagree." and stays under 8 KB.

## 🧪 Tests and docs

- `tests/test_harness_contract.py` checks every module against the interface. Add the new name to its list of Harnesses and its capabilities to the expected table.
- `test_doorbell.py`, `test_loop.py`, `test_orchestrator.py` and `test_setup.py` list every Harness in places; add the new one there, and a `test_setup.py` test for its skill stores.
- `--help` lists the names, so rewrite the goldens (`python3 -B tests/run.py --update-goldens`) and check the diff only adds the new one.
- Docs: the badges, an Install and a Beta channel section and the Commands table in `README.md`, the Harnesses table in `docs/VDD-WORKFLOW.md`, and the Harness entry in `GLOSSARY.md`.

Cursor and Copilot CLI install from the Claude Code manifest. An agent that needs a manifest of its own changes the repository's [invariants](../CONTRIBUTING.md#invariants), so its pull request edits the check in `verify.yml` too.

## ⚠️ Common pitfalls

Each of these broke a loop on a supported agent:

- **Waiting that burns tokens.** Codex cannot be woken by a background shell, so polling for a Doorbell would cost a model turn each time. VDD waits there in a hook instead.
- **Subagents that report late.** On Claude Code, review passes run in the background came back late or were polled. They run in the foreground now.
- **Subagents on the wrong model.** Copilot CLI picks its own model for a subagent unless every spawn names one.
- **Subagents that carry the parent's conversation.** Codex forks the whole conversation into a subagent by default, which costs tokens and makes a review less independent.
- **Returns that never arrive.** A subagent that finishes after the parent's turn has ended may not wake it.
- **Waits that block or end early.** A blocking shell freezes the whole session on Copilot CLI, and a default timeout shorter than the wait ends it early on Claude Code.
- **Sessions that outlive you, or die too soon.** Plain `codex` keeps working in the background after you quit; Copilot CLI's subagents die when the session restarts.

## 🚦 Trying it

Before the pull request, run a whole loop on the agent in its own interactive client: the Planner in one session, the Orchestrator in a second, through to the PR-Author. An agent driven headless or through another tool cannot ask you anything, so it does not show how a Role behaves for a user. Check that each Doorbell wakes the other session without a paste.
