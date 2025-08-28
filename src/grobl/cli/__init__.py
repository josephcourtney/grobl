"""CLI exports.

This package exposes `cli` and `main` from `root.py` so that
`python -m grobl` and any console entry points continue to work.
"""

from .common import (
    _maybe_offer_legacy_migration,
    _maybe_warn_on_common_heavy_dirs,
    print_interrupt_diagnostics,
)
from .root import cli, main

__all__ = [
    "_maybe_offer_legacy_migration",
    "_maybe_warn_on_common_heavy_dirs",
    "cli",
    "main",
    "print_interrupt_diagnostics",
]
