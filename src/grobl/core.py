"""Core scan orchestration: traverses paths, applies config, and collects data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pathspec import PathSpec

from grobl.binary_probe import probe_binary_details
from grobl.constants import (
    CONFIG_EXCLUDE_PRINT,
    CONFIG_EXCLUDE_TREE,
)
from grobl.directory import DirectoryTreeBuilder, traverse_dir
from grobl.errors import ScanInterrupted
from grobl.utils import find_common_ancestor, is_text, read_text

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class ScanResult:
    builder: DirectoryTreeBuilder
    common: Path


def run_scan(
    paths: list[Path],
    cfg: dict[str, Any],
) -> ScanResult:
    """Traverse the requested paths and collect data only."""
    resolved = [p.resolve() for p in paths]
    common = find_common_ancestor(resolved)

    excl_tree = list(cfg.get(CONFIG_EXCLUDE_TREE, []))
    excl_print = list(cfg.get(CONFIG_EXCLUDE_PRINT, []))
    # Compile gitignore-style specs once per run
    tree_spec = PathSpec.from_lines("gitwildmatch", excl_tree)
    print_spec = PathSpec.from_lines("gitwildmatch", excl_print)

    builder = DirectoryTreeBuilder(base_path=common, exclude_patterns=excl_tree)

    def collect(item: Path, prefix: str, *, is_last: bool) -> None:
        if item.is_dir():
            builder.add_directory(item, prefix, is_last=is_last)
            return

        # file
        builder.add_file_to_tree(item, prefix, is_last=is_last)
        rel = item.relative_to(common)
        if is_text(item):
            content = read_text(item)
            ln, ch = len(content.splitlines()), len(content)
            builder.record_metadata(rel, ln, ch)
            # gitignore semantics for exclude_print
            rel_str = rel.as_posix()
            if not print_spec.match_file(rel_str):
                builder.add_file(item, rel, ln, ch, content)
        else:
            size = item.stat().st_size
            builder.record_metadata(rel, 0, size)
            # Collect additional binary summary details (e.g., image dimensions)
            details = probe_binary_details(item)
            builder.record_binary_details(rel, details)

    try:
        # Pass a 4-tuple so traverse_dir can reuse the compiled spec
        traverse_dir(common, (resolved, excl_tree, common, tree_spec), collect)
    except KeyboardInterrupt as _:
        # Surface the partial state so the CLI can print proper diagnostics.
        raise ScanInterrupted(builder, common) from _

    return ScanResult(
        builder=builder,
        common=common,
    )
