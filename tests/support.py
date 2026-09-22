"""Helper utilities shared by tests that need layered inclusion matchers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grobl.config_defaults import load_default_config
from grobl.ignore import LayeredIgnoreMatcher, build_layered_ignores

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path


def build_ignore_matcher(
    *,
    repo_root: Path,
    scan_paths: Sequence[Path],
    exclude_patterns: Iterable[str] = (),
    tree_only_patterns: Iterable[str] = (),
    include_patterns: Iterable[str] = (),
    tree_patterns: Iterable[str] = (),
    print_patterns: Iterable[str] = (),
    include_defaults: bool = False,
) -> LayeredIgnoreMatcher:
    """Return a matcher mirroring the CLI inclusion assembly.

    tree_patterns and print_patterns remain available for tests that exercise
    compatibility with the former two-scope API.
    """
    default_cfg = load_default_config()
    return build_layered_ignores(
        repo_root=repo_root,
        include_defaults=include_defaults,
        runtime_exclude=tuple(exclude_patterns),
        runtime_tree_only=tuple(tree_only_patterns),
        runtime_include=tuple(include_patterns),
        runtime_tree_patterns=tuple(tree_patterns),
        runtime_print_patterns=tuple(print_patterns),
        default_cfg=default_cfg,
    )
