"""The command catalog: every command's spec, the group list, parsing, the
refusals, the helps and each group's entry. A group module holds its help
text and handlers; the catalog holds what a command is."""

from .entry import Context, run  # noqa: F401
from .refusals import check_slug, missing, unknown_command  # noqa: F401
from .specs import GROUPS  # noqa: F401
