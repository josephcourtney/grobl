"""Prompt helpers for interactive CLI workflows (e.g., heavy-directory warnings)."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from grobl.constants import HEAVY_DIRS

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

ConfirmFn = Callable[[str], bool]


def env_assume_yes() -> bool:
    """Return True if environment variable GROBL_ASSUME_YES=1 or true-like."""
    value = os.environ.get("GROBL_ASSUME_YES", "").strip().lower()
    return value in {"1", "true", "yes"}


def _detect_heavy_dirs(paths: tuple[Path, ...]) -> set[str]:
    """Return set of heavy directories found within the given paths."""
    found: set[str] = set()
    for p in paths:
        for d in HEAVY_DIRS:
            if (p / d).exists():
                found.add(d)
    return found


def maybe_warn_on_common_heavy_dirs(
    *,
    paths: tuple[Path, ...],
    ignore_defaults: bool,
    assume_yes: bool,
    confirm: ConfirmFn,
) -> None:
    """Emit a warning and optionally abort if scanning likely-heavy directories."""
    if assume_yes:
        return
    found = _detect_heavy_dirs(paths)
    explicit_heavy = any({p.name for p in paths} & HEAVY_DIRS) or any(
        d in set(p.parts) for p in paths for d in HEAVY_DIRS
    )
    if not ignore_defaults and not explicit_heavy:
        return
    if not found:
        return
    joined = ", ".join(sorted(found))
    msg = (
        "Warning: this scan may include heavy directories: "
        f"{joined}. Continue? (y/N) [tip: keep default ignores or pass --yes or "
        "set GROBL_ASSUME_YES=1]: "
    )
    logger.warning("potential heavy scan; dirs=%s", joined)
    if not confirm(msg):
        raise SystemExit(2)
