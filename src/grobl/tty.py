"""Helpers for TTY detection and output decisions."""

from __future__ import annotations

import sys

from .constants import TableStyle


def stdout_is_tty() -> bool:
    """Return True if stdout is a TTY. Isolated for testability."""
    try:
        return sys.stdout.isatty()
    except AttributeError:
        # stdout replaced with an object lacking isatty(); treat as non-TTY
        return False


def resolve_table_style(requested: TableStyle) -> TableStyle:
    """Resolve 'auto' to a concrete style based on TTY, otherwise return unchanged."""
    if requested is TableStyle.AUTO:
        return TableStyle.FULL if stdout_is_tty() else TableStyle.COMPACT
    return requested
