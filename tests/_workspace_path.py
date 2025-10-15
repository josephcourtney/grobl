"""Helpers for making workspace packages importable in pytest runs."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_workspace_packages_importable() -> None:
    """Prepend local workspace ``src`` trees to ``sys.path`` if available."""
    workspace_root = Path(__file__).resolve().parents[1]
    src_dirs = (
        workspace_root / "src",
        workspace_root / "grobl" / "src",
        workspace_root / "grobl-cli" / "src",
        workspace_root / "grobl-config" / "src",
    )

    for path in src_dirs:
        if path.exists():
            path_str = str(path)
            if path_str not in sys.path:
                sys.path.insert(0, path_str)
