"""Generic utility helpers."""

from pathlib import Path

from .errors import (
    ERROR_MSG_EMPTY_PATHS,
    ERROR_MSG_NO_COMMON_ANCESTOR,
    PathNotFoundError,
)


def find_common_ancestor(paths: list[Path]) -> Path:
    """Return the deepest common ancestor of the given paths."""
    if not paths:
        raise ValueError(ERROR_MSG_EMPTY_PATHS)
    common = paths[0].resolve()
    for p in map(Path.resolve, paths[1:]):
        while not p.is_relative_to(common):
            common = common.parent
            if common == Path("/"):
                raise PathNotFoundError(ERROR_MSG_NO_COMMON_ANCESTOR)
    return common


def is_text(file_path: Path) -> bool:
    """Return ``True`` if ``file_path`` looks like a text file."""

    # Preliminary binary check: if there's a NULL byte, treat as binary
    try:
        with file_path.open("rb") as f:
            if b"\x00" in f.read(1024):
                return False
    except OSError:
        return False

    # Fallback to UTF-8 decode test
    try:
        file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    return True


def read_text(file_path: Path) -> str:
    """Read text from ``file_path`` using UTF-8 with ignore errors."""

    return file_path.read_text(encoding="utf-8", errors="ignore")


def find_project_root(start: Path) -> Path | None:
    """Return the project root starting from ``start`` if detected.

    The root is determined by looking for ``pyproject.toml`` or ``.git``
    directories in ``start`` and its parents.
    """

    start = start.resolve()
    for path in [start, *start.parents]:
        if (path / "pyproject.toml").exists() or (path / ".git").exists():
            return path
    return None
