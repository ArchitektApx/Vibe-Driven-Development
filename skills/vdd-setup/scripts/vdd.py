# The VDD tool's entry. It must parse on any Python 3, so it holds nothing
# but the version check, bytecode off and the dispatch into the package.
import sys

if sys.version_info < (3, 9):
    sys.stdout.write("VDD needs Python 3.9 or newer.\n")
    sys.exit(1)

sys.dont_write_bytecode = True

from vdd.cli import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
