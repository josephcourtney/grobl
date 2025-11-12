"""Helpers for building machine-readable summaries and sink payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .constants import OutputMode, TableStyle

if TYPE_CHECKING:  # resolve types for static checkers without runtime imports
    from pathlib import Path

    from .directory import DirectoryTreeBuilder


@dataclass(frozen=True, slots=True)
class SummaryContext:
    """Parameter object capturing the shared summary inputs."""

    builder: DirectoryTreeBuilder
    common: Path
    mode: OutputMode
    table: TableStyle


def _file_entries(builder: DirectoryTreeBuilder) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for key, (ln, ch, included) in builder.metadata_items():
        entry: dict[str, Any] = {"path": key, "lines": ln, "chars": ch, "included": included}
        # Heuristic: non-empty files with zero lines are treated as binary
        is_binary = ch > 0 and ln == 0 and not included
        if is_binary:
            entry["binary"] = True
        files.append(entry)
    return files


def _totals(builder: DirectoryTreeBuilder) -> dict[str, int]:
    return {
        "total_lines": builder.total_lines,
        "total_characters": builder.total_characters,
        "all_total_lines": builder.all_total_lines,
        "all_total_characters": builder.all_total_characters,
    }


def build_summary(context: SummaryContext) -> dict[str, Any]:
    """Build a machine-readable summary for SUMMARY mode printing."""
    builder = context.builder
    return {
        "root": str(context.common),
        "mode": context.mode.value,
        "table": context.table.value,
        "totals": _totals(builder),
        "files": _file_entries(builder),
    }


def build_sink_payload_json(context: SummaryContext) -> dict[str, Any]:
    """Build the JSON payload written to the sink for non-summary JSON mode.

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
        "mode": context.mode.value,
    }
    if context.mode in {OutputMode.ALL, OutputMode.TREE}:
        entries = [{"type": typ, "path": str(rel)} for typ, rel in builder.ordered_entries()]
        payload["tree"] = entries
    if context.mode in {OutputMode.ALL, OutputMode.FILES}:
        payload["files"] = builder.files_json()

    payload["summary"] = {
        "table": context.table.value,
        "totals": _totals(builder),
        "files": _file_entries(builder),
    }
    return payload
