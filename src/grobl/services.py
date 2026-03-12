"""Compatibility facade for application scan execution services.

Core execution logic lives in :mod:`grobl.app.execution`.
"""

from grobl.app.execution import (
    _PAYLOAD_STRATEGIES,
    ContentScope,
    JsonPayloadStrategy,
    LlmPayloadStrategy,
    MarkdownPayloadStrategy,
    NdjsonPayloadStrategy,
    NoopPayloadStrategy,
    PayloadFormat,
    ScanExecutor,
    ScanExecutorDependencies,
    ScanOptions,
    StrategySource,
    SummaryFormat,
    TableStyle,
    build_summary_for_format,
)

__all__ = [
    "_PAYLOAD_STRATEGIES",
    "ContentScope",
    "JsonPayloadStrategy",
    "LlmPayloadStrategy",
    "MarkdownPayloadStrategy",
    "NdjsonPayloadStrategy",
    "NoopPayloadStrategy",
    "PayloadFormat",
    "ScanExecutor",
    "ScanExecutorDependencies",
    "ScanOptions",
    "StrategySource",
    "SummaryFormat",
    "TableStyle",
    "build_summary_for_format",
]
