"""Core scan orchestration: traverses paths, applies config, and collects data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Any

from grobl.directory import DirectoryTreeBuilder, TraverseConfig, traverse_dir
from grobl.errors import ERROR_MSG_EMPTY_PATHS, ScanInterrupted
from grobl.file_handling import (
    FileHandlerRegistry,
    FileProcessingContext,
    ScanDependencies,
)
from grobl.logging_utils import StructuredLogEvent, get_logger, log_event
from grobl.utils import find_common_ancestor

if TYPE_CHECKING:
    from pathlib import Path

    from grobl.ignore import LayeredIgnoreMatcher


logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ScanResult:
    builder: DirectoryTreeBuilder
    common: Path


def _coerce_to_directory(path: Path) -> Path:
    return path.parent if path.is_file() else path


def _determine_builder_base(common: Path, resolved: list[Path], repo_root: Path | None) -> Path:
    if repo_root is None:
        return common
    candidate = _coerce_to_directory(repo_root.resolve(strict=False))
    if all(p.is_relative_to(candidate) for p in resolved):
        return candidate
    return common


def _determine_match_base(match_base: Path | None, resolved: list[Path], default: Path) -> Path:
    if match_base is None:
        return default
    normalized = _coerce_to_directory(match_base.resolve())
    if all(p.is_relative_to(normalized) for p in resolved):
        return normalized
    return default


def run_scan(
    *,
    paths: list[Path],
    cfg: dict[str, Any],
    ignores: LayeredIgnoreMatcher,
    match_base: Path | None = None,
    repo_root: Path | None = None,
    dependencies: ScanDependencies | None = None,
    handlers: FileHandlerRegistry | None = None,
) -> ScanResult:
    """Traverse the requested paths and collect data only."""
    if not paths:
        raise ValueError(ERROR_MSG_EMPTY_PATHS)

    missing = [p for p in paths if not p.exists()]
    if missing:
        raise ValueError("scan paths do not exist: " + ", ".join(sorted(str(p) for p in missing)))

    start = perf_counter()
    resolved = [p.resolve() for p in paths]
    common = find_common_ancestor(resolved)
    if common.is_file():
        # For single-file scans the common ancestor resolves to the file path
        # itself. Normalise to the containing directory so relative paths and
        # directory traversal operate on a directory base.
        common = common.parent
    builder_base = _determine_builder_base(common, resolved, repo_root)
    match_base = _determine_match_base(match_base, resolved, builder_base)

    log_event(
        logger,
        StructuredLogEvent(
            name="scan.start",
            message="starting directory traversal",
            context={
                "path_count": len(resolved),
                "paths": resolved,
                "ignore_tree_layers": len(ignores.tree_layers),
                "ignore_print_layers": len(ignores.print_layers),
                "config_entry_count": len(cfg),
            },
        ),
    )

    builder = DirectoryTreeBuilder(base_path=builder_base, exclude_patterns=[])
    registry = FileHandlerRegistry.default() if handlers is None else handlers
    context = FileProcessingContext(
        builder=builder,
        common=common,
        ignores=ignores,
        dependencies=ScanDependencies.default() if dependencies is None else dependencies,
    )

    def collect(item: Path, prefix: str, *, is_last: bool) -> bool:
        excluded_tree = ignores.excluded_from_tree(item, is_dir=item.is_dir())

        if item.is_dir():
            # Do not render excluded dirs in the tree.
            if not excluded_tree:
                builder.add_directory(item, prefix, is_last=is_last)
                return True

            # Reviewer: "If there are no negations anywhere, excluded dirs can be pruned safely."
            # (place here)
            return ignores.tree_has_negations  # descend only if negations exist

        # file
        if excluded_tree:
            return False

        builder.add_file_to_tree(item, prefix, is_last=is_last)
        registry.handle(path=item, context=context)
        return False

    try:
        traverse_dir(
            common,
            TraverseConfig(
                paths=resolved,
                base=match_base,
                repo_root=repo_root or builder_base,
            ),
            collect,
        )
    except KeyboardInterrupt as _:
        log_event(
            logger,
            StructuredLogEvent(
                name="scan.interrupted",
                message="scan interrupted by user",
                level=logging.WARNING,
                context={"duration_seconds": perf_counter() - start},
            ),
        )
        # Surface the partial state so the CLI can print proper diagnostics.
        raise ScanInterrupted(builder, common) from _

    # duration is emitted inline below to avoid extra locals
    log_event(
        logger,
        StructuredLogEvent(
            name="scan.complete",
            message="completed directory traversal",
            context={
                "duration_seconds": perf_counter() - start,
                "files_processed": len(builder.file_tree_entries()),
                "tree_line_count": len(builder.tree_output()),
            },
        ),
    )

    return ScanResult(
        builder=builder,
        common=common,
    )
