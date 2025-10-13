"""Application services that glue together scanning and rendering."""

from __future__ import annotations

import json as _json
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .constants import (
    CONFIG_INCLUDE_FILE_TAGS,
    CONFIG_INCLUDE_TREE_TAGS,
    OutputMode,
    SummaryFormat,
    TableStyle,
)
from .core import ScanResult, run_scan
from .formatter import human_summary
from .renderers import DirectoryRenderer, build_llm_payload
from .summary import SummaryContext, build_sink_payload_json, build_summary

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .directory import DirectoryTreeBuilder


@dataclass(frozen=True, slots=True)
class ScanOptions:
    mode: OutputMode
    table: TableStyle
    fmt: SummaryFormat = SummaryFormat.HUMAN


@dataclass(frozen=True, slots=True)
class ScanExecutorDependencies:
    scan: Callable[..., ScanResult]
    renderer_factory: Callable[[DirectoryTreeBuilder], DirectoryRenderer]
    human_formatter: Callable[..., str]
    summary_builder: Callable[[SummaryContext], dict[str, Any]]
    sink_payload_builder: Callable[[SummaryContext], dict[str, Any]]
    payload_builder: Callable[..., str]

    @classmethod
    def default(cls) -> ScanExecutorDependencies:
        return cls(
            scan=run_scan,
            renderer_factory=DirectoryRenderer,
            human_formatter=human_summary,
            summary_builder=build_summary,
            sink_payload_builder=build_sink_payload_json,
            payload_builder=build_llm_payload,
        )


class ScanExecutor:
    """Application service that runs a scan and produces both machine and human outputs."""

    def __init__(
        self,
        *,
        sink: Callable[[str], None],
        dependencies: ScanExecutorDependencies | None = None,
    ) -> None:
        self._sink = sink
        self._deps = ScanExecutorDependencies.default() if dependencies is None else dependencies

    @staticmethod
    def _should_emit_json_payload(options: ScanOptions) -> bool:
        return options.fmt is SummaryFormat.JSON and options.mode is not OutputMode.SUMMARY

    def execute(
        self,
        *,
        paths: list[Path],
        cfg: dict[str, object],
        options: ScanOptions,
    ) -> tuple[str, dict[str, Any]]:
        """Return (human summary, json-summary); emit payload to sink as needed."""
        result = self._deps.scan(paths=paths, cfg=cfg)

        ttag = str(cfg.get(CONFIG_INCLUDE_TREE_TAGS, "directory"))
        ftag = str(cfg.get(CONFIG_INCLUDE_FILE_TAGS, "file"))

        builder = result.builder
        context = SummaryContext(
            builder=builder, common=result.common, mode=options.mode, table=options.table
        )

        renderer = self._deps.renderer_factory(builder)
        tree_lines = renderer.tree_lines(include_metadata=True)

        human = self._deps.human_formatter(
            tree_lines=tree_lines,
            total_lines=builder.total_lines,
            total_chars=builder.total_characters,
            table=options.table.value,
        )

        if self._should_emit_json_payload(options):
            payload_json = self._deps.sink_payload_builder(context)
            self._sink(_json.dumps(payload_json, sort_keys=True, indent=2))
            json_summary = self._deps.summary_builder(context)
            return human, json_summary

        payload = self._deps.payload_builder(
            builder=builder,
            common=result.common,
            mode=options.mode,
            tree_tag=ttag,
            file_tag=ftag,
        )
        if payload:
            self._sink(payload)

        # Build a machine-readable summary structure (for SUMMARY mode printing)
        json_summary = self._deps.summary_builder(context)
        return human, json_summary
