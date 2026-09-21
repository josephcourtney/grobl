"""Runtime inclusion-policy editing helpers."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class RuntimeInclusionEdits:
    """Canonical runtime edits for the three-state inclusion policy."""

    exclude_patterns: list[str]
    tree_only_patterns: list[str]
    include_patterns: list[str]


def apply_runtime_inclusion_edits(
    *,
    exclude: tuple[str, ...] = (),
    tree_only: tuple[str, ...] = (),
    include: tuple[str, ...] = (),
    exclude_files: tuple[Path, ...] = (),
    tree_only_files: tuple[Path, ...] = (),
    include_files: tuple[Path, ...] = (),
    no_ignore: bool = False,
) -> RuntimeInclusionEdits:
    """Normalize runtime CLI edits into the canonical three-state lists."""
    if no_ignore:
        return RuntimeInclusionEdits([], [], [])

    return RuntimeInclusionEdits(
        exclude_patterns=_with_file_patterns(exclude, exclude_files),
        tree_only_patterns=_with_file_patterns(tree_only, tree_only_files),
        include_patterns=_with_file_patterns(include, include_files),
    )


def _with_file_patterns(values: tuple[str, ...], files: tuple[Path, ...]) -> list[str]:
    result: list[str] = []
    _append_unique(result, values)
    _append_unique(result, tuple(str(path) for path in files))
    return result


# ---------------------------------------------------------------------------
# Legacy two-scope compatibility API.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeIgnoreEdits:
    """Compatibility representation of the former two-scope runtime model."""

    tree_patterns: list[str]
    print_patterns: list[str]


def apply_runtime_ignore_edits(
    *,
    base_tree: list[str],
    base_print: list[str],
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
    add_ignore_files: tuple[Path, ...] = (),
    unignore: tuple[str, ...] = (),
    no_ignore: bool = False,
    exclude: tuple[str, ...] = (),
    include: tuple[str, ...] = (),
    exclude_tree: tuple[str, ...] = (),
    include_tree: tuple[str, ...] = (),
    exclude_content: tuple[str, ...] = (),
    include_content: tuple[str, ...] = (),
) -> RuntimeIgnoreEdits:
    """Translate legacy runtime edits while preserving their observable behavior."""
    tree = list(base_tree)
    if no_ignore:
        return RuntimeIgnoreEdits(tree_patterns=[], print_patterns=[])

    _append_ignore_file_patterns(tree, add_ignore_files)
    _append_unique(tree, add_ignore)

    print_patterns = list(base_print)

    for pattern in exclude:
        _append_unique(tree, (pattern,))
        _append_unique(print_patterns, (pattern,))
    _append_unique(tree, exclude_tree)
    _append_unique(print_patterns, exclude_content)

    _remove_patterns(tree, remove_ignore)
    _append_unignore_patterns(tree, unignore)
    _append_unignore_patterns(tree, include)
    _append_unignore_patterns(tree, include_tree)
    _append_unignore_patterns(print_patterns, include)
    _append_unignore_patterns(print_patterns, include_content)

    return RuntimeIgnoreEdits(tree_patterns=tree, print_patterns=print_patterns)


def _append_unique(patterns: list[str], values: tuple[str, ...]) -> None:
    for value in values:
        if value not in patterns:
            patterns.append(value)


def _append_ignore_file_patterns(patterns: list[str], add_ignore_files: tuple[Path, ...]) -> None:
    for path in add_ignore_files:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        cleaned = [line.strip() for line in lines]
        values = tuple(line for line in cleaned if line and not line.startswith("#"))
        _append_unique(patterns, values)


def _remove_patterns(patterns: list[str], removals: tuple[str, ...]) -> None:
    for value in removals:
        if value in patterns:
            patterns.remove(value)
        else:
            print(f"warning: ignore pattern not found: {value}", file=sys.stderr)


def _append_unignore_patterns(patterns: list[str], values: tuple[str, ...]) -> None:
    for value in values:
        negated = value if value.startswith("!") else f"!{value}"
        if negated not in patterns:
            patterns.append(negated)
