"""Generic utility helpers."""

import codecs
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from os.path import commonpath  # <-- needed by find_common_ancestor
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
        return git_root
    try:
        common = find_common_ancestor(candidates)
    except (ValueError, PathNotFoundError):
        return cwd

    if common.is_file():
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


def _process_remainder(
    decoder: codecs.IncrementalDecoder,
    fh: BinaryIO,
    *,
    file_path: Path,
    decoded_chunk: str,
) -> tuple[str, str | None]:
    """Read the remainder of the probe and extend the decoded content."""
    remainder = fh.read()
    if b"\x00" in remainder:
        return "", "null byte detected"
    if remainder:
        decoded_remainder, detail = _decode_with_logging(
            decoder,
            remainder,
            file_path=file_path,
            final=True,
            message="utf-8 remainder decode failed",
        )
        if detail:
            return "", detail
        return decoded_chunk + decoded_remainder, None
    trimmed, detail = _decode_with_logging(
        decoder,
        b"",
        file_path=file_path,
        final=True,
        message="utf-8 probe flush failed",
    )
    if detail:
        return "", detail
    return decoded_chunk + trimmed, None


def detect_text(file_path: Path, *, probe_size: int = 4096) -> TextDetectionResult:
    """Probe ``file_path`` to determine if it is text and prefetch its contents."""
    try:
        with file_path.open("rb") as fh:
            chunk = fh.read(probe_size)
            if b"\x00" in chunk:
                return TextDetectionResult(is_text=False, detail="null byte detected")
            decoder = codecs.getincrementaldecoder("utf-8")()
            decoded_chunk, detail = _decode_with_logging(
                decoder,
                chunk,
                file_path=file_path,
                final=False,
                message="utf-8 probe chunk failed",
            )
            if detail:
                return TextDetectionResult(is_text=False, detail=detail)
            content, detail = _process_remainder(
                decoder,
                fh,
                file_path=file_path,
                decoded_chunk=decoded_chunk,
            )
            if detail:
                return TextDetectionResult(is_text=False, detail=detail)
            return TextDetectionResult(is_text=True, content=content)
    except OSError as err:
        logger.debug("io error while probing %s", file_path, exc_info=True)
        return TextDetectionResult(is_text=False, detail=f"read error: {err}")


def is_text(file_path: Path) -> bool:
    """Return ``True`` if :func:`detect_text` classifies ``file_path`` as text."""
    return detect_text(file_path).is_text


def read_text(file_path: Path) -> str:
    """Read text from ``file_path`` using UTF-8 with ignore errors."""
    return file_path.read_text(encoding="utf-8", errors="ignore")
