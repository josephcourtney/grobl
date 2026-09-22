"""Runtime scan/explain orchestration helpers shared by CLI wrappers."""

from __future__ import annotations

import os
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import click

from grobl.config_defaults import load_default_config
from grobl.config_loading import discover_grobl_toml_files, load_toml_config
from grobl.constants import IgnorePolicy
from grobl.ignore import (
    InclusionLayer,
    LayeredIgnoreMatcher,
    LayerSource,
    build_layered_ignores,
    rules_from_config,
)
from grobl.utils import resolve_repo_root

if TYPE_CHECKING:
    from grobl.app.command_support import ScanParams


@dataclass(frozen=True, slots=True)
class IgnoreCLIArgs:
    exclude: tuple[str, ...]
    tree_only: tuple[str, ...]
    include: tuple[str, ...]
    exclude_file: tuple[Path, ...]
    tree_only_file: tuple[Path, ...]
    include_file: tuple[Path, ...]
    exclude_tree: tuple[str, ...]
    include_tree: tuple[str, ...]
    exclude_content: tuple[str, ...]
    include_content: tuple[str, ...]

    @classmethod
    def from_values(
        cls,
        *,
        exclude: tuple[str, ...],
        tree_only: tuple[str, ...],
        include: tuple[str, ...],
        exclude_file: tuple[Path, ...],
        tree_only_file: tuple[Path, ...],
        include_file: tuple[Path, ...],
        exclude_tree: tuple[str, ...],
        include_tree: tuple[str, ...],
        exclude_content: tuple[str, ...],
        include_content: tuple[str, ...],
    ) -> IgnoreCLIArgs:
        return cls(
            exclude=exclude,
            tree_only=tree_only,
            include=include,
            exclude_file=exclude_file,
            tree_only_file=tree_only_file,
            include_file=include_file,
            exclude_tree=exclude_tree,
            include_tree=include_tree,
            exclude_content=exclude_content,
            include_content=include_content,
        )


def expand_path_token(path: Path) -> Path:
    expanded = os.path.expandvars(str(path))
    with suppress(RuntimeError):
        expanded = Path(expanded).expanduser()
    return Path(expanded)


def resolve_runtime_paths(paths: tuple[Path, ...]) -> tuple[tuple[Path, ...], Path]:
    requested_paths = tuple(expand_path_token(path) for path in paths) if paths else (Path(),)
    return requested_paths, resolve_repo_root(cwd=Path(), paths=requested_paths)


def _load_config_layers(
    *,
    repo_root: Path,
    scan_paths: tuple[Path, ...],
    explicit_config: Path | None,
) -> tuple[InclusionLayer, ...]:
    layers: list[InclusionLayer] = []
    discovered: set[Path] = set()

    for config_path in discover_grobl_toml_files(
        repo_root=repo_root,
        scan_paths=scan_paths,
    ):
        real = config_path.resolve()
        discovered.add(real)
        layers.append(
            InclusionLayer(
                base_dir=real.parent,
                rules=rules_from_config(load_toml_config(real)),
                source=LayerSource.CONFIG,
                config_path=real,
            )
        )

    if explicit_config is not None:
        real = explicit_config.resolve(strict=False)
        if real.exists() and real not in discovered:
            layers.append(
                InclusionLayer(
                    base_dir=real.parent,
                    rules=rules_from_config(load_toml_config(real)),
                    source=LayerSource.EXPLICIT_CONFIG,
                    config_path=real,
                )
            )

    return tuple(layers)


