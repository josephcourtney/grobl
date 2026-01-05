"""Layered ignore discovery and matching.

Implements SPEC.md:
  - hierarchical .grobl.toml discovery from repo root down to scanned dirs
  - patterns are interpreted relative to the directory containing the file
  - gitignore semantics including ! negation, evaluated sequentially (last match wins)
  - negation must be able to re-include children even if parent was excluded (handled by traversal)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pathspec import PathSpec

from .config import TOML_CONFIG, load_toml_config
from .constants import CONFIG_EXCLUDE_PRINT, CONFIG_EXCLUDE_TREE

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class IgnoreLayer:
    base_dir: Path
    patterns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompiledPattern:
    negated: bool
    spec: PathSpec


@dataclass(frozen=True, slots=True)
class CompiledLayer:
    base_dir: Path
    patterns: tuple[CompiledPattern, ...]


def _coerce_to_dir(p: Path) -> Path:
    return p.parent if p.is_file() else p


def discover_grobl_toml_files(*, repo_root: Path, scan_paths: Sequence[Path]) -> list[Path]:
    """Return discovered .grobl.toml files ordered from repo root to deepest.

    Only returns config files that are ancestors of at least one scanned directory.
    """
    root = repo_root.resolve()
    targets = [_coerce_to_dir(p.resolve(strict=False)) for p in scan_paths]

    found: set[Path] = set()
    for t in targets:
        if not t.is_relative_to(root):
            # Caller should guard this; keep safe.
            continue
        cur = t
        while True:
            candidate = cur / TOML_CONFIG
            if candidate.exists():
                found.add(candidate.resolve())
            if cur == root:
                break
            cur = cur.parent

    # Order by depth: root-first.
    return sorted(found, key=lambda p: (len(p.parent.relative_to(root).parts), p.as_posix().casefold()))


def _compile_patterns(patterns: Iterable[str]) -> tuple[CompiledPattern, ...]:
    compiled: list[CompiledPattern] = []
    for raw in patterns:
        pat = raw.strip()
        if not pat or pat.startswith("#"):
            continue
        neg = pat.startswith("!")
        core = pat[1:] if neg else pat
        # One-line spec, sequentially evaluated.
        spec = PathSpec.from_lines("gitwildmatch", [core])
        compiled.append(CompiledPattern(negated=neg, spec=spec))
    return tuple(compiled)


def compile_layers(layers: Sequence[IgnoreLayer]) -> tuple[CompiledLayer, ...]:
    return tuple(
        CompiledLayer(base_dir=layer.base_dir, patterns=_compile_patterns(layer.patterns)) for layer in layers
    )


def _to_git_path(rel: Path, *, is_dir: bool) -> str:
    s = rel.as_posix()
    if is_dir and not s.endswith("/"):
        return s + "/"
    return s


@dataclass(frozen=True, slots=True)
class LayeredIgnoreMatcher:
    """Sequential ignore matcher with per-layer bases."""

    tree_layers: tuple[CompiledLayer, ...]
    print_layers: tuple[CompiledLayer, ...]
    tree_has_negations: bool
    print_has_negations: bool

    @staticmethod
    def _matches(layers: tuple[CompiledLayer, ...], abs_path: Path, *, is_dir: bool) -> bool:
        """Return True if excluded after sequential evaluation."""
        excluded = False
        for layer in layers:
            base = layer.base_dir
            try:
                if not abs_path.is_relative_to(base):
                    continue
                rel = abs_path.relative_to(base)
            except OSError:
                continue
            rel_git = _to_git_path(rel, is_dir=is_dir)
            for pat in layer.patterns:
                if pat.spec.match_file(rel_git):
                    excluded = not pat.negated
        return excluded

    def excluded_from_tree(self, abs_path: Path, *, is_dir: bool) -> bool:
        return self._matches(self.tree_layers, abs_path, is_dir=is_dir)

    def excluded_from_print(self, abs_path: Path, *, is_dir: bool) -> bool:
        return self._matches(self.print_layers, abs_path, is_dir=is_dir)


def build_layered_ignores(
    *,
    repo_root: Path,
    scan_paths: Sequence[Path],
    include_defaults: bool,
    include_config: bool,
    runtime_tree_patterns: Sequence[str],
    runtime_print_patterns: Sequence[str],
    default_cfg: dict[str, object],
    explicit_config: Path | None = None,  # NEW
) -> LayeredIgnoreMatcher:
    """Assemble ignores in the spec order.

    1) bundled defaults (optional)
    2) .grobl.toml files from repo root to deepest (optional)
    3) explicit --config file (optional; highest precedence among config layers)
    4) runtime/CLI layer (always present).
    """
    tree_layers: list[IgnoreLayer] = []
    print_layers: list[IgnoreLayer] = []

    if include_defaults:
        tree_layers.append(
            IgnoreLayer(base_dir=repo_root, patterns=tuple(default_cfg.get(CONFIG_EXCLUDE_TREE, [])))  # type: ignore[arg-type]
        )
        print_layers.append(
            IgnoreLayer(base_dir=repo_root, patterns=tuple(default_cfg.get(CONFIG_EXCLUDE_PRINT, [])))  # type: ignore[arg-type]
        )

    discovered: set[Path] = set()
    if include_config:
        for cfg_path in discover_grobl_toml_files(repo_root=repo_root, scan_paths=scan_paths):
            real = cfg_path.resolve()
            discovered.add(real)
            data = load_toml_config(real)
            base = real.parent
            tree_layers.append(IgnoreLayer(base_dir=base, patterns=tuple(data.get(CONFIG_EXCLUDE_TREE, []))))  # type: ignore[arg-type]
            print_layers.append(
                IgnoreLayer(base_dir=base, patterns=tuple(data.get(CONFIG_EXCLUDE_PRINT, [])))
            )  # type: ignore[arg-type]

        if explicit_config is not None:
            real = explicit_config.resolve(strict=False)
            if real.exists() and real not in discovered:
                data = load_toml_config(real)
                base = real.parent
                tree_layers.append(
                    IgnoreLayer(base_dir=base, patterns=tuple(data.get(CONFIG_EXCLUDE_TREE, [])))
                )  # type: ignore[arg-type]
                print_layers.append(
                    IgnoreLayer(base_dir=base, patterns=tuple(data.get(CONFIG_EXCLUDE_PRINT, [])))
                )  # type: ignore[arg-type]

    # CLI runtime layer: base at repo_root for deterministic interpretation.
    tree_layers.append(IgnoreLayer(base_dir=repo_root, patterns=tuple(runtime_tree_patterns)))
    print_layers.append(IgnoreLayer(base_dir=repo_root, patterns=tuple(runtime_print_patterns)))

    compiled_tree = compile_layers(tree_layers)
    compiled_print = compile_layers(print_layers)

    tree_has_negations = any(p.negated for layer in compiled_tree for p in layer.patterns)
    print_has_negations = any(p.negated for layer in compiled_print for p in layer.patterns)

    return LayeredIgnoreMatcher(
        tree_layers=compiled_tree,
        print_layers=compiled_print,
        tree_has_negations=tree_has_negations,
        print_has_negations=print_has_negations,
    )
