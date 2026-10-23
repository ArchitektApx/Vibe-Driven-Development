# Tests drive the tool the way a Role does

The VDD tool's tests are black-box: each runs the tool as its own process
through `vdd.py`, with the arguments a Role passes, and judges only what
comes back: the printed lines, the exit code and the files in the staged
repository. A test bound to that surface survives any refactor of the
modules behind it, so changing the code does not mean rewriting the tests.
A real process also shows what an in-process call hides: the entry's path
setup and bytecode setting, the exit code the operating system passes on,
the bytes on stdout on Windows, and a fresh interpreter for every run. The
Harness contract test is the one exception: it imports the package to
check that every Harness module implements the whole interface.

## Considered options

**Unit tests that import a module.** Rejected: a test pinned to a function
or a file breaks when that code moves, and every refactor then rewrites
tests.

**Calling `cli.main` in-process.** Rejected: it saves each run's
interpreter start, but tests sharing one interpreter can leak environment,
working directory, signal handlers and module state into each other, and
it skips the startup a user's Role runs. Running the suite in parallel and
precompiling bytecode for the test run recover most of that time within
the rule.
