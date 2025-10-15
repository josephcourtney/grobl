"""Test package for the grobl CLI project."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    candidates = [
        root / "src",
        (root / "../grobl/src").resolve(),
        (root / "../grobl-config/src").resolve(),
    ]
    for path in candidates:
        if path.is_dir():
            str_path = str(path)
            if str_path not in sys.path:
                sys.path.insert(0, str_path)


_ensure_src_on_path()
