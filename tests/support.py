"""Helper utilities shared by tests that need layered ignore matchers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grobl.config import load_default_config
from grobl.ignore import LayeredIgnoreMatcher, build_layered_ignores

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path


def build_ignore_matcher(
    *,
    repo_root: Path,
    scan_paths: Sequence[Path],
    tree_patterns: Iterable[str] = (),
    print_patterns: Iterable[str] = (),
    include_defaults: bool = False,
    include_config: bool = False,
) -> LayeredIgnoreMatcher:
    """Return a matcher that mirrors the CLI's layered ignore assembly."""
    default_cfg = load_default_config()
    return build_layered_ignores(
        repo_root=repo_root,
        scan_paths=scan_paths,
        include_defaults=include_defaults,
        include_config=include_config,
        runtime_tree_patterns=tuple(tree_patterns),
        runtime_print_patterns=tuple(print_patterns),
        default_cfg=default_cfg,
    )
