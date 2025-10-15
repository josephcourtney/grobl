"""Generic utility helpers."""

from os.path import commonpath  # <-- needed by find_common_ancestor
from pathlib import Path

from grobl.errors import (
    ERROR_MSG_EMPTY_PATHS,
    ERROR_MSG_NO_COMMON_ANCESTOR,
    PathNotFoundError,
)

__all__ = ["find_common_ancestor", "is_text", "read_text"]


def find_common_ancestor(paths: list[Path]) -> Path:
    """Return the deepest common ancestor of the given paths."""
    if not paths:
        msg = ERROR_MSG_EMPTY_PATHS
        raise ValueError(msg)
    try:
        # Using os.path.commonpath for cross-drive safety.
        root = Path(commonpath([str(p.resolve()) for p in paths]))
    except ValueError as e:
        # Different drives or otherwise disjoint paths.
        msg = ERROR_MSG_NO_COMMON_ANCESTOR
        raise PathNotFoundError(msg) from e
    # Treat “only the filesystem root” as no real common ancestor.
    if root == Path(root.anchor):
        anchor = root.anchor or "/"
        msg = (
            f"No common ancestor found (only '{anchor}' shared). "
            "Choose paths under a common project directory."
        )
        raise PathNotFoundError(msg)
    return root


def is_text(file_path: Path) -> bool:
    """
    Determine if file is a text file.

    Heuristic: check early binary markers, then try partial UTF-8 decode.
    Avoids reading entire file.
    """
    try:
        with file_path.open("rb") as f:
            chunk = f.read(4096)
            if b"\x00" in chunk:
                return False
            try:
                chunk.decode("utf-8")
            except UnicodeDecodeError:
                return False
    except OSError:
        return False
    return True


def read_text(file_path: Path) -> str:
    """Read text from ``file_path`` using UTF-8 with ignore errors."""
    return file_path.read_text(encoding="utf-8", errors="ignore")
