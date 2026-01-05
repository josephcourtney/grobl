"""Generic utility helpers."""

from collections.abc import Sequence
from dataclasses import dataclass
from os.path import commonpath  # <-- needed by find_common_ancestor
from pathlib import Path

from grobl.errors import (
    ERROR_MSG_EMPTY_PATHS,
    ERROR_MSG_NO_COMMON_ANCESTOR,
    PathNotFoundError,
)

__all__ = [
    "TextDetectionResult",
    "detect_text",
    "find_common_ancestor",
    "is_text",
    "read_text",
    "resolve_repo_root",
]


@dataclass(frozen=True, slots=True)
class TextDetectionResult:
    """Outcome of probing whether a file is textual."""

    is_text: bool
    content: str | None = None


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
    return root


def _git_root_for_cwd(cwd: Path) -> Path | None:
    """Return the git worktree root for ``cwd`` if available."""
    current = cwd.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def resolve_repo_root(*, cwd: Path, paths: Sequence[Path]) -> Path:
    """Return the repo root for the current run using git & path fallbacks."""
    candidates = list(paths) or [cwd]
    git_root = _git_root_for_cwd(cwd)
    if git_root is not None:
        resolved = [p.resolve(strict=False) for p in candidates]
        if all(p.is_relative_to(git_root) for p in resolved):
            return git_root

    try:
        common = find_common_ancestor(candidates)
    except (ValueError, PathNotFoundError):
        return cwd

    if common.is_file():
        return common.parent

    return common


def detect_text(file_path: Path, *, probe_size: int = 4096) -> TextDetectionResult:
    """Probe ``file_path`` to determine if it is text and prefetch its contents."""
    try:
        with file_path.open("rb") as fh:
            chunk = fh.read(probe_size)
            if b"\x00" in chunk:
                return TextDetectionResult(is_text=False)
            try:
                decoded_chunk = chunk.decode("utf-8")
            except UnicodeDecodeError:
                return TextDetectionResult(is_text=False)
            remainder = fh.read()
            if b"\x00" in remainder:
                return TextDetectionResult(is_text=False)
            if remainder:
                decoded_remainder = remainder.decode("utf-8", errors="ignore")
                content = decoded_chunk + decoded_remainder
            else:
                content = decoded_chunk
    except OSError:
        return TextDetectionResult(is_text=False)
    return TextDetectionResult(is_text=True, content=content)


def is_text(file_path: Path) -> bool:
    """Return ``True`` if :func:`detect_text` classifies ``file_path`` as text."""
    return detect_text(file_path).is_text


def read_text(file_path: Path) -> str:
    """Read text from ``file_path`` using UTF-8 with ignore errors."""
    return file_path.read_text(encoding="utf-8", errors="ignore")
