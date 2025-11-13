"""Application services that glue together scanning and rendering."""

from __future__ import annotations

import json as _json
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .constants import (
    CONFIG_INCLUDE_FILE_TAGS,
    CONFIG_INCLUDE_TREE_TAGS,
    ContentScope,
    PayloadFormat,
    SummaryFormat,
    TableStyle,
)
from .core import ScanResult, run_scan
from .formatter import human_summary
from .logging_utils import StructuredLogEvent, get_logger, log_event
from .renderers import DirectoryRenderer, build_llm_payload, build_markdown_payload
from .summary import SummaryContext, build_sink_payload_json, build_summary

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .directory import DirectoryTreeBuilder


@dataclass(frozen=True, slots=True)
class ScanOptions:
    scope: ContentScope
    payload_format: PayloadFormat
    summary_format: SummaryFormat
    summary_style: TableStyle


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

    _logger = get_logger(__name__)

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
        return options.payload_format is PayloadFormat.JSON

    def execute(
        self,
        *,
        paths: list[Path],
        cfg: dict[str, object],
        options: ScanOptions,
    ) -> tuple[str, dict[str, Any]]:
        """Return (human summary, json-summary); emit payload to sink as needed."""
        log_event(
            self._logger,
            StructuredLogEvent(
                name="executor.start",
                message="starting scan executor",
                context={
                    "path_count": len(paths),
                    "scope": options.scope.value,
                    "payload_format": options.payload_format.value,
                    "summary_format": options.summary_format.value,
                },
            ),
        )
        result = self._deps.scan(paths=paths, cfg=cfg)

        ttag = str(cfg.get(CONFIG_INCLUDE_TREE_TAGS, "directory"))
        ftag = str(cfg.get(CONFIG_INCLUDE_FILE_TAGS, "file"))

        builder = result.builder
        context = SummaryContext(
            builder=builder,
            common=result.common,
            scope=options.scope,
            style=options.summary_style,
        )

        renderer = self._deps.renderer_factory(builder)

        human_summary_text = ""
        if options.summary_format is SummaryFormat.HUMAN:
            tree_lines = renderer.tree_lines(include_metadata=True)
            human_summary_text = self._deps.human_formatter(
                tree_lines=tree_lines,
                total_lines=builder.total_lines,
                total_chars=builder.total_characters,
                table=options.summary_style.value,
            )

        if self._should_emit_json_payload(options):
            payload_json = self._deps.sink_payload_builder(context)
            self._sink(_json.dumps(payload_json, sort_keys=True, indent=2))
            log_event(
                self._logger,
                StructuredLogEvent(
                    name="executor.emitted_json",
                    message="emitted json payload to sink",
                    context={
                        "tree_entries": len(builder.tree_output()),
                        "file_entries": len(builder.file_contents()),
                    },
                ),
            )
        elif options.payload_format is PayloadFormat.LLM:
            payload = self._deps.payload_builder(
                builder=builder,
                common=result.common,
                scope=options.scope,
                tree_tag=ttag,
                file_tag=ftag,
            )
            if payload:
                self._sink(payload)
        elif options.payload_format is PayloadFormat.MARKDOWN:
            payload = build_markdown_payload(
                builder=builder,
                common=result.common,
                scope=options.scope,
            )
            if payload:
                self._sink(payload)

        base_summary = self._deps.summary_builder(context)

        if options.summary_format is SummaryFormat.NONE:
            summary_dict = {
                "root": base_summary["root"],
                "scope": base_summary["scope"],
                "style": base_summary["style"],
                "totals": base_summary["totals"],
                "files": [],
            }
            human_summary_text = ""
        elif options.summary_format is SummaryFormat.JSON:
            summary_dict = base_summary
            human_summary_text = ""
        else:
            summary_dict = base_summary

        log_event(
            self._logger,
            StructuredLogEvent(
                name="executor.complete",
                message="scan executor completed",
                context={
                    "total_lines": builder.total_lines,
                    "total_characters": builder.total_characters,
                },
            ),
        )
        return human_summary_text, summary_dict
