"""Application logic for explain output."""

from __future__ import annotations

import json
import operator
from typing import TYPE_CHECKING, Any

import click

from grobl.provenance import exclusion_reason_to_dict, format_content_reason
from grobl.utils import detect_text

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
) -> list[dict[str, Any]]:
    """Return sorted explain entries for the given targets."""
    validated_paths = validate_existing_paths(paths)
    return sorted(
        (_explain_entry(path, ignores) for path in validated_paths),
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
    parts = [f"pattern={reason['pattern']}"]
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
        lines.append(f"Path: {entry['path']}")
        tree = entry["tree"]
        lines.append(f"  tree: {'included' if tree['included'] else 'excluded'}")
        if tree.get("reason"):
            lines.append(f"    reason: {_build_reason(tree['reason'])}")
        content = entry["content"]
        lines.append(f"  content: {'included' if content['included'] else 'excluded'}")
        if content.get("reason"):
            lines.append(f"    reason: {_build_reason(content['reason'])}")
        if entry.get("text_detection"):
            details = entry["text_detection"]
            detail = details.get("detail") or "binary file"
            lines.append(f"  text detection: binary ({detail})")
    lines.append("")
    return "\n".join(lines)


def _render_json(entries: list[dict[str, Any]]) -> str:
    return json.dumps(entries, sort_keys=True, indent=2) + "\n"


def _explain_entry(abs_path: Path, ignores: LayeredIgnoreMatcher) -> dict[str, Any]:
    is_dir = abs_path.is_dir()
    tree_decision = ignores.explain_tree(abs_path, is_dir=is_dir)
    content_decision = ignores.explain_content(abs_path, is_dir=is_dir)

    tree_reason = exclusion_reason_to_dict(tree_decision.reason) if tree_decision.reason else None
    entry: dict[str, Any] = {
        "path": str(abs_path),
        "tree": {"included": not tree_decision.excluded, "reason": tree_reason},
    }

    content_included = not content_decision.excluded
    content_reason: dict[str, Any] | None = None
    text_detection: dict[str, Any] | None = None

    if content_decision.excluded and content_decision.reason is not None:
        content_reason = exclusion_reason_to_dict(content_decision.reason)
    elif abs_path.is_file() and not content_decision.excluded:
        detection = detect_text(abs_path)
        if not detection.is_text:
            content_included = False
            content_reason = format_content_reason(detection_detail=detection.detail, subject=abs_path)
            detail = detection.detail or "binary file"
            text_detection = {"is_text": False, "detail": detail}

    entry["content"] = {"included": content_included, "reason": content_reason}
    if text_detection is not None:
        entry["text_detection"] = text_detection

    return entry
