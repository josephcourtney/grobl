"""Custom exception classes and error messages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

ERROR_MSG_EMPTY_PATHS = "The list of paths is empty"
ERROR_MSG_NO_COMMON_ANCESTOR = "No common ancestor found"

if TYPE_CHECKING:
    from pathlib import Path

    from .directory import DirectoryTreeBuilder


class PathNotFoundError(Exception):
    """Raised when no common ancestor can be found."""


@dataclass(frozen=True, slots=True)
class ScanStateSnapshot:
    """Immutable snapshot of the scan state captured on interruption."""

    builder: DirectoryTreeBuilder
    common: Path


class ScanInterrupted(KeyboardInterrupt):
    """Raised when a scan is interrupted; carries partial state."""

    __slots__ = ("snapshot",)

    def __init__(self, builder: DirectoryTreeBuilder, common: Path) -> None:
        super().__init__("Scan interrupted")
        self.snapshot = ScanStateSnapshot(builder=builder, common=common)

    @property
    def builder(self) -> DirectoryTreeBuilder:
        return self.snapshot.builder

    @property
    def common(self) -> Path:
        return self.snapshot.common


__all__ = [
    "ERROR_MSG_EMPTY_PATHS",
    "ERROR_MSG_NO_COMMON_ANCESTOR",
    "PathNotFoundError",
    "ScanInterrupted",
    "ScanStateSnapshot",
]
