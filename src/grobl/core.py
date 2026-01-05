"""Core scan orchestration: traverses paths, applies config, and collects data."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from grobl.directory import DirectoryTreeBuilder, TraverseConfig, TreeCallback, traverse_dir
from grobl.file_handling import FileHandlerRegistry, FileProcessingContext, ScanDependencies
from grobl.utils import find_common_ancestor

if TYPE_CHECKING:
    from pathlib import Path

    from grobl.ignore import LayeredIgnoreMatcher


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


def _coerce_exclude_patterns(value: object | None) -> list[str]:
    r"""Normalize ``cfg[\"exclude_tree\"]``-like values to a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return []


def run_scan(
    *,
    paths: Iterable[Path],
    cfg: dict[str, object],
    ignores: LayeredIgnoreMatcher,
    repo_root: Path | None = None,
    match_base: Path | None = None,
    handlers: FileHandlerRegistry | None = None,
    dependencies: ScanDependencies | None = None,
) -> ScanResult:
    """
    Run a filesystem scan.

    Corrected invariant:
      - traversal root
      - tree builder base
      - ScanResult.common

    must all agree, otherwise relative paths and rendered output drift.

    We anchor everything at `builder_base`, which is:
      - repo_root (if supplied and contains all scan paths), else
      - the common ancestor of the scan paths.
    """
    resolved_paths = [p.resolve() for p in paths]
    if not resolved_paths:
        msg = "run_scan requires at least one path"
        raise ValueError(msg)

    if any(not p.exists() for p in resolved_paths):
        msg = "scan paths do not exist"
        raise ValueError(msg)

    common = find_common_ancestor(resolved_paths)
    if common.is_file():
        common = common.parent

    builder_base = _determine_builder_base(common, resolved_paths, repo_root)
    match_base = _determine_match_base(match_base, resolved_paths, builder_base)

    builder = DirectoryTreeBuilder(
        base_path=builder_base,
        exclude_patterns=_coerce_exclude_patterns(cfg.get("exclude_tree")),
    )

    context = FileProcessingContext(
        builder=builder,
        common=builder_base,
        ignores=ignores,
        dependencies=ScanDependencies.default() if dependencies is None else dependencies,
    )

    registry = FileHandlerRegistry.default() if handlers is None else handlers
    tree_has_negations = ignores.tree_has_negations

    def collect(path: Path, prefix: str, *, is_last: bool) -> bool:
        is_dir = path.is_dir()
        excluded = ignores.excluded_from_tree(path, is_dir=is_dir)
        if is_dir:
            if not excluded:
                builder.add_directory(path, prefix, is_last=is_last)
            return not excluded or tree_has_negations
        if excluded:
            return False
        builder.add_file_to_tree(path, prefix, is_last=is_last)
        registry.handle(path=path, context=context)
        return False

    traverse_dir(
        builder_base,
        TraverseConfig(
            paths=resolved_paths,
            base=match_base,
            repo_root=repo_root or builder_base,
        ),
        cast("TreeCallback", collect),
    )

    return ScanResult(
        builder=builder,
        common=builder_base,
    )
