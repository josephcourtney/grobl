"""CLI exports.

This package exposes `cli` and `main` from `root.py` so that
`python -m grobl` and any console entry points continue to work.
"""

from .root import cli, main

__all__ = [
    "cli",
    "main",
]
