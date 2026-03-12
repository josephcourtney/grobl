"""Helpers for building machine-readable summaries and sink payloads."""

from __future__ import annotations

import json as _json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .constants import ContentScope, TableStyle
from .metadata_visibility import DEFAULT_METADATA_VISIBILITY, MetadataVisibility

if TYPE_CHECKING:  # resolve types for static checkers without runtime imports
    from pathlib import Path

    from .directory import DirectoryTreeBuilder, SummaryTotals


@dataclass(frozen=True, slots=True)
class SummaryContext:
    """Parameter object capturing the shared summary inputs."""

    builder: DirectoryTreeBuilder
    common: Path
    scope: ContentScope
    style: TableStyle
    visibility: MetadataVisibility = DEFAULT_METADATA_VISIBILITY


def _visible_totals(context: SummaryContext, snapshot: SummaryTotals) -> dict[str, int]:
    totals: dict[str, int] = {}
    visibility = context.visibility
    if visibility.lines:
        totals["total_lines"] = snapshot.total_lines
        totals["all_total_lines"] = snapshot.all_total_lines
    if visibility.chars:
        totals["total_characters"] = snapshot.total_characters
        totals["all_total_characters"] = snapshot.all_total_characters
    if visibility.tokens:
        totals["total_tokens"] = snapshot.total_tokens
        totals["all_total_tokens"] = snapshot.all_total_tokens
    return totals


def _file_entries(snapshot: SummaryTotals, *, visibility: MetadataVisibility) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for key, record in snapshot.iter_files():
        entry: dict[str, Any] = {"path": key}
        if visibility.lines:
            entry["lines"] = record.lines
        if visibility.chars:
            entry["chars"] = record.chars
        if visibility.tokens:
            entry["tokens"] = record.tokens
        if visibility.inclusion_status:
            entry["included"] = record.included
        if record.content_reason is not None:
            entry["content_reason"] = record.content_reason
        # Heuristic: non-empty files with zero lines are treated as binary
        is_binary = record.chars > 0 and record.lines == 0 and not record.included
        if is_binary:
            entry["binary"] = True
        files.append(entry)
    return files


def build_summary(context: SummaryContext) -> dict[str, Any]:
    """Build a machine-readable summary from collected scan data."""
    builder = context.builder
    snapshot = builder.summary_totals()
    return {
        "root": str(context.common),
        "scope": context.scope.value,
        "style": context.style.value,
        "totals": _visible_totals(context, snapshot),
        "files": _file_entries(snapshot, visibility=context.visibility),
    }


def _visible_payload_file_entry(
    entry: dict[str, Any],
    *,
    visibility: MetadataVisibility,
) -> dict[str, Any]:
    filtered = {
        "name": entry["name"],
        "path": entry["path"],
        "content": entry["content"],
    }
    if visibility.lines and "lines" in entry:
        filtered["lines"] = entry["lines"]
    if visibility.chars and "chars" in entry:
        filtered["chars"] = entry["chars"]
    if visibility.tokens and "tokens" in entry:
        filtered["tokens"] = entry["tokens"]
    if visibility.inclusion_status and "included" in entry:
        filtered["included"] = entry["included"]
    return filtered


def build_sink_payload_json(context: SummaryContext) -> dict[str, Any]:
    """Build the JSON payload written to the sink for JSON format runs.

    Structure is preserved for backward compatibility with existing behavior:
    {
      "root": str,
      "mode": str,
      "tree"?: list,
      "files"?: list,
      "summary": {"table": str, "totals": {...}, "files": [...]}
    }
    """
    builder = context.builder
    payload: dict[str, Any] = {
        "root": str(context.common),
        "scope": context.scope.value,
    }
    tree_entries: list[dict[str, str]] = []
    file_entries: list[dict[str, Any]] = []
    if context.scope in {ContentScope.ALL, ContentScope.TREE}:
        tree_entries = [{"type": typ, "path": str(rel)} for typ, rel in builder.ordered_entries()]
    if context.scope in {ContentScope.ALL, ContentScope.FILES}:
        file_entries = [
            _visible_payload_file_entry(entry, visibility=context.visibility)
            for entry in builder.files_json()
        ]
    payload["tree"] = tree_entries
    payload["files"] = file_entries

    payload["summary"] = build_summary(context)
    return payload


def build_ndjson_payload(context: SummaryContext) -> str:
    """Build an NDJSON payload orientated around the summary data."""
    payload = build_sink_payload_json(context)
    records: list[dict[str, Any]] = []
    tree = payload.get("tree")
    if tree is not None:
        records.append({"type": "tree", "entries": tree})
    files = payload.get("files")
    if files is not None:
        records.append({"type": "files", "entries": files})
    records.append({"type": "summary", "summary": payload["summary"]})

    lines = [_json.dumps(record, sort_keys=True, separators=(",", ":")) for record in records]
    return "\n".join(lines) + "\n"
