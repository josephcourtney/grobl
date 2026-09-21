"""Layered three-state inclusion policy discovery and matching.

The effective state of every path is one of full, tree_only, or omit.
Rules are applied in layer order and the last matching rule wins.
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
class PolicyRule:
    """A pattern that assigns one inclusion state when it matches."""

    pattern: str
    state: InclusionLevel


@dataclass(frozen=True, slots=True)
class PolicyLayer:
    base_dir: Path
    rules: tuple[PolicyRule, ...]
    source: LayerSource
    config_path: Path | None = None


@dataclass(frozen=True, slots=True)
class CompiledRule:
    raw: str
    core: str
    negated: bool
    state: InclusionLevel
    spec: PathSpec


@dataclass(frozen=True, slots=True)
class CompiledLayer:
    base_dir: Path
    source: LayerSource
    config_path: Path | None
    rules: tuple[CompiledRule, ...]


@dataclass(frozen=True, slots=True)
class ExclusionReason:
    """Provenance for the rule that produced the effective state.

    The historical name is retained because it is part of the explain/summary
    compatibility surface even though a winning rule may now include a path.
    """

    raw: str
    core: str
    negated: bool
    state: InclusionLevel
    base_dir: Path
    source: LayerSource
    config_path: Path | None


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    state: InclusionLevel
    reason: ExclusionReason | None

    @property
    def tree_included(self) -> bool:
        return self.state is not InclusionLevel.OMIT

    @property
    def content_included(self) -> bool:
        return self.state is InclusionLevel.FULL


@dataclass(frozen=True, slots=True)
class MatchDecision:
    """Compatibility projection of a policy decision onto one old scope."""

    excluded: bool
    reason: ExclusionReason | None


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


def _append_rules(
    target: list[PolicyRule],
    patterns: Iterable[str],
    state: InclusionLevel,
) -> None:
    target.extend(PolicyRule(pattern=str(pattern), state=state) for pattern in patterns)


def rules_from_config(source: dict[str, object]) -> tuple[PolicyRule, ...]:
    """Compile canonical and legacy config lists into one ordered rule stream.

    Legacy content rules are evaluated before legacy tree rules so a path that
    appeared in both old exclusion lists remains fully omitted. Canonical keys
    are then applied in increasing information order, with include last.
    """

    rules: list[PolicyRule] = []

    legacy_content_key = (
        CONFIG_EXCLUDE_CONTENT if CONFIG_EXCLUDE_CONTENT in source else CONFIG_EXCLUDE_PRINT
    )
    _append_rules(
        rules,
        _extract_patterns(source, legacy_content_key),
        InclusionLevel.TREE_ONLY,
    )
    _append_rules(
        rules,
        _extract_patterns(source, CONFIG_EXCLUDE_TREE),
        InclusionLevel.OMIT,
    )

    _append_rules(rules, _extract_patterns(source, CONFIG_EXCLUDE), InclusionLevel.OMIT)
    _append_rules(rules, _extract_patterns(source, CONFIG_TREE_ONLY), InclusionLevel.TREE_ONLY)
    _append_rules(rules, _extract_patterns(source, CONFIG_INCLUDE), InclusionLevel.FULL)
    return tuple(rules)


def discover_grobl_toml_files(*, repo_root: Path, scan_paths: Sequence[Path]) -> list[Path]:
    """Return applicable .grobl.toml files from repository root to leaf."""

    root = repo_root.resolve()
    targets = [_coerce_to_dir(p.resolve(strict=False)) for p in scan_paths]

    found: set[Path] = set()
    for target in targets:
        if not target.is_relative_to(root):
            continue
        current = target
        while True:
            candidate = current / TOML_CONFIG
            if candidate.exists():
                found.add(candidate.resolve())
            if current == root:
                break
            current = current.parent

    return sorted(
        found,
        key=lambda p: (len(p.parent.relative_to(root).parts), p.as_posix().casefold()),
    )


def _compile_rules(rules: Iterable[PolicyRule]) -> tuple[CompiledRule, ...]:
    compiled: list[CompiledRule] = []
    for rule in rules:
        raw = rule.pattern.strip()
        if not raw or raw.startswith("#"):
            continue
        negated = raw.startswith("!")
        core = raw[1:] if negated else raw
        state = InclusionLevel.FULL if negated else rule.state
        spec = PathSpec.from_lines("gitignore", [core])
        compiled.append(
            CompiledRule(
                raw=raw,
                core=core,
                negated=negated,
                state=state,
                spec=spec,
            )
        )
    return tuple(compiled)


def compile_layers(layers: Sequence[PolicyLayer]) -> tuple[CompiledLayer, ...]:
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
    value = rel.as_posix()
    if is_dir and not value.endswith("/"):
        return value + "/"
    return value


@dataclass(frozen=True, slots=True)
class LayeredIgnoreMatcher:
    """Sequential three-state matcher with per-layer matching bases."""

    layers: tuple[CompiledLayer, ...]
    has_restore_rules: bool

    @staticmethod
    def _decide(
        layers: tuple[CompiledLayer, ...],
        abs_path: Path,
        *,
        is_dir: bool,
    ) -> PolicyDecision:
        state = InclusionLevel.FULL
        reason: ExclusionReason | None = None

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
                    state = rule.state
                    reason = ExclusionReason(
                        raw=rule.raw,
                        core=rule.core,
                        negated=rule.negated,
                        state=rule.state,
                        base_dir=layer.base_dir,
                        source=layer.source,
                        config_path=layer.config_path,
                    )

        return PolicyDecision(state=state, reason=reason)

    def explain_policy(self, abs_path: Path, *, is_dir: bool) -> PolicyDecision:
        return self._decide(self.layers, abs_path, is_dir=is_dir)

    def explain_tree(self, abs_path: Path, *, is_dir: bool) -> MatchDecision:
        decision = self.explain_policy(abs_path, is_dir=is_dir)
        return MatchDecision(excluded=not decision.tree_included, reason=decision.reason)

    def explain_content(self, abs_path: Path, *, is_dir: bool) -> MatchDecision:
        decision = self.explain_policy(abs_path, is_dir=is_dir)
        return MatchDecision(excluded=not decision.content_included, reason=decision.reason)

    def excluded_from_tree(self, abs_path: Path, *, is_dir: bool) -> bool:
        return not self.explain_policy(abs_path, is_dir=is_dir).tree_included

    def excluded_from_print(self, abs_path: Path, *, is_dir: bool) -> bool:
        return not self.explain_policy(abs_path, is_dir=is_dir).content_included

    @property
    def tree_has_negations(self) -> bool:
        """Compatibility alias used by older traversal callers."""

        return self.has_restore_rules

    @property
    def print_has_negations(self) -> bool:
        """Compatibility alias retained for external callers."""

        return self.has_restore_rules


def _layer(
    *,
    base_dir: Path,
    source: LayerSource,
    data: dict[str, object],
    config_path: Path | None = None,
) -> PolicyLayer:
    return PolicyLayer(
        base_dir=base_dir,
        rules=rules_from_config(data),
        source=source,
        config_path=config_path,
    )


def _legacy_runtime_rules(
    *,
    tree_patterns: Sequence[str],
    print_patterns: Sequence[str],
) -> tuple[PolicyRule, ...]:
    rules: list[PolicyRule] = []
    _append_rules(rules, print_patterns, InclusionLevel.TREE_ONLY)
    _append_rules(rules, tree_patterns, InclusionLevel.OMIT)
    return tuple(rules)


def build_layered_ignores(
    *,
    repo_root: Path,
    scan_paths: Sequence[Path],
    include_defaults: bool,
    include_config: bool,
    default_cfg: dict[str, object],
    runtime_rules: Sequence[PolicyRule] = (),
    explicit_config: Path | None = None,
    runtime_tree_patterns: Sequence[str] = (),
    runtime_print_patterns: Sequence[str] = (),
) -> LayeredIgnoreMatcher:
    """Assemble policy layers in defaults -> config -> explicit -> CLI order."""

    layers: list[PolicyLayer] = []

    if include_defaults:
        layers.append(
            _layer(
                base_dir=repo_root,
                source=LayerSource.DEFAULTS,
                data=default_cfg,
            )
        )

    discovered: set[Path] = set()
    if include_config:
        for cfg_path in discover_grobl_toml_files(repo_root=repo_root, scan_paths=scan_paths):
            real = cfg_path.resolve()
            discovered.add(real)
            layers.append(
                _layer(
                    base_dir=real.parent,
                    source=LayerSource.CONFIG,
                    data=load_toml_config(real),
                    config_path=real,
                )
            )

        if explicit_config is not None:
            real = explicit_config.resolve(strict=False)
            if real.exists() and real not in discovered:
                layers.append(
                    _layer(
                        base_dir=real.parent,
                        source=LayerSource.EXPLICIT_CONFIG,
                        data=load_toml_config(real),
                        config_path=real,
                    )
                )

    legacy_rules = _legacy_runtime_rules(
        tree_patterns=runtime_tree_patterns,
        print_patterns=runtime_print_patterns,
    )
    layers.append(
        PolicyLayer(
            base_dir=repo_root,
            rules=(*legacy_rules, *tuple(runtime_rules)),
            source=LayerSource.CLI_RUNTIME,
        )
    )

    compiled = compile_layers(layers)
    has_restore_rules = any(
        rule.state is InclusionLevel.FULL for layer in compiled for rule in layer.rules
    )
    return LayeredIgnoreMatcher(
        layers=compiled,
        has_restore_rules=has_restore_rules,
    )
