# The VDD tool

The VDD tool does every step in VDD that has one right outcome, so models cannot get those steps wrong and tests can pin them. The skills keep what needs judgment: the conversation with you, reviewing, deciding, consent. Prose is followed a little differently by every model and every run; code runs the same each time.

## 📚 Contents

- [🧰 What it does](#-what-it-does)
- [📦 Where it lives](#-where-it-lives)
- [🔒 Its limits](#-its-limits)
- [🗂 How the code is laid out](#-how-the-code-is-laid-out)
- [🧪 Tests](#-tests)
- [🤝 Working on it](#-working-on-it)

## 🧰 What it does

A Role runs one command per step and does what the command prints:

```
python3 <Shared directory>/vdd.py <group> <command> [options]
```

On native Windows the interpreter is `py -3`. Each command explains itself with `--help`, so a skill names the command and leaves the details to the tool. Every run ends with a `Next:` line naming the exact step the Role takes after it, and a `Tell the user verbatim:` line gives the Role the exact words to pass on to you. The Role works from the tool's latest output, not from its memory of a long conversation, so it does not lose track. A command that writes first prints what it would do, and does it only with `--write`.

| Group | Does |
|-------|------|
| `setup` | checks the machine and the repository for a loop, and copies the tool into the Shared directory |
| `loop` | starts a loop, and shows, changes, closes or reopens its Loop file |
| `doorbell` | rings, waits for and takes Doorbells between the Planner and the Orchestrator |
| `orchestrator` | places the Workflow and acts on each hosted Role's return |
| `review` | writes and checks the Plan-Reviewer's and the Code-Reviewer's rounds, and takes your findings with `review add` |
| `coder` | starts the Coder's round on the feature branch, checks `FIXES.md` and records the round's end |
| `pr` | checks the PR template, the history and the preflight, then pushes, opens the PR and closes the loop |
| `brainstorm` | keeps the Brainstormer's idea store: the overview, one idea, a search, and every write |
| `wayfinder` | starts a Wayfinder effort: its map, Matt Pocock's `wayfinder` and the briefing |
| `codex-stop` | the Codex `Stop` hook; Codex runs it at a turn's end, a Role never does |

## 📦 Where it lives

The tool ships inside the Setup skill, in [`skills/vdd-setup/scripts/`](../skills/vdd-setup/scripts/): the entry script `vdd.py` and the package `vdd/`. A plugin's install path changes with every version and differs per Harness, so Setup copies both into the Shared directory, and every Role runs that copy:

- macOS and Linux: `${XDG_DATA_HOME:-$HOME/.local/share}/vdd/`
- native Windows: `%LOCALAPPDATA%\vdd\`

Setup compares the shipped copy with the Shared one at every loop start and replaces the Shared copy when they differ, after showing what it writes. One Shared directory serves every Harness on the machine. Uninstalling the plugin leaves it in place; delete the directory to remove it. [ADR 0008](adr/0008-where-the-tool-and-hook-live.md) has the reasons.

## 🔒 Its limits

- It needs Python 3.9 or newer and nothing beyond the standard library.
- It reaches the network only through `git` and `gh`, for the pull request. It starts no shell and evaluates no text.
- It writes only to your project (its `.gitignore`, `.scratch/`, and in the repository the feature branch, the fold's commits, the push and the PR), to the Shared directory and, on Codex, to `~/.codex/hooks.json`, where it removes an older VDD's entry. It writes no bytecode.
- It runs only when a Role calls it through `python3` or `py -3`, or when Codex runs the one hook you trusted.

CI checks these on every pull request. [ADR 0011](adr/0011-what-runs-on-a-users-machine.md) has the full rule.

## 🗂 How the code is laid out

```
skills/vdd-setup/scripts/
├── vdd.py            the entry: version check, bytecode off, dispatch
└── vdd/
    ├── cli.py        hands a command line to its group
    ├── catalog/      every command's spec, parsing, --help and refusals
    ├── runner/       runs a write command's plan: the dry run, or --write
    ├── harness/      one module per Harness
    ├── setup/  loop/  orchestrator/  coder/  review/  pr/  brainstorm/
    │                 the groups with modules of their own
    ├── doorbell.py  wayfinder.py  codex_hook.py
    │                 the single-module groups
    ├── loopfile/  loopstate/  workfile/  doorbells/
    │                 concerns shared by several groups
    └── *.py          shared helpers: git, output, paths, text files, skill stores
```

A few rules keep it in shape:

- The catalog holds what a command is. A group module holds the rest: its help, its handlers and the lines it prints.
- No group module imports another group's module.
- A write command is a precondition and a plan of effects, each effect with the line its dry run prints and the line `--write` prints.
- A helper returns facts, and the group that calls it words what the Role reads.
- Code with one user stays in that group. It moves to the top of the package when a second group needs it.
- One concern per module, about 500 lines at most.

[`CONTRIBUTING.md`](../CONTRIBUTING.md) holds the full list.

## 🧪 Tests

The tests drive the tool from outside, the way a Role does: each runs `vdd.py` as its own process with a Role's arguments, then checks the printed lines, the exit code and the files in a staged repository. A refactor behind that surface leaves the tests alone ([ADR 0013](adr/0013-tests-drive-the-tool-as-a-role-does.md)). The one exception, `tests/test_harness_contract.py`, imports the package to check that every Harness module implements the whole interface.

```sh
python3 -B tests/run.py                     # parallel, what CI runs
python3 -B -m unittest discover -s tests    # one class after another
python3 -B tests/run.py --update-goldens    # after a deliberate change to printed output
```

On native Windows, use `py -3` for `python3`. Review the diff of `tests/golden/` after updating it. CI runs the suite on Ubuntu, Windows and macOS against Python 3.9 and the newest 3.x.

## 🤝 Working on it

Pull requests target `beta`. [`CONTRIBUTING.md`](../CONTRIBUTING.md) holds the house rules and the invariants CI enforces.

### Adding a command

1. Add its spec to `catalog/specs.py`: its group and its options.
2. Write its help, handler and printed lines in the group's module. A write command builds a plan of effects and lets `runner/` print or apply it.
3. Add tests that run it through `vdd.py`, and goldens if its output is fixed.
4. Teach the Role in its `SKILL.md` only what `--help` does not already say.

### Adding a Harness

A new coding agent gets a module in `harness/`, instructions in three skills, tests and docs. [ADD-HARNESSES.md](ADD-HARNESSES.md) walks through each part.
