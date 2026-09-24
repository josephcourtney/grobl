"""Helpers for building machine-readable summaries and sink payloads."""

from __future__ import annotations

import json as _json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .constants import ContentScope, TableStyle
from .metadata_visibility import DEFAULT_METADATA_VISIBILITY, MetadataVisibility

if TYPE_CHECKING:
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
    files = tuple(snapshot.iter_files())
    totals["included_files"] = sum(1 for _, record in files if record.included)
    totals["all_files"] = len(files)
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


def _generated_sources(builder: DirectoryTreeBuilder, rel: Path, *, is_dir: bool = False) -> tuple[str, ...]:
    getter = getattr(builder, "generated_sources", None)
    if not callable(getter):
        return ()
    result = getter(rel, is_dir=is_dir)
    return tuple(str(item) for item in result)


def _file_entries(
    builder: DirectoryTreeBuilder,
    snapshot: SummaryTotals,
    *,
    visibility: MetadataVisibility,
) -> list[dict[str, Any]]:
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
        generated_from = _generated_sources(builder, Path(key))
        if generated_from:
            entry["generated_from"] = list(generated_from)
        reason_source = record.content_reason.get("source") if record.content_reason is not None else None
        if reason_source == "text-detection":
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
        "files": _file_entries(builder, snapshot, visibility=context.visibility),
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


def _tree_entry(builder: DirectoryTreeBuilder, typ: str, rel: Path) -> dict[str, Any]:
    entry: dict[str, Any] = {"type": typ, "path": str(rel)}
    generated_from = _generated_sources(builder, rel, is_dir=typ == "dir")
    if generated_from:
        entry["generated_from"] = list(generated_from)
    if typ != "symlink":
        return entry
    info = builder.symlink_info(rel)
    if info is None:
        return entry
    entry.update({
        "target": info.target,
        "target_scope": info.scope,
        "broken": info.broken,
    })
    if info.resolved_target is not None:
        entry["resolved_target"] = str(info.resolved_target)
    return entry


def _relationships(builder: DirectoryTreeBuilder) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    for typ, rel in builder.ordered_entries():
        if typ != "file":
            continue
        sources = _generated_sources(builder, rel)
        if not sources:
            continue
        relationships.append({
            "type": "generated_from",
            "path": str(rel),
            "sources": list(sources),
        })
    return relationships


def build_sink_payload_json(context: SummaryContext) -> dict[str, Any]:
    """Build the JSON payload written to the sink for JSON format runs."""
    builder = context.builder
    payload: dict[str, Any] = {
        "root": str(context.common),
        "scope": context.scope.value,
    }
    tree_entries: list[dict[str, Any]] = []
    file_entries: list[dict[str, Any]] = []
    if context.scope in {ContentScope.ALL, ContentScope.TREE}:
        tree_entries = [_tree_entry(builder, typ, rel) for typ, rel in builder.ordered_entries()]
        relationships = _relationships(builder)
        if relationships:
            payload["relationships"] = relationships
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
    relationships = payload.get("relationships")
    if relationships is not None:
        records.append({"type": "relationships", "entries": relationships})
    files = payload.get("files")
    if files is not None:
        records.append({"type": "files", "entries": files})
    records.append({"type": "summary", "summary": payload["summary"]})

    lines = [_json.dumps(record, sort_keys=True, separators=(",", ":")) for record in records]
    return "\n".join(lines) + "\n"
