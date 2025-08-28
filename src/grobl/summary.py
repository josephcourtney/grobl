"""Helpers to build machine-readable summaries and JSON payloads.

This module centralizes logic that was previously duplicated in services.py:
- constructing per-file entries with binary heuristics
- assembling totals and top-level summary structures
- building the non-summary JSON payload written to the sink
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .constants import OutputMode, TableStyle

if TYPE_CHECKING:  # resolve types for static checkers without runtime imports
    from pathlib import Path

    from .directory import DirectoryTreeBuilder


def _file_entries(builder: DirectoryTreeBuilder) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for key, (ln, ch, included) in builder.metadata_items():
        entry: dict[str, Any] = {"path": key, "lines": ln, "chars": ch, "included": included}
        # Heuristic: non-empty files with zero lines are treated as binary
        is_binary = ch > 0 and ln == 0 and not included
        if is_binary:
            entry["binary"] = True
            details = builder.get_binary_details(key) or {"size_bytes": ch}
            entry["binary_details"] = details
        files.append(entry)
    return files


def _totals(builder: DirectoryTreeBuilder) -> dict[str, int]:
    return {
        "total_lines": builder.total_lines,
        "total_characters": builder.total_characters,
        "all_total_lines": builder.all_total_lines,
        "all_total_characters": builder.all_total_characters,
    }


def build_summary(
    *,
    builder: DirectoryTreeBuilder,
    common: Path,
    mode: OutputMode,
    table: TableStyle,
) -> dict[str, Any]:
    """Build a machine-readable summary for SUMMARY mode printing."""
    return {
        "root": str(common),
        "mode": mode.value,
        "table": table.value,
        "totals": _totals(builder),
        "files": _file_entries(builder),
    }


def build_sink_payload_json(
    *,
    builder: DirectoryTreeBuilder,
    common: Path,
    mode: OutputMode,
    table: TableStyle,
) -> dict[str, Any]:
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
    payload: dict[str, Any] = {
        "root": str(common),
        "mode": mode.value,
    }
    if mode in {OutputMode.ALL, OutputMode.TREE}:
        entries = [{"type": typ, "path": str(rel)} for typ, rel in builder.ordered_entries()]
        payload["tree"] = entries
    if mode in {OutputMode.ALL, OutputMode.FILES}:
        payload["files"] = builder.files_json()

    payload["summary"] = {
        "table": table.value,
        "totals": _totals(builder),
        "files": _file_entries(builder),
    }
    return payload
