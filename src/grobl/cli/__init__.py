"""CLI exports.

This package exposes `cli` and `main` from `root.py` so that
`python -m grobl` and any console entry points continue to work.
"""

from .common import (
    print_interrupt_diagnostics,
)
from .root import cli, main

__all__ = [
    "cli",
    "main",
    "print_interrupt_diagnostics",
]
