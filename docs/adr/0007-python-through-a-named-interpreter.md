# Python, run through a named interpreter

The plugin ships one program, the VDD tool: standard-library Python 3.9 or
newer, run only through a named interpreter, `python3` on macOS and Linux and
`py -3` on native Windows, never by its own path. A Role without Python 3.9
says so and stops. 3.9 is what Apple's Command Line Tools bring with git, and
`py -3` is the one name every Windows install route provides. A named
interpreter keeps the command a hook or an approval prompt shows short and
readable. A Role never writes, edits or replaces the tool: shipped code was
reviewed and released with the plugin, code an agent writes was not.

## Considered options

**`.sh` and `.ps1` pairs.** Rejected: every step was written twice, and the
two drifted.

**Python with the shell pairs as a fallback.** Rejected: it keeps every cost
of the pairs and adds a second path to test.

**A compiled Go binary.** Rejected: committed builds per platform in a
history every Harness clones, and unsigned Windows `.exe` files meeting
Defender; its one gain, no Python install, matters only on native Windows.

**Node, Deno, Bun or uv.** Rejected: no Harness provides those runtimes, and
uv buys nothing for a standard-library program.
