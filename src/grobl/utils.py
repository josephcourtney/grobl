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
    return file_path.read_text(encoding="utf-8", errors="ignore")
