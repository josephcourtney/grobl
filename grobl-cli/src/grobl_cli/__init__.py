"""Package initialization for grobl."""

from __future__ import annotations

import contextlib
import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Final

from .cli import cli, main

__all__ = [
    "__version__",
    "__version_source__",
    "cli",
    "main",
]


def _load_pyproject_version() -> tuple[str, str] | None:
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if not pyproject_path.exists():
        return None
    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    project = data.get("project")
    if isinstance(project, dict):
        version_value = project.get("version")
        if isinstance(version_value, str):
            return version_value, "pyproject"
    return None


def _fallback_version() -> tuple[str, str]:
    fallback_version: Final[str] = "0.0.0"
    return fallback_version, "fallback"


def _resolve_version() -> tuple[str, str]:
    if __package__ is not None:
        with contextlib.suppress(PackageNotFoundError):
            return version(__package__), "distribution"
    pyproject = _load_pyproject_version()
    if pyproject is not None:
        return pyproject
    return _fallback_version()


__version__, __version_source__ = _resolve_version()
