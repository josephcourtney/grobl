"""Helpers for TTY detection and output decisions."""

from __future__ import annotations

import sys
from typing import Any

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


def clipboard_allowed(cfg: dict[str, Any], *, no_clipboard_flag: bool) -> bool:
    """Return True if clipboard usage is allowed under current conditions."""
    # Disable clipboard if stdout is not a TTY or if disabled via flag/config
    return stdout_is_tty() and not (no_clipboard_flag or bool(cfg.get("no_clipboard")))
