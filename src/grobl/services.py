from __future__ import annotations

import json as _json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from .constants import CONFIG_INCLUDE_FILE_TAGS, CONFIG_INCLUDE_TREE_TAGS, OutputMode, TableStyle
from .core import run_scan
from .formatter import human_summary
from .renderers import DirectoryRenderer, build_llm_payload

if TYPE_CHECKING:
    from pathlib import Path


class OutputSink(Protocol):
    def write(self, content: str) -> None: ...


@dataclass(frozen=True)
class ScanOptions:
    mode: OutputMode
    table: TableStyle
    fmt: str = "human"


class ScanExecutor:
    """Application service that runs a scan and produces both machine and human outputs."""

    def __init__(self, sink: OutputSink) -> None:
        self._sink = sink

    def execute(
        self,
        *,
        paths: list[Path],
        cfg: dict[str, object],
        options: ScanOptions,
    ) -> tuple[str, dict[str, Any]]:
        """Return (human summary, json-summary); emit LLM payload to sink.

        "The CLI stays thin; this service is easy to unit-test.".
        """
        result = run_scan(paths=paths, cfg=cfg)

        ttag = str(cfg.get(CONFIG_INCLUDE_TREE_TAGS, "directory"))
        ftag = str(cfg.get(CONFIG_INCLUDE_FILE_TAGS, "file"))

        if options.fmt == "json" and options.mode != OutputMode.SUMMARY:
            # Build JSON payload and embed summary information
            payload_json: dict[str, Any] = {
                "root": str(result.common),
                "mode": options.mode.value,
            }
            if options.mode in {OutputMode.ALL, OutputMode.TREE}:
                entries = [{"type": typ, "path": str(rel)} for typ, rel in result.builder.ordered_entries()]
                payload_json["tree"] = entries
            if options.mode in {OutputMode.ALL, OutputMode.FILES}:
                payload_json["files"] = result.builder.files_json()

            # Prepare summary contents consistent with summary mode
            sum_files: list[dict[str, Any]] = []
            for key, (ln, ch, included) in result.builder.metadata_items():
                entry: dict[str, Any] = {"path": key, "lines": ln, "chars": ch, "included": included}
                is_binary = ch > 0 and ln == 0 and not included
                if is_binary:
                    entry["binary"] = True
                    details = result.builder.get_binary_details(key) or {"size_bytes": ch}
                    entry["binary_details"] = details
                sum_files.append(entry)
            payload_json["summary"] = {
                "table": options.table.value,
                "totals": {
                    "total_lines": result.builder.total_lines,
                    "total_characters": result.builder.total_characters,
                    "all_total_lines": result.builder.all_total_lines,
                    "all_total_characters": result.builder.all_total_characters,
                },
                "files": sum_files,
            }

            self._sink.write(_json.dumps(payload_json, sort_keys=True, indent=2))
        else:
            payload = build_llm_payload(
                builder=result.builder,
                common=result.common,
                mode=options.mode,
                tree_tag=ttag,
                file_tag=ftag,
            )
            if payload:
                self._sink.write(payload)

        renderer = DirectoryRenderer(result.builder)
        tree_lines = renderer.tree_lines(include_metadata=True)

        human = human_summary(
            tree_lines=tree_lines,
            total_lines=result.builder.total_lines,
            total_chars=result.builder.total_characters,
            table=options.table.value,
        )
        # Build a machine-readable summary structure
        files: list[dict[str, Any]] = []
        for key, (ln, ch, included) in result.builder.metadata_items():
            entry: dict[str, Any] = {"path": key, "lines": ln, "chars": ch, "included": included}
            # Heuristic: non-empty files with zero lines are treated as binary
            is_binary = ch > 0 and ln == 0 and not included
            if is_binary:
                entry["binary"] = True
                details = result.builder.get_binary_details(key) or {"size_bytes": ch}
                entry["binary_details"] = details
            files.append(entry)
        json_summary: dict[str, Any] = {
            "root": str(result.common),
            "mode": options.mode.value,
            "table": options.table.value,
            "totals": {
                "total_lines": result.builder.total_lines,
                "total_characters": result.builder.total_characters,
                "all_total_lines": result.builder.all_total_lines,
                "all_total_characters": result.builder.all_total_characters,
            },
            "files": files,
        }
        return human, json_summary
