"""Resource limits for prompt-content collection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

RESOURCE_LIMIT_SOURCE = "resource-limit"
RESOURCE_LIMIT_PATTERN = "<resource-limit>"


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    """Maximum resources allowed for captured file contents.

    A value of None means unlimited. Limits apply only to content that would
    otherwise be fully included; omitted and tree-only files consume no budget.
    """

    max_file_bytes: int | None = None
    max_total_bytes: int | None = None
    max_tokens: int | None = None

    def to_dict(self) -> dict[str, int | None]:
        return {
            "max_file_bytes": self.max_file_bytes,
            "max_total_bytes": self.max_total_bytes,
            "max_tokens": self.max_tokens,
        }


UNLIMITED_RESOURCE_LIMITS = ResourceLimits()


def resource_limit_reason(
    *,
    path: Path,
    limit: str,
    actual: int,
    maximum: int,
) -> dict[str, Any]:
    """Return a stable provenance record for content omitted by a budget."""
    return {
        "pattern": RESOURCE_LIMIT_PATTERN,
        "state": "full",
        "negated": False,
        "source": RESOURCE_LIMIT_SOURCE,
        "base_dir": str(path.parent),
        "config_path": None,
        "detail": f"{limit} exceeded: {actual} > {maximum}",
    }


@dataclass(slots=True)
class ResourceBudget:
    """Mutable aggregate budget used during deterministic traversal."""

    limits: ResourceLimits
    total_bytes: int = 0
    total_tokens: int = 0

    def preflight(self, path: Path, *, file_bytes: int) -> dict[str, Any] | None:
        """Reject a file before reading when byte limits already make it ineligible."""
        if (
            self.limits.max_file_bytes is not None
            and file_bytes > self.limits.max_file_bytes
        ):
            return resource_limit_reason(
                path=path,
                limit="max_file_bytes",
                actual=file_bytes,
                maximum=self.limits.max_file_bytes,
            )
        if (
            self.limits.max_total_bytes is not None
            and self.total_bytes + file_bytes > self.limits.max_total_bytes
        ):
            return resource_limit_reason(
                path=path,
                limit="max_total_bytes",
                actual=self.total_bytes + file_bytes,
                maximum=self.limits.max_total_bytes,
            )
        return None

    def accept(
        self,
        path: Path,
        *,
        file_bytes: int,
        tokens: int,
    ) -> dict[str, Any] | None:
        """Consume budget for a file, or return the reason it cannot be included."""
        byte_reason = self.preflight(path, file_bytes=file_bytes)
        if byte_reason is not None:
            return byte_reason
        if (
            self.limits.max_tokens is not None
            and self.total_tokens + tokens > self.limits.max_tokens
        ):
            return resource_limit_reason(
                path=path,
                limit="max_tokens",
                actual=self.total_tokens + tokens,
                maximum=self.limits.max_tokens,
            )
        self.total_bytes += file_bytes
        self.total_tokens += tokens
        return None
