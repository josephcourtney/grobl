"""Application services that glue together scanning and rendering."""

from __future__ import annotations

import json as _json
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

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
    from logging import Logger
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
    llm_payload_builder: Callable[..., str]
    markdown_payload_builder: Callable[..., str]

    @classmethod
    def default(cls) -> ScanExecutorDependencies:
        return cls(
            scan=run_scan,
            renderer_factory=DirectoryRenderer,
            human_formatter=human_summary,
            summary_builder=build_summary,
            sink_payload_builder=build_sink_payload_json,
            llm_payload_builder=build_llm_payload,
            markdown_payload_builder=build_markdown_payload,
        )


class PayloadStrategy(Protocol):
    def emit(
        self,
        *,
        builder: DirectoryTreeBuilder,
        context: SummaryContext,
        result: ScanResult,
        sink: Callable[[str], None],
        logger: Logger,
        config: dict[str, object],
    ) -> None: ...


@dataclass(slots=True)
class JsonPayloadStrategy:
    build_payload: Callable[[SummaryContext], dict[str, Any]]

    def emit(
        self,
        *,
        builder: DirectoryTreeBuilder,
        context: SummaryContext,
        result: ScanResult,  # noqa: ARG002 - retained for protocol symmetry
        sink: Callable[[str], None],
        logger: Logger,
        config: dict[str, object],  # noqa: ARG002
    ) -> None:
        payload_json = self.build_payload(context)
        sink(_json.dumps(payload_json, sort_keys=True, indent=2))
        log_event(
            logger,
            StructuredLogEvent(
                name="executor.emitted_json",
                message="emitted json payload to sink",
                context={
                    "tree_entries": len(builder.tree_output()),
                    "file_entries": len(builder.file_contents()),
                },
            ),
        )


@dataclass(slots=True)
class MarkdownPayloadStrategy:
    build_payload: Callable[..., str]

    def emit(
        self,
        *,
        builder: DirectoryTreeBuilder,
        context: SummaryContext,
        result: ScanResult,
        sink: Callable[[str], None],
        logger: Logger,  # noqa: ARG002
        config: dict[str, object],  # noqa: ARG002
    ) -> None:
        payload = self.build_payload(
            builder=builder,
            common=result.common,
            scope=context.scope,
        )
        if payload:
            sink(payload)


@dataclass(slots=True)
class LlmPayloadStrategy:
    build_payload: Callable[..., str]

    def emit(
        self,
        *,
        builder: DirectoryTreeBuilder,
        context: SummaryContext,
        result: ScanResult,
        sink: Callable[[str], None],
        logger: Logger,  # noqa: ARG002
        config: dict[str, object],
    ) -> None:
        tree_tag = str(config.get(CONFIG_INCLUDE_TREE_TAGS, "directory"))
        file_tag = str(config.get(CONFIG_INCLUDE_FILE_TAGS, "file"))
        payload = self.build_payload(
            builder=builder,
            common=result.common,
            scope=context.scope,
            tree_tag=tree_tag,
            file_tag=file_tag,
        )
        if payload:
            sink(payload)


@dataclass(slots=True)
class NoopPayloadStrategy:
    def emit(  # noqa: PLR6301
        self,
        *,
        builder: DirectoryTreeBuilder,  # noqa: ARG002
        context: SummaryContext,  # noqa: ARG002
        result: ScanResult,  # noqa: ARG002
        sink: Callable[[str], None],  # noqa: ARG002
        logger: Logger,  # noqa: ARG002
        config: dict[str, object],  # noqa: ARG002
    ) -> None:
        return


StrategySource = PayloadStrategy | Callable[[ScanExecutorDependencies], PayloadStrategy]


def _build_default_payload_strategies(
    deps: ScanExecutorDependencies,
) -> dict[PayloadFormat, PayloadStrategy]:
    sources: dict[PayloadFormat, StrategySource] = dict(_PAYLOAD_STRATEGIES)
    strategies: dict[PayloadFormat, PayloadStrategy] = {}
    for fmt, source in sources.items():
        if hasattr(source, "emit"):
            strategies[fmt] = source  # type: ignore[assignment]
        else:
            factory = source  # type: ignore[assignment]
            strategies[fmt] = factory(deps)
    return strategies


def build_summary_for_format(
    *,
    base_summary: dict[str, Any],
    fmt: SummaryFormat,
    renderer: DirectoryRenderer,
    builder: DirectoryTreeBuilder,
    options: ScanOptions,
    human_formatter: Callable[..., str],
) -> tuple[str, dict[str, Any]]:
    if fmt is SummaryFormat.NONE:
        minimal = {
            "root": base_summary["root"],
            "scope": base_summary["scope"],
            "style": base_summary["style"],
            "totals": base_summary["totals"],
            "files": [],
        }
        return "", minimal
    if fmt is SummaryFormat.JSON:
        return "", base_summary

    tree_lines = renderer.tree_lines(include_metadata=True)
    human_summary_text = human_formatter(
        tree_lines=tree_lines,
        total_lines=builder.total_lines,
        total_chars=builder.total_characters,
        table=options.summary_style.value,
    )
    return human_summary_text, base_summary


_PAYLOAD_STRATEGIES: dict[PayloadFormat, StrategySource] = {
    PayloadFormat.JSON: lambda deps: JsonPayloadStrategy(deps.sink_payload_builder),
    PayloadFormat.MARKDOWN: lambda deps: MarkdownPayloadStrategy(deps.markdown_payload_builder),
    PayloadFormat.LLM: lambda deps: LlmPayloadStrategy(deps.llm_payload_builder),
    PayloadFormat.NONE: NoopPayloadStrategy(),
}


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
        self._payload_strategies = _build_default_payload_strategies(self._deps)

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

        builder = result.builder
        context = SummaryContext(
            builder=builder,
            common=result.common,
            scope=options.scope,
            style=options.summary_style,
        )

        renderer = self._deps.renderer_factory(builder)
        strategy = self._payload_strategies[options.payload_format]
        strategy.emit(
            builder=builder,
            context=context,
            result=result,
            sink=self._sink,
            logger=self._logger,
            config=cfg,
        )

        base_summary = self._deps.summary_builder(context)
        human_summary_text, summary_dict = build_summary_for_format(
            base_summary=base_summary,
            fmt=options.summary_format,
            renderer=renderer,
            builder=builder,
            options=options,
            human_formatter=self._deps.human_formatter,
        )

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
