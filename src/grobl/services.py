from __future__ import annotations

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
            files.append({"path": key, "lines": ln, "chars": ch, "included": included})
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
