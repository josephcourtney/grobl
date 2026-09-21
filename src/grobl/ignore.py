"""Layered inclusion-policy discovery and matching.

The policy is a single three-state decision per path:

    OMIT < TREE_ONLY < FULL

Rules are layered from defaults through discovered configuration, explicit
configuration, and finally CLI runtime overrides. Within each layer the last
matching rule wins. Legacy tree/content ignore inputs are translated into the
same state model at the boundary.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from pathspec import PathSpec

from .config_defaults import TOML_CONFIG
from .config_loading import load_toml_config
from .constants import (
    CONFIG_EXCLUDE,
    CONFIG_EXCLUDE_CONTENT,
    CONFIG_EXCLUDE_PRINT,
    CONFIG_EXCLUDE_TREE,
    CONFIG_INCLUDE,
    CONFIG_TREE_ONLY,
    InclusionLevel,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class LayerSource(StrEnum):
    DEFAULTS = "defaults"
    CONFIG = "config"
    EXPLICIT_CONFIG = "explicit_config"
    CLI_RUNTIME = "cli_runtime"


@dataclass(frozen=True, slots=True)
class RuleSpec:
    pattern: str
    level: InclusionLevel
    reinclude: bool = False


@dataclass(frozen=True, slots=True)
class InclusionLayer:
    base_dir: Path
    rules: tuple[RuleSpec, ...]
    source: LayerSource
    config_path: Path | None = None


@dataclass(frozen=True, slots=True)
class CompiledRule:
    raw: str
    core: str
    level: InclusionLevel
    negated: bool
    reinclude: bool
    spec: PathSpec


@dataclass(frozen=True, slots=True)
class CompiledLayer:
    base_dir: Path
    source: LayerSource
    config_path: Path | None
    rules: tuple[CompiledRule, ...]


@dataclass(frozen=True, slots=True)
class InclusionReason:
    raw: str
    core: str
    level: InclusionLevel
    negated: bool
    base_dir: Path
    source: LayerSource
    config_path: Path | None


@dataclass(frozen=True, slots=True)
class InclusionDecision:
    level: InclusionLevel
    reason: InclusionReason | None

    @property
    def in_tree(self) -> bool:
        return self.level is not InclusionLevel.OMIT

    @property
    def include_content(self) -> bool:
        return self.level is InclusionLevel.FULL


@dataclass(frozen=True, slots=True)
class MatchDecision:
    """Compatibility view of an inclusion decision for one old scope."""

    excluded: bool
    reason: InclusionReason | None


def _coerce_to_dir(p: Path) -> Path:
    return p.parent if p.is_file() else p


def _extract_patterns(source: dict[str, object], key: str) -> tuple[str, ...]:
    value = source.get(key)
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, str):
        return tuple(str(item) for item in value)
    return ()


def _specs(patterns: Iterable[str], level: InclusionLevel, *, reinclude: bool = False) -> list[RuleSpec]:
    return [RuleSpec(pattern=str(pattern), level=level, reinclude=reinclude) for pattern in patterns]


def _canonical_rules(source: dict[str, object]) -> tuple[RuleSpec, ...]:
    """Compile canonical config lists into one state-setting rule stream.

    The shorthand lists have deterministic within-layer precedence:
    exclude < tree_only < include. For non-overlapping patterns this ordering is
    irrelevant; when the same path matches several lists, the more explicit
    inclusion state wins.
    """
    rules: list[RuleSpec] = []
    rules.extend(_specs(_extract_patterns(source, CONFIG_EXCLUDE), InclusionLevel.OMIT))
    rules.extend(_specs(_extract_patterns(source, CONFIG_TREE_ONLY), InclusionLevel.TREE_ONLY))
    rules.extend(
        _specs(
            _extract_patterns(source, CONFIG_INCLUDE),
            InclusionLevel.FULL,
            reinclude=True,
        )
    )
    return tuple(rules)


def _legacy_rules(source: dict[str, object]) -> tuple[RuleSpec, ...]:
    """Translate the old independent tree/content lists into one state model."""
    rules: list[RuleSpec] = []
    content_key = (
        CONFIG_EXCLUDE_CONTENT if CONFIG_EXCLUDE_CONTENT in source else CONFIG_EXCLUDE_PRINT
    )
    # Content-only suppression is the less restrictive state, so apply it before
    # tree omission. A path present in both legacy lists remains fully omitted.
    rules.extend(_specs(_extract_patterns(source, content_key), InclusionLevel.TREE_ONLY))
    rules.extend(_specs(_extract_patterns(source, CONFIG_EXCLUDE_TREE), InclusionLevel.OMIT))
    return tuple(rules)


def _rules_from_config(source: dict[str, object]) -> tuple[RuleSpec, ...]:
    if any(key in source for key in (CONFIG_EXCLUDE, CONFIG_TREE_ONLY, CONFIG_INCLUDE)):
        return _canonical_rules(source)
    return _legacy_rules(source)


def discover_grobl_toml_files(*, repo_root: Path, scan_paths: Sequence[Path]) -> list[Path]:
    """Return discovered .grobl.toml files ordered from repo root to deepest."""
    root = repo_root.resolve()
    targets = [_coerce_to_dir(p.resolve(strict=False)) for p in scan_paths]

    found: set[Path] = set()
    for target in targets:
        if not target.is_relative_to(root):
            continue
        cur = target
        while True:
            candidate = cur / TOML_CONFIG
            if candidate.exists():
                found.add(candidate.resolve())
            if cur == root:
                break
            cur = cur.parent

    return sorted(
        found,
        key=lambda p: (len(p.parent.relative_to(root).parts), p.as_posix().casefold()),
    )


def _compile_rules(rules: Iterable[RuleSpec]) -> tuple[CompiledRule, ...]:
    compiled: list[CompiledRule] = []
    for rule in rules:
        raw = rule.pattern.strip()
        if not raw or raw.startswith("#"):
            continue
        negated = raw.startswith("!")
        core = raw[1:] if negated else raw
        level = InclusionLevel.FULL if negated else rule.level
        spec = PathSpec.from_lines("gitignore", [core])
        compiled.append(
            CompiledRule(
                raw=raw,
                core=core,
                level=level,
                negated=negated,
                reinclude=rule.reinclude or negated,
                spec=spec,
            )
        )
    return tuple(compiled)


def compile_layers(layers: Sequence[InclusionLayer]) -> tuple[CompiledLayer, ...]:
    return tuple(
        CompiledLayer(
            base_dir=layer.base_dir,
            source=layer.source,
            config_path=layer.config_path,
            rules=_compile_rules(layer.rules),
        )
        for layer in layers
    )


def _to_git_path(rel: Path, *, is_dir: bool) -> str:
    text = rel.as_posix()
    if is_dir and not text.endswith("/"):
        return text + "/"
    return text


@dataclass(frozen=True, slots=True)
class LayeredIgnoreMatcher:
    """Sequential matcher returning one effective inclusion state per path."""

    layers: tuple[CompiledLayer, ...]
    has_reinclusions: bool

    @staticmethod
    def _decide(
        layers: tuple[CompiledLayer, ...],
        abs_path: Path,
        *,
        is_dir: bool,
    ) -> InclusionDecision:
        level = InclusionLevel.FULL
        reason: InclusionReason | None = None
        for layer in layers:
            try:
                if not abs_path.is_relative_to(layer.base_dir):
                    continue
                rel = abs_path.relative_to(layer.base_dir)
            except OSError:
                continue
            rel_git = _to_git_path(rel, is_dir=is_dir)
            for rule in layer.rules:
                if rule.spec.match_file(rel_git):
                    level = rule.level
                    reason = InclusionReason(
                        raw=rule.raw,
                        core=rule.core,
                        level=rule.level,
                        negated=rule.negated,
                        base_dir=layer.base_dir,
                        source=layer.source,
                        config_path=layer.config_path,
                    )
        return InclusionDecision(level=level, reason=reason)

    def explain_inclusion(self, abs_path: Path, *, is_dir: bool) -> InclusionDecision:
        return self._decide(self.layers, abs_path, is_dir=is_dir)

    def inclusion_level(self, abs_path: Path, *, is_dir: bool) -> InclusionLevel:
        return self.explain_inclusion(abs_path, is_dir=is_dir).level

    # Compatibility views used by older internal/test consumers. They are
    # projections of the single inclusion decision, not independent matchers.
    def explain_tree(self, abs_path: Path, *, is_dir: bool) -> MatchDecision:
        decision = self.explain_inclusion(abs_path, is_dir=is_dir)
        reason = decision.reason if decision.level is not InclusionLevel.TREE_ONLY else None
        return MatchDecision(
            excluded=decision.level is InclusionLevel.OMIT,
            reason=reason,
        )

    def explain_content(self, abs_path: Path, *, is_dir: bool) -> MatchDecision:
        decision = self.explain_inclusion(abs_path, is_dir=is_dir)
        return MatchDecision(
            excluded=decision.level is not InclusionLevel.FULL,
            reason=decision.reason,
        )

    def excluded_from_tree(self, abs_path: Path, *, is_dir: bool) -> bool:
        return self.inclusion_level(abs_path, is_dir=is_dir) is InclusionLevel.OMIT

    def excluded_from_print(self, abs_path: Path, *, is_dir: bool) -> bool:
        return self.inclusion_level(abs_path, is_dir=is_dir) is not InclusionLevel.FULL

    @property
    def tree_has_negations(self) -> bool:
        return self.has_reinclusions

    @property
    def print_has_negations(self) -> bool:
        return self.has_reinclusions


def _legacy_runtime_specs(
    *,
    tree_patterns: Sequence[str],
    print_patterns: Sequence[str],
) -> tuple[RuleSpec, ...]:
    specs: list[RuleSpec] = []
    specs.extend(_specs(print_patterns, InclusionLevel.TREE_ONLY))
    specs.extend(_specs(tree_patterns, InclusionLevel.OMIT))
    return tuple(specs)


def build_layered_ignores(
    *,
    repo_root: Path,
    scan_paths: Sequence[Path],
    include_defaults: bool,
    include_config: bool,
    default_cfg: dict[str, object],
    runtime_exclude: Sequence[str] = (),
    runtime_tree_only: Sequence[str] = (),
    runtime_include: Sequence[str] = (),
    runtime_tree_patterns: Sequence[str] = (),
    runtime_print_patterns: Sequence[str] = (),
    explicit_config: Path | None = None,
) -> LayeredIgnoreMatcher:
    """Assemble inclusion rules in precedence order.

    1) bundled defaults
    2) discovered .grobl.toml files, root to deepest
    3) explicit --config
    4) runtime/CLI rules
    """
    layers: list[InclusionLayer] = []

    if include_defaults:
        layers.append(
            InclusionLayer(
                base_dir=repo_root,
                rules=_rules_from_config(default_cfg),
                source=LayerSource.DEFAULTS,
            )
        )

    discovered: set[Path] = set()
    if include_config:
        for cfg_path in discover_grobl_toml_files(repo_root=repo_root, scan_paths=scan_paths):
            real = cfg_path.resolve()
            discovered.add(real)
            layers.append(
                InclusionLayer(
                    base_dir=real.parent,
                    rules=_rules_from_config(load_toml_config(real)),
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
                        rules=_rules_from_config(load_toml_config(real)),
                        source=LayerSource.EXPLICIT_CONFIG,
                        config_path=real,
                    )
                )

    runtime_rules: list[RuleSpec] = list(
        _legacy_runtime_specs(
            tree_patterns=runtime_tree_patterns,
            print_patterns=runtime_print_patterns,
        )
    )
    runtime_rules.extend(_specs(runtime_exclude, InclusionLevel.OMIT))
    runtime_rules.extend(_specs(runtime_tree_only, InclusionLevel.TREE_ONLY))
    runtime_rules.extend(_specs(runtime_include, InclusionLevel.FULL, reinclude=True))
    layers.append(
        InclusionLayer(
            base_dir=repo_root,
            rules=tuple(runtime_rules),
            source=LayerSource.CLI_RUNTIME,
        )
    )

    compiled = compile_layers(layers)
    has_reinclusions = any(rule.reinclude for layer in compiled for rule in layer.rules)
    return LayeredIgnoreMatcher(layers=compiled, has_reinclusions=has_reinclusions)


# Legacy name retained for type imports in downstream code.
ExclusionReason = InclusionReason
