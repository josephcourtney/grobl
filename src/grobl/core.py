"""Core scan orchestration: traverses paths, applies config, and collects data."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from grobl.constants import InclusionLevel
from grobl.directory import (
    DirectoryTreeBuilder,
    TraverseConfig,
    TreeCallback,
    inspect_symlink,
    should_follow_symlink,
    traverse_dir,
)
from grobl.errors import PathNotFoundError
from grobl.file_handling import FileHandlerRegistry, FileProcessingContext, ScanDependencies
from grobl.resource_limits import UNLIMITED_RESOURCE_LIMITS, ResourceBudget, ResourceLimits
from grobl.utils import find_common_ancestor

if TYPE_CHECKING:
    from pathlib import Path

    from grobl.ignore import LayeredIgnoreMatcher
    from grobl.timing import TimingRecorder


@dataclass(frozen=True, slots=True)
class ScanResult:
    builder: DirectoryTreeBuilder
    common: Path


def _coerce_to_directory(path: Path) -> Path:
    return path.parent if path.is_file() and not path.is_symlink() else path


def _determine_builder_base(common: Path, paths: list[Path], repo_root: Path | None) -> Path:
    if repo_root is None:
        return common
    candidate = _coerce_to_directory(repo_root.absolute())
    if all(path.is_relative_to(candidate) for path in paths):
        return candidate
    return common


def _determine_match_base(match_base: Path | None, paths: list[Path], default: Path) -> Path:
    if match_base is None:
        return default
    normalized = _coerce_to_directory(match_base.absolute())
    if all(path.is_relative_to(normalized) for path in paths):
        return normalized
    return default


def _coerce_exclude_patterns(value: object | None) -> list[str]:
    """Normalize an exclusion-like config value to a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return []


def _exists_without_dereferencing(path: Path) -> bool:
    try:
        path.lstat()
    except OSError:
        return False
    return True


def run_scan(
    *,
    paths: Iterable[Path],
    cfg: dict[str, object],
    ignores: LayeredIgnoreMatcher,
    repo_root: Path | None = None,
    match_base: Path | None = None,
    handlers: FileHandlerRegistry | None = None,
    dependencies: ScanDependencies | None = None,
    limits: ResourceLimits = UNLIMITED_RESOURCE_LIMITS,
    timing: TimingRecorder | None = None,
) -> ScanResult:
    """Run a filesystem scan under the effective three-state inclusion policy."""
    logical_paths = [path.absolute() for path in paths]
    if not logical_paths:
        msg = "run_scan requires at least one path"
        raise ValueError(msg)

    missing = [path for path in logical_paths if not _exists_without_dereferencing(path)]
    if missing:
        if len(missing) == 1:
            msg = f"scan path not found: {missing[0]}"
        else:
            joined = ", ".join(str(path) for path in missing)
            msg = f"scan paths not found: {joined}"
        raise PathNotFoundError(msg)

    common = find_common_ancestor(logical_paths, resolve_symlinks=False)
    if common.is_symlink() or common.is_file():
        common = common.parent

    builder_base = _determine_builder_base(common, logical_paths, repo_root)
    match_base = _determine_match_base(match_base, logical_paths, builder_base)

    diagnostic_excludes = cfg.get("exclude", cfg.get("exclude_tree"))
    builder = DirectoryTreeBuilder(
        base_path=builder_base,
        exclude_patterns=_coerce_exclude_patterns(diagnostic_excludes),
    )

    context = FileProcessingContext(
        builder=builder,
        common=builder_base,
        ignores=ignores,
        dependencies=ScanDependencies.default() if dependencies is None else dependencies,
        budget=ResourceBudget(limits),
        timing=timing,
    )

    registry = FileHandlerRegistry.default() if handlers is None else handlers
    traversal = TraverseConfig(
        paths=logical_paths,
        base=match_base,
        repo_root=(repo_root or builder_base).absolute(),
        follow_symlinks=bool(cfg.get("_follow_symlinks", cfg.get("follow_symlinks", False))),
        allow_external_symlinks=bool(
            cfg.get("_allow_external_symlinks", cfg.get("allow_external_symlinks", False))
        ),
    )
    followed_file_identities: set[tuple[int, int]] = set()

    def collect(path: Path, prefix: str, *, is_last: bool) -> bool:
        if path.is_symlink():
            info = inspect_symlink(path, root=traversal.repo_root)
            if timing is None:
                decision = ignores.explain_inclusion(path, is_dir=info.target_is_dir)
            else:
                with timing.measure("policy matching", depth=1):
                    decision = ignores.explain_inclusion(path, is_dir=info.target_is_dir)

            can_follow = should_follow_symlink(info, traversal)
            if decision.level is InclusionLevel.OMIT:
                return (
                    can_follow
                    and info.target_is_dir
                    and ignores.may_reinclude_descendant(path)
                )

            builder.add_symlink_to_tree(path, info, prefix, is_last=is_last)
            if not can_follow:
                return False
            if info.target_is_file and decision.level is InclusionLevel.FULL:
                if info.identity is not None and info.identity in followed_file_identities:
                    return False
                if info.identity is not None:
                    followed_file_identities.add(info.identity)
                registry.handle(path=path, context=context)
                return False
            return info.target_is_dir

        is_dir = path.is_dir()
        if timing is None:
            decision = ignores.explain_inclusion(path, is_dir=is_dir)
        else:
            with timing.measure("policy matching", depth=1):
                decision = ignores.explain_inclusion(path, is_dir=is_dir)
        if is_dir:
            if decision.level is not InclusionLevel.OMIT:
                builder.add_directory(path, prefix, is_last=is_last)
                return True
            return ignores.may_reinclude_descendant(path)

        if decision.level is InclusionLevel.OMIT:
            return False
        builder.add_file_to_tree(path, prefix, is_last=is_last)
        registry.handle(path=path, context=context)
        return False

    traverse_dir(builder_base, traversal, cast("TreeCallback", collect))
    return ScanResult(builder=builder, common=builder_base)