def gather_runtime_ignore_patterns(
    *,
    repo_root: Path,
    ignore_args: IgnoreCLIArgs,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Return CLI rules projected onto omit, tree_only, and full states."""
    file_excludes = tuple(
        _path_to_runtime_pattern(path, repo_root=repo_root) for path in ignore_args.exclude_file
    )
    file_tree_only = tuple(
        _path_to_runtime_pattern(path, repo_root=repo_root) for path in ignore_args.tree_only_file
    )
    file_includes = tuple(
        _path_to_runtime_pattern(path, repo_root=repo_root) for path in ignore_args.include_file
    )

    runtime_exclude = (
        *ignore_args.exclude_tree,
        *ignore_args.exclude,
        *file_excludes,
    )
    runtime_tree_only = (
        *ignore_args.exclude_content,
        *ignore_args.tree_only,
        *file_tree_only,
    )
    runtime_include = (
        *ignore_args.include,
        *file_includes,
        *ignore_args.include_tree,
        *ignore_args.include_content,
    )
    return runtime_exclude, runtime_tree_only, runtime_include


def ensure_paths_within_repo(
    *,
    repo_root: Path,
    requested_paths: tuple[Path, ...],
    ctx: click.Context,
) -> None:
    msg = "scan paths must be within the resolved repository root"
    try:
        resolved_targets = [path.resolve(strict=False) for path in requested_paths]
        if not all(target.is_relative_to(repo_root) for target in resolved_targets):
            details = "\n".join(f"  - {target}" for target in resolved_targets)
            msg = f"{msg}\nrepo_root: {repo_root}\nrequested:\n{details}"
            raise click.UsageError(msg, ctx=ctx)
    except OSError as err:
        raise click.UsageError(msg, ctx=ctx) from err


def assemble_layered_ignores(
    *,
    repo_root: Path,
    scan_paths: tuple[Path, ...],
    params: ScanParams,
    ignore_policy: str,
    inherit_defaults: bool,
    ignore_defaults_flag: bool,
    no_ignore_config_flag: bool,
    no_ignore_flag: bool,
    runtime_exclude: tuple[str, ...] = (),
    runtime_tree_only: tuple[str, ...] = (),
    runtime_include: tuple[str, ...] = (),
) -> LayeredIgnoreMatcher:
    default_cfg = load_default_config()
    cli_policy_used = bool(runtime_exclude or runtime_tree_only or runtime_include)
    ignore_policy_value = IgnorePolicy(ignore_policy)
    if ignore_policy_value is IgnorePolicy.NONE and cli_policy_used:
        msg = (
            "--ignore-policy none (or --no-ignore) disables all inclusion rules, "
            "so CLI inclusion flags may not be used.\n"
            "Either remove those flags, or use --ignore-policy auto|all|cli."
        )
        raise click.UsageError(msg)

    include_defaults, include_config = _ignore_source_flags(
        ignore_policy=ignore_policy_value,
        inherit_defaults=inherit_defaults,
        ignore_defaults_flag=ignore_defaults_flag,
        no_ignore_config_flag=no_ignore_config_flag,
        no_ignore_flag=no_ignore_flag,
    )
    config_layers = (
        _load_config_layers(
            repo_root=repo_root,
            scan_paths=scan_paths,
            explicit_config=params.config_path,
        )
        if include_config
        else ()
    )
    return build_layered_ignores(
        repo_root=repo_root,
        include_defaults=include_defaults,
        runtime_exclude=runtime_exclude,
        runtime_tree_only=runtime_tree_only,
        runtime_include=runtime_include,
        default_cfg=default_cfg,
        config_layers=config_layers,
    )


def _path_to_runtime_pattern(path: Path, *, repo_root: Path) -> str:
    normalized = expand_path_token(path)
    resolved = normalized.resolve(strict=False)
    try:
        rel = resolved.relative_to(repo_root)
    except (ValueError, OSError):
        rel = resolved
    pattern = rel.as_posix()
    if normalized.is_dir() and not pattern.endswith("/"):
        pattern += "/"
    return pattern


def _ignore_source_flags(
    *,
    ignore_policy: IgnorePolicy,
    inherit_defaults: bool,
    ignore_defaults_flag: bool,
    no_ignore_config_flag: bool,
    no_ignore_flag: bool,
) -> tuple[bool, bool]:
    include_defaults = False
    include_config = False
    if no_ignore_flag:
        return include_defaults, include_config
    if ignore_policy is IgnorePolicy.AUTO:
        include_defaults = inherit_defaults
        include_config = True
    elif ignore_policy is IgnorePolicy.ALL:
        include_defaults = True
        include_config = True
    elif ignore_policy is IgnorePolicy.DEFAULTS:
        include_defaults = True
    elif ignore_policy is IgnorePolicy.CONFIG:
        include_config = True
    elif ignore_policy is IgnorePolicy.CLI:
        include_defaults = False
        include_config = False

    if ignore_defaults_flag:
        include_defaults = False
    if no_ignore_config_flag:
        include_config = False
    return include_defaults, include_config
