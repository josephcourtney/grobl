"""Core scan orchestration: traverses paths, applies config, and collects data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Any

from pathspec import PathSpec

from grobl.constants import (
    CONFIG_EXCLUDE_PRINT,
    CONFIG_EXCLUDE_TREE,
)
from grobl.directory import DirectoryTreeBuilder, traverse_dir
from grobl.errors import ERROR_MSG_EMPTY_PATHS, ScanInterrupted
from grobl.file_handling import (
    FileHandlerRegistry,
    FileProcessingContext,
    ScanDependencies,
)
from grobl.utils import find_common_ancestor

if TYPE_CHECKING:
    from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScanResult:
    builder: DirectoryTreeBuilder
    common: Path


def run_scan(
    *,
    paths: list[Path],
    cfg: dict[str, Any],
    dependencies: ScanDependencies | None = None,
    handlers: FileHandlerRegistry | None = None,
) -> ScanResult:
    """Traverse the requested paths and collect data only."""
    if not paths:
        raise ValueError(ERROR_MSG_EMPTY_PATHS)

    missing = [p for p in paths if not p.exists()]
    if missing:
        missing_str = ", ".join(sorted(str(p) for p in missing))
        msg = f"scan paths do not exist: {missing_str}"
        raise ValueError(msg)

    start = perf_counter()
    resolved = [p.resolve() for p in paths]
    common = find_common_ancestor(resolved)
    if common.is_file():
        # For single-file scans the common ancestor resolves to the file path
        # itself. Normalise to the containing directory so relative paths and
        # directory traversal operate on a directory base.
        common = common.parent

    excl_tree = list(cfg.get(CONFIG_EXCLUDE_TREE, []))
    excl_print = list(cfg.get(CONFIG_EXCLUDE_PRINT, []))
    # Compile gitignore-style specs once per run
    tree_spec = PathSpec.from_lines("gitwildmatch", excl_tree)
    print_spec = PathSpec.from_lines("gitwildmatch", excl_print)

    logger.info(
        "scan_start",
        extra={
            "event": "scan_start",
            "paths": len(resolved),
            "exclude_tree": len(excl_tree),
            "exclude_print": len(excl_print),
        },
    )

    builder = DirectoryTreeBuilder(base_path=common, exclude_patterns=excl_tree)
    deps = ScanDependencies.default() if dependencies is None else dependencies
    registry = FileHandlerRegistry.default() if handlers is None else handlers
    context = FileProcessingContext(
        builder=builder,
        common=common,
        print_spec=print_spec,
        dependencies=deps,
    )

    def collect(item: Path, prefix: str, *, is_last: bool) -> None:
        if item.is_dir():
            builder.add_directory(item, prefix, is_last=is_last)
            return

        # file
        builder.add_file_to_tree(item, prefix, is_last=is_last)
        registry.handle(path=item, context=context)

    try:
        # Pass a 4-tuple so traverse_dir can reuse the compiled spec
        traverse_dir(common, (resolved, excl_tree, common, tree_spec), collect)
    except KeyboardInterrupt as _:
        logger.warning("scan interrupted by user (duration=%.3fs)", perf_counter() - start)
        # Surface the partial state so the CLI can print proper diagnostics.
        raise ScanInterrupted(builder, common) from _

    duration = perf_counter() - start
    logger.info(
        "scan_complete",
        extra={
            "event": "scan_complete",
            "duration_s": round(duration, 3),
            "files": len(builder.file_tree_entries()),
            "tree_lines": len(builder.tree_output()),
        },
    )

    return ScanResult(
        builder=builder,
        common=common,
    )
