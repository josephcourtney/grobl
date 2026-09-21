"""Helpers for rendering inclusion-policy provenance to stable dictionaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from .ignore import InclusionReason

NON_TEXT_REASON_PATTERN = "<non-text>"
TEXT_DETECTION_SOURCE = "text-detection"


def _fmt_path(value: Path | str) -> str:
    return str(value)


def inclusion_reason_to_dict(reason: InclusionReason) -> dict[str, Any]:
    """Return a JSON-friendly dict describing the winning policy rule."""

    return {
        "pattern": reason.raw,
        "state": reason.level.value,
        "negated": reason.negated,
        "source": reason.source.value,
        "base_dir": _fmt_path(reason.base_dir),
        "config_path": _fmt_path(reason.config_path) if reason.config_path else None,
        "detail": None,
    }


# Compatibility name retained for consumers of the former exclusion API.
exclusion_reason_to_dict = inclusion_reason_to_dict


def format_content_reason(
    *,
    reason: InclusionReason | None = None,
    detection_detail: str | None = None,
    subject: Path,
) -> dict[str, Any] | None:
    """Return a consistent reason dict for content omissions."""

    if reason is not None:
        return inclusion_reason_to_dict(reason)

    if detection_detail is None:
        detection_detail = "binary file"
    return {
        "pattern": NON_TEXT_REASON_PATTERN,
        "state": "full",
        "negated": False,
        "source": TEXT_DETECTION_SOURCE,
        "base_dir": _fmt_path(subject.parent),
        "config_path": None,
        "detail": detection_detail,
    }
