"""Application services that glue together scanning and rendering."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .constants import (
    CONFIG_INCLUDE_FILE_TAGS,
    CONFIG_INCLUDE_TREE_TAGS,
    DEFAULT_FILE_TAG,
    DEFAULT_TREE_TAG,
    OutputMode,
    SummaryFormat,
    TableStyle,
)
from .core import ScanResult, run_scan
from .summary import SummaryContext, build_summary

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .directory import DirectoryTreeBuilder

logger = logging.getLogger(__name__)

# ------------------ Presentation helpers (merged from formatter/renderers) ------------------


class DirectoryRenderer:
    """Responsible for turning collected data into strings/lists for output."""

    def __init__(self, builder: DirectoryTreeBuilder) -> None:
        self.builder = builder

    def tree_lines(self, *, include_metadata: bool = False) -> list[str]:
        raw_tree = self.builder.tree_output()
        base_entry = f"{self.builder.base_path.name}/"
        if not include_metadata:
            return [base_entry, *raw_tree]
        if not raw_tree:
            return [base_entry]
        return self._tree_lines_with_metadata(raw_tree, base_entry)

    def _tree_lines_with_metadata(self, raw_tree: list[str], base_entry: str) -> list[str]:
        builder = self.builder
        name_w = max(max((len(line) for line in raw_tree), default=0), len("lines"))
        line_digits = max((len(str(values[0])) for _, values in builder.metadata_items()), default=1)
        char_digits = max((len(str(values[1])) for _, values in builder.metadata_items()), default=1)
        line_w = max(line_digits, len("lines"))
        char_w = max(char_digits, len("chars"))
        marker_w = len("included")
        output = [
            f"{'':{name_w}} {'lines':>{line_w}} {'chars':>{char_w}} {'included':>{marker_w}}",
            base_entry,
        ]
        entry_map = dict(builder.file_tree_entries())
        for idx, text in enumerate(raw_tree):
            rel = entry_map.get(idx)
            if rel is None:
                output.append(text)
                continue
            ln, ch, included = builder.get_metadata(str(rel)) or (0, 0, False)
            output.append(
                f"{text:<{name_w}} {ln:>{line_w}} {ch:>{char_w}} {' ' if included else '*':>{marker_w}}"
            )
        return output


def human_summary(tree_lines: list[str], total_lines: int, total_chars: int, *, table: str = "full") -> str:
    if table == "none":
        return ""
    if table == "compact":
        return f"Total lines: {total_lines}\nTotal characters: {total_chars}\n"
    max_width = max(len(line) for line in tree_lines) if tree_lines else len(" Project Summary ")
    title = " Project Summary "
    bar = "═" * max((max_width - len(title)) // 2, 0)
    out: list[str] = []
    out.append(f"{bar}{title}{bar}")
    out.extend(tree_lines)
    out.extend((
        "─" * max_width,
        f"Total lines: {total_lines}",
        f"Total characters: {total_chars}",
        "═" * max_width,
    ))
    return "\n".join(out) + ("\n" if out else "")


def _build_tree_payload(builder: DirectoryTreeBuilder, common: Path, *, ttag: str) -> str:
    renderer = DirectoryRenderer(builder)
    tree_xml = "\n".join(renderer.tree_lines(include_metadata=False))
    return f'<{ttag} name="{common.name}" path="{common}">\n{tree_xml}\n</{ttag}>'


def _build_files_payload(builder: DirectoryTreeBuilder, common: Path, *, ftag: str) -> str:
    files_xml = "\n".join(builder.file_contents())
    return f'<{ftag} root="{common.name}">\n{files_xml}\n</{ftag}>'


def build_llm_payload(
    *, builder: DirectoryTreeBuilder, common: Path, mode: OutputMode, tree_tag: str, file_tag: str
) -> str:
    if mode is OutputMode.SUMMARY:
        return ""
    if mode is OutputMode.TREE:
        return _build_tree_payload(builder, common, ttag=tree_tag)
    if mode is OutputMode.FILES:
        return _build_files_payload(builder, common, ftag=file_tag)
    # Deprecated 'all' still supported for now
    return "\n".join([
        _build_tree_payload(builder, common, ttag=tree_tag),
        _build_files_payload(builder, common, ftag=file_tag),
    ])


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
    payload_builder: Callable[..., str]

    @classmethod
    def default(cls) -> ScanExecutorDependencies:
        return cls(
            scan=run_scan,
            renderer_factory=DirectoryRenderer,
            human_formatter=human_summary,
            summary_builder=build_summary,
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

    def execute(
        self,
        *,
        paths: list[Path],
        cfg: dict[str, object],
        options: ScanOptions,
    ) -> tuple[str, dict[str, Any]]:
        """Return both the human summary text and the machine summary payload."""
        logger.info(
            "executor start (paths=%d, mode=%s, format=%s)", len(paths), options.mode.value, options.fmt.value
        )
        result = self._deps.scan(paths=paths, cfg=cfg)

        ttag = str(cfg.get(CONFIG_INCLUDE_TREE_TAGS, DEFAULT_TREE_TAG))
        ftag = str(cfg.get(CONFIG_INCLUDE_FILE_TAGS, DEFAULT_FILE_TAG))

        builder = result.builder

        renderer = self._deps.renderer_factory(builder)
        tree_lines = renderer.tree_lines(include_metadata=True)

        human = self._deps.human_formatter(
            tree_lines=tree_lines,
            total_lines=builder.total_lines,
            total_chars=builder.total_characters,
            table=options.table.value,
        )

        summary_context = SummaryContext(
            builder=builder,
            common=result.common,
            mode=options.mode,
            table=options.table,
        )
        summary_payload = self._deps.summary_builder(summary_context)

        # Emit XML payload (tree/files) via sink when mode requests it.
        payload = self._deps.payload_builder(
            builder=builder,
            common=result.common,
            mode=options.mode,
            tree_tag=ttag,
            file_tag=ftag,
        )
        if payload:
            self._sink(payload)

        logger.info(
            "executor complete (total_lines=%d, total_chars=%d)",
            builder.total_lines,
            builder.total_characters,
        )
        return human, summary_payload
