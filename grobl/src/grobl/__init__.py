"""Package initialization for grobl."""

from __future__ import annotations

import contextlib
import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Final

_UNKNOWN_VERSION: Final[str] = "0.0.0"
_UNKNOWN_SOURCE: Final[str] = "unknown"
_PYPROJECT_SOURCE: Final[str] = "pyproject"


def _load_pyproject_version() -> tuple[str, str]:
    """Read the version declared in this package's ``pyproject.toml``."""
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as fh:
        data = tomllib.load(fh)

    project_table = data.get("project")
    if not isinstance(project_table, dict):  # pragma: no cover - defensive
        msg = "pyproject.toml is missing a [project] table"
        raise TypeError(msg)

    version_value = project_table.get("version")
    if not isinstance(version_value, str):
        msg = "[project].version must be a string"
        raise TypeError(msg)

    return version_value, _PYPROJECT_SOURCE


def _resolve_version() -> tuple[str, str]:
    """Resolve the package version and record the source used."""
    if __package__:
        with contextlib.suppress(PackageNotFoundError):
            return version(__package__), "distribution"

    with contextlib.suppress(Exception):
        return _load_pyproject_version()

    return _UNKNOWN_VERSION, _UNKNOWN_SOURCE


__version__, VERSION_SOURCE = _resolve_version()

__all__ = ["VERSION_SOURCE", "__version__"]
