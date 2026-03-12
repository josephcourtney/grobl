"""Legacy reference scanning helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grobl.utils import is_text

from .config_defaults import TOML_CONFIG
from .config_loading import LEGACY_TOML_CONFIG

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def scan_legacy_references(base: Path) -> Iterator[tuple[Path, int, str]]:
    """Yield ``(path, line_number, text)`` for files mentioning the legacy config name."""
    for path in base.rglob("*"):
        if path.is_dir():
            continue
        if path.name in {TOML_CONFIG, LEGACY_TOML_CONFIG}:
            continue
        try:
            if not is_text(path):
                continue
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if LEGACY_TOML_CONFIG in line:
                        yield path, line_number, line.rstrip()
        except OSError:
            continue
