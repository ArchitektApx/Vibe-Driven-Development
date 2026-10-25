"""The command catalog: every command's spec, the group list, parsing, the
refusals, the helps, each group's entry and the line builder. A group module
holds its help text and handlers; the catalog holds what a command is."""

# pyright: reportUnusedImport=false

from .entry import Context, run  # noqa: F401
from .help import Help, Only  # noqa: F401
from .builder import Value, bare, line, quoted  # noqa: F401
from .refusals import check_slug, not_a_choice, unknown_command  # noqa: F401
from .specs import GROUPS  # noqa: F401
