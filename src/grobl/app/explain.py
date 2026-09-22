"""Application logic for explain output."""

from __future__ import annotations

import json
import operator
from typing import TYPE_CHECKING, Any

import click

from grobl.constants import InclusionLevel
from grobl.provenance import format_content_reason, inclusion_reason_to_dict
from grobl.resource_limits import ResourceBudget, ResourceLimits, UNLIMITED_RESOURCE_LIMITS
from grobl.token_counting import count_tokens
from grobl.utils import detect_text, read_text

if TYPE_CHECKING:
    from pathlib import Path

    from grobl.ignore import LayeredIgnoreMatcher


def validate_existing_paths(paths: tuple[Path, ...]) -> list[Path]:
    """Resolve and validate explain targets."""
    validated: list[Path] = []
    for path in paths:
        try:
            path.lstat()
        except OSError as err:
            msg = f"path not found: {path}"
            raise click.UsageError(msg) from err
        validated.append(path.resolve(strict=False))
    return validated


def build_explain_entries(
    *,
    paths: tuple[Path, ...],
    ignores: LayeredIgnoreMatcher,
    limits: ResourceLimits = UNLIMITED_RESOURCE_LIMITS,
) -> list[dict[str, Any]]:
    """Return sorted explain entries for the given targets."""
    validated_paths = sorted(
        validate_existing_paths(paths),
        key=lambda path: tuple(part.casefold() for part in path.parts),
    )
    budget = ResourceBudget(limits)
    return sorted(
        (_explain_entry(path, ignores, budget) for path in validated_paths),
        key=operator.itemgetter("path"),
    )


def render_explain(entries: list[dict[str, Any]], *, explain_format: str) -> str:
    """Render explain entries in the requested format."""
    normalized_format = explain_format.lower()
    if normalized_format == "human":
        normalized_format = "markdown"
    return _render_json(entries) if normalized_format == "json" else _render_human(entries)


def _build_reason(reason: dict[str, Any] | None) -> str:
    if reason is None:
        return "none"
    parts = [f"pattern={reason['pattern']}", f"state={reason['state']}"]
    if reason.get("negated"):
        parts.append("negated")
    parts.extend((f"source={reason['source']}", f"base={reason['base_dir']}"))
    if reason.get("config_path"):
        parts.append(f"config={reason['config_path']}")
    if reason.get("detail"):
        parts.append(f"detail={reason['detail']}")
    return "; ".join(parts)


def _render_human(entries: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for entry in entries:
        lines.extend((f"Path: {entry['path']}", f"  state: {entry['state']}"))
        if entry.get("reason"):
            lines.append(f"    reason: {_build_reason(entry['reason'])}")
        tree = entry["tree"]
        lines.append(f"  tree: {'included' if tree['included'] else 'excluded'}")
        content = entry["content"]
        lines.append(f"  content: {'included' if content['included'] else 'excluded'}")
        if content.get("reason") and content.get("reason") != entry.get("reason"):
            lines.append(f"    reason: {_build_reason(content['reason'])}")
        if entry.get("text_detection"):
            details = entry["text_detection"]
            detail = details.get("detail") or "binary file"
            lines.append(f"  text detection: binary ({detail})")
        limits = entry.get("resource_limits")
        if limits:
            lines.append(
                "  resource limits: "
                f"file-bytes={limits['max_file_bytes'] or 'unlimited'}; "
                f"total-bytes={limits['max_total_bytes'] or 'unlimited'}; "
                f"tokens={limits['max_tokens'] or 'unlimited'}"
            )
    lines.append("")
    return "\n".join(lines)


def _render_json(entries: list[dict[str, Any]]) -> str:
    return json.dumps(entries, sort_keys=True, indent=2) + "\n"


def _explain_entry(
    abs_path: Path,
    ignores: LayeredIgnoreMatcher,
    budget: ResourceBudget,
) -> dict[str, Any]:
    limits = budget.limits
    is_dir = abs_path.is_dir()
    decision = ignores.explain_inclusion(abs_path, is_dir=is_dir)
    reason = inclusion_reason_to_dict(decision.reason) if decision.reason is not None else None

    entry: dict[str, Any] = {
        "path": str(abs_path),
        "state": decision.level.value,
        "reason": reason,
        "resource_limits": limits.to_dict(),
        "tree": {
            "included": decision.level is not InclusionLevel.OMIT,
            "reason": reason if decision.level is InclusionLevel.OMIT else None,
        },
    }

    content_included = decision.level is InclusionLevel.FULL
    content_reason: dict[str, Any] | None = reason if decision.level is InclusionLevel.TREE_ONLY else None
    text_detection: dict[str, Any] | None = None

    if abs_path.is_file() and decision.level is InclusionLevel.FULL:
        try:
            file_bytes = abs_path.stat().st_size
        except OSError:
            file_bytes = None
        budget_reason = (
            budget.preflight(abs_path, file_bytes=file_bytes)
            if file_bytes is not None
            else None
        )
        if budget_reason is not None:
            content_included = False
            content_reason = budget_reason
        else:
            detection = detect_text(abs_path)
            if not detection.is_text:
                content_included = False
                content_reason = format_content_reason(
                    detection_detail=detection.detail,
                    subject=abs_path,
                )
                detail = detection.detail or "binary file"
                text_detection = {"is_text": False, "detail": detail}
            else:
                tokens = 0
                actual_bytes = file_bytes
                if limits.max_tokens is not None or actual_bytes is None:
                    try:
                        content = read_text(abs_path)
                    except OSError as err:
                        content_included = False
                        content_reason = format_content_reason(
                            detection_detail=f"read error: {err}",
                            subject=abs_path,
                        )
                    else:
                        tokens = count_tokens(content) if limits.max_tokens is not None else 0
                        actual_bytes = (
                            file_bytes
                            if file_bytes is not None
                            else len(content.encode("utf-8"))
                        )
                if content_included and actual_bytes is not None:
                    budget_reason = budget.accept(
                        abs_path,
                        file_bytes=actual_bytes,
                        tokens=tokens,
                    )
                    if budget_reason is not None:
                        content_included = False
                        content_reason = budget_reason

    entry["content"] = {"included": content_included, "reason": content_reason}
    if text_detection is not None:
        entry["text_detection"] = text_detection

    return entry
