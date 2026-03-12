"""Runtime scan/explain orchestration helpers shared by CLI wrappers."""

from __future__ import annotations

import os
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import click

from grobl.constants import IgnorePolicy
from grobl.ignore import LayeredIgnoreMatcher, build_layered_ignores
from grobl.utils import resolve_repo_root

from .config_defaults import load_default_config
from .config_runtime import apply_runtime_ignore_edits

if TYPE_CHECKING:
    from grobl.app.command_support import ScanParams


@dataclass(frozen=True, slots=True)
class IgnoreCLIArgs:
    exclude: tuple[str, ...]
    include: tuple[str, ...]
    exclude_file: tuple[Path, ...]
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
        include: tuple[str, ...],
        exclude_file: tuple[Path, ...],
        include_file: tuple[Path, ...],
        exclude_tree: tuple[str, ...],
        include_tree: tuple[str, ...],
        exclude_content: tuple[str, ...],
        include_content: tuple[str, ...],
    ) -> IgnoreCLIArgs:
        return cls(
            exclude=exclude,
            include=include,
            exclude_file=exclude_file,
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


def gather_runtime_ignore_patterns(
    *,
    repo_root: Path,
    ignore_args: IgnoreCLIArgs,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    file_excludes = tuple(
        _path_to_runtime_pattern(path, repo_root=repo_root) for path in ignore_args.exclude_file
    )
    file_includes = tuple(
        _path_to_runtime_pattern(path, repo_root=repo_root) for path in ignore_args.include_file
    )
    runtime_exclude = (*ignore_args.exclude, *file_excludes)
    runtime_include = (*ignore_args.include, *file_includes)
    return (
        runtime_exclude,
        runtime_include,
        ignore_args.exclude_tree,
        ignore_args.include_tree,
        ignore_args.exclude_content,
        ignore_args.include_content,
    )


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
    ignore_defaults_flag: bool,
    no_ignore_config_flag: bool,
    no_ignore_flag: bool,
    runtime_exclude: tuple[str, ...] = (),
    runtime_include: tuple[str, ...] = (),
    runtime_exclude_tree: tuple[str, ...] = (),
    runtime_include_tree: tuple[str, ...] = (),
    runtime_exclude_content: tuple[str, ...] = (),
    runtime_include_content: tuple[str, ...] = (),
) -> LayeredIgnoreMatcher:
    default_cfg = load_default_config()
    cli_ignore_used = bool(
        runtime_exclude
        or runtime_include
        or runtime_exclude_tree
        or runtime_include_tree
        or runtime_exclude_content
        or runtime_include_content
    )
    ignore_policy_value = IgnorePolicy(ignore_policy)
    if ignore_policy_value is IgnorePolicy.NONE and cli_ignore_used:
        msg = (
            "--ignore-policy none (or --no-ignore) disables all ignore rules, "
            "so CLI ignore flags may not be used.\n"
            "Either remove CLI ignore flags, or use --ignore-policy auto|all|cli."
        )
        raise click.UsageError(msg)

    runtime_edits = apply_runtime_ignore_edits(
        base_tree=[],
        base_print=[],
        add_ignore=(),
        remove_ignore=(),
        add_ignore_files=(),
        unignore=(),
        no_ignore=False,
        exclude=runtime_exclude,
        include=runtime_include,
        exclude_tree=runtime_exclude_tree,
        include_tree=runtime_include_tree,
        exclude_content=runtime_exclude_content,
        include_content=runtime_include_content,
    )

    include_defaults, include_config = _ignore_source_flags(
        ignore_policy=ignore_policy_value,
        ignore_defaults_flag=ignore_defaults_flag,
        no_ignore_config_flag=no_ignore_config_flag,
        no_ignore_flag=no_ignore_flag,
    )
    return build_layered_ignores(
        repo_root=repo_root,
        scan_paths=scan_paths,
        include_defaults=include_defaults,
        include_config=include_config,
        runtime_tree_patterns=runtime_edits.tree_patterns,
        runtime_print_patterns=runtime_edits.print_patterns,
        default_cfg=default_cfg,
        explicit_config=params.config_path,
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
    ignore_defaults_flag: bool,
    no_ignore_config_flag: bool,
    no_ignore_flag: bool,
) -> tuple[bool, bool]:
    include_defaults = False
    include_config = False
    if no_ignore_flag:
        return include_defaults, include_config
    if ignore_policy is IgnorePolicy.AUTO:
        include_defaults = not ignore_defaults_flag
        include_config = not no_ignore_config_flag
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
    return include_defaults, include_config
