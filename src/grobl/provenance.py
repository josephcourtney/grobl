"""Helpers for rendering ignore provenance to stable dictionaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from .ignore import ExclusionReason

NON_TEXT_REASON_PATTERN = "<non-text>"
TEXT_DETECTION_SOURCE = "text-detection"


def _fmt_path(value: Path | str) -> str:
    return str(value)


def exclusion_reason_to_dict(reason: ExclusionReason) -> dict[str, Any]:
    """Return a JSON-friendly dict describing a matching ignore pattern."""
    return {
        "pattern": reason.raw,
        "negated": reason.negated,
        "source": reason.source.value,
        "base_dir": _fmt_path(reason.base_dir),
        "config_path": _fmt_path(reason.config_path) if reason.config_path else None,
        "detail": None,
    }


def format_content_reason(
    *,
    reason: ExclusionReason | None = None,
    detection_detail: str | None = None,
    subject: Path,
) -> dict[str, Any] | None:
    """Return a consistent reason dict for content exclusions."""
    if reason is not None:
        return exclusion_reason_to_dict(reason)

    if detection_detail is None:
        detection_detail = "binary file"
    return {
        "pattern": NON_TEXT_REASON_PATTERN,
        "negated": False,
        "source": TEXT_DETECTION_SOURCE,
        "base_dir": _fmt_path(subject.parent),
        "config_path": None,
        "detail": detection_detail,
    }
