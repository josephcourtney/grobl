"""Generic utility helpers."""

import codecs
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from os.path import commonpath
from pathlib import Path
from typing import BinaryIO

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
    "logical_absolute",
    "read_text",
    "resolve_repo_root",
]


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TextDetectionResult:
    """Outcome of probing whether a file is textual."""

    is_text: bool
    content: str | None = None
    detail: str | None = None


def logical_absolute(path: Path) -> Path:
    """Return an absolute, dot-normalized path without resolving symlinks."""
    return Path(Path(path).resolve())


def find_common_ancestor(paths: list[Path], *, resolve_symlinks: bool = True) -> Path:
    """Return the deepest common ancestor of the given paths."""
    if not paths:
        msg = ERROR_MSG_EMPTY_PATHS
        raise ValueError(msg)
    try:
        normalized = [path.resolve() if resolve_symlinks else logical_absolute(path) for path in paths]
        root = Path(commonpath([str(path) for path in normalized]))
    except ValueError as err:
        msg = ERROR_MSG_NO_COMMON_ANCESTOR
        raise PathNotFoundError(msg) from err
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
        return git_root
    try:
        common = find_common_ancestor(candidates, resolve_symlinks=False)
    except (ValueError, PathNotFoundError):
        return logical_absolute(cwd)

    if common.is_symlink() or common.is_file():
        return common.parent

    return common


def _decode_with_logging(
    decoder: codecs.IncrementalDecoder,
    chunk: bytes,
    *,
    file_path: Path,
    final: bool,
    message: str,
) -> tuple[str, str | None]:
    """Decode ``chunk`` and capture any Unicode errors for logging."""
    try:
        return decoder.decode(chunk, final=final), None
    except UnicodeDecodeError as err:
        logger.debug("%s for %s", message, file_path, exc_info=True)
        return "", f"unicode decode error: {err}"


def _detect_text_from_stream(
    fh: BinaryIO,
    *,
    file_path: Path,
    probe_size: int,
) -> TextDetectionResult:
    """Classify a binary stream as UTF-8 text without retaining its contents."""
    decoder = codecs.getincrementaldecoder("utf-8")()
    while True:
        chunk = fh.read(probe_size)
        if not chunk:
            break
        if b"\x00" in chunk:
            return TextDetectionResult(is_text=False, detail="null byte detected")
        _, detail = _decode_with_logging(
            decoder,
            chunk,
            file_path=file_path,
            final=False,
            message="utf-8 decode failed",
        )
        if detail:
            return TextDetectionResult(is_text=False, detail=detail)

    _, detail = _decode_with_logging(
        decoder,
        b"",
        file_path=file_path,
        final=True,
        message="utf-8 final decode failed",
    )
    if detail:
        return TextDetectionResult(is_text=False, detail=detail)
    return TextDetectionResult(is_text=True)


def detect_text(file_path: Path, *, probe_size: int = 4096) -> TextDetectionResult:
    """Probe file_path to determine whether it contains valid UTF-8 text."""
    try:
        with file_path.open("rb") as fh:
            return _detect_text_from_stream(fh, file_path=file_path, probe_size=probe_size)
    except OSError as err:
        logger.debug("io error while probing %s", file_path, exc_info=True)
        return TextDetectionResult(is_text=False, detail=f"read error: {err}")


def is_text(file_path: Path) -> bool:
    """Return ``True`` if :func:`detect_text` classifies ``file_path`` as text."""
    return detect_text(file_path).is_text


def read_text(file_path: Path) -> str:
    """Read text from ``file_path`` using UTF-8 with ignore errors."""
    return file_path.read_text(encoding="utf-8", errors="ignore")
