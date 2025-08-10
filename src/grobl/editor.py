"""Interactive configuration editor."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import tomlkit

from .config import TOML_CONFIG
from .directory import traverse_dir
from .utils import find_common_ancestor


def _build_tree(paths: list[Path], base: Path) -> tuple[list[str], dict[str, Path]]:
    """Return tree lines and an index→relative-path mapping."""
    lines: list[str] = []
    mapping: dict[str, Path] = {}

    def collect(item: Path, prefix: str, is_last: bool) -> None:
        connector = "└── " if is_last else "├── "
        rel = item.relative_to(base)
        lines.append(f"{prefix}{connector}{item.name}")
        mapping[str(len(lines))] = rel

    traverse_dir(base, (paths, [], base), collect)
    lines.insert(0, base.name)
    return lines, mapping


def _prompt_indices(
    prompt: str, *, input_iter: Iterator[str] | None = None
) -> list[str]:
    """Prompt the user and return a list of indices."""
    if input_iter is None:
        response = input(prompt).strip()
    else:
        try:
            response = next(input_iter).strip()
        except StopIteration:
            response = ""
    if not response:
        return []
    return response.split()


def interactive_edit_config(
    paths: list[Path], cfg: dict, *, save: bool, input_iter: Iterator[str] | None = None
) -> dict:
    """Interactively edit configuration.

    Parameters
    ----------
    paths:
        Paths to include in the tree view.
    cfg:
        Existing configuration dictionary to modify.
    save:
        If true, write the updated configuration to ``TOML_CONFIG``.
    input_iter:
        Optional iterator for providing input programmatically (used in tests).
    """

    resolved = [p.resolve() for p in paths]
    base = find_common_ancestor(resolved)
    lines, mapping = _build_tree(resolved, base)

    print("\n".join(lines))

    excl_tree = set(cfg.get("exclude_tree", []))
    tree_indices = _prompt_indices(
        "Enter numbers to toggle exclusion from tree (blank to continue): ",
        input_iter=input_iter,
    )
    for idx in tree_indices:
        rel = mapping.get(idx)
        if rel is None:
            continue
        rel_str = str(rel)
        if rel_str in excl_tree:
            excl_tree.remove(rel_str)
        else:
            excl_tree.add(rel_str)
    cfg["exclude_tree"] = sorted(excl_tree)

    excl_print = set(cfg.get("exclude_print", []))
    print_indices = _prompt_indices(
        "Enter numbers to toggle exclusion from file contents (blank to finish): ",
        input_iter=input_iter,
    )
    for idx in print_indices:
        rel = mapping.get(idx)
        if rel is None:
            continue
        if (base / rel).is_dir():
            continue
        rel_str = str(rel)
        if rel_str in excl_print:
            excl_print.remove(rel_str)
        else:
            excl_print.add(rel_str)
    cfg["exclude_print"] = sorted(excl_print)

    if save:
        toml_path = base / TOML_CONFIG
        toml_path.write_text(tomlkit.dumps(cfg), encoding="utf-8")
        print(f"Saved {TOML_CONFIG}")

    return cfg
