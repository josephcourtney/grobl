from __future__ import annotations

import json as _json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .constants import CONFIG_INCLUDE_FILE_TAGS, CONFIG_INCLUDE_TREE_TAGS, OutputMode, TableStyle
from .core import run_scan
from .formatter import human_summary
from .renderers import DirectoryRenderer, build_llm_payload
from .summary import build_sink_payload_json, build_summary

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@dataclass(frozen=True)
class ScanOptions:
    mode: OutputMode
    table: TableStyle
    fmt: str = "human"


class ScanExecutor:
    """Application service that runs a scan and produces both machine and human outputs."""

    def __init__(self, sink: Callable[[str], None]) -> None:
        self._sink = sink

    def execute(
        self,
        *,
        paths: list[Path],
        cfg: dict[str, object],
        options: ScanOptions,
    ) -> tuple[str, dict[str, Any]]:
        """Return (human summary, json-summary); emit payload to sink as needed."""
        result = run_scan(paths=paths, cfg=cfg)

        ttag = str(cfg.get(CONFIG_INCLUDE_TREE_TAGS, "directory"))
        ftag = str(cfg.get(CONFIG_INCLUDE_FILE_TAGS, "file"))

        if options.fmt == "json" and options.mode != OutputMode.SUMMARY:
            payload_json = build_sink_payload_json(
                builder=result.builder,
                common=result.common,
                mode=options.mode,
                table=options.table,
            )
            self._sink(_json.dumps(payload_json, sort_keys=True, indent=2))
        else:
            payload = build_llm_payload(
                builder=result.builder,
                common=result.common,
                mode=options.mode,
                tree_tag=ttag,
                file_tag=ftag,
            )
            if payload:
                self._sink(payload)

        renderer = DirectoryRenderer(result.builder)
        tree_lines = renderer.tree_lines(include_metadata=True)

        human = human_summary(
            tree_lines=tree_lines,
            total_lines=result.builder.total_lines,
            total_chars=result.builder.total_characters,
            table=options.table.value,
        )
        # Build a machine-readable summary structure (for SUMMARY mode printing)
        json_summary = build_summary(
            builder=result.builder,
            common=result.common,
            mode=options.mode,
            table=options.table,
        )
        return human, json_summary
