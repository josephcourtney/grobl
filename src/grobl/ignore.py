"""Layered three-state inclusion policy matching.

Every path resolves to exactly one level: full, tree_only, or omit.
Rules are evaluated sequentially across layers and the last matching rule wins.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pathspec import PathSpec

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


class LayerSource(StrEnum):
    DEFAULTS = "defaults"
    CONFIG = "config"
    EXPLICIT_CONFIG = "explicit_config"
    CLI_RUNTIME = "cli_runtime"


@dataclass(frozen=True, slots=True)
class InclusionRule:
    """A gitignore-style pattern that assigns an inclusion level."""

    pattern: str
    level: InclusionLevel


# Compatibility name used by the application runtime while the public model is
# described in terms of inclusion.
PolicyRule = InclusionRule


@dataclass(frozen=True, slots=True)
class InclusionLayer:
    base_dir: Path
    rules: tuple[InclusionRule, ...]
    source: LayerSource
    config_path: Path | None = None


@dataclass(frozen=True, slots=True)
class CompiledRule:
    raw: str
    core: str
    negated: bool
    level: InclusionLevel
    spec: PathSpec


@dataclass(frozen=True, slots=True)
class CompiledLayer:
    base_dir: Path
    source: LayerSource
    config_path: Path | None
    rules: tuple[CompiledRule, ...]


@dataclass(frozen=True, slots=True)
class InclusionReason:
    """Provenance for the winning inclusion rule."""

    raw: str
    core: str
    negated: bool
    level: InclusionLevel
    base_dir: Path
    source: LayerSource
    config_path: Path | None


# Historical type name retained for imports in downstream code.
ExclusionReason = InclusionReason


@dataclass(frozen=True, slots=True)
class InclusionDecision:
    level: InclusionLevel
    reason: InclusionReason | None

    @property
    def tree_included(self) -> bool:
        return self.level is not InclusionLevel.OMIT

    @property
    def content_included(self) -> bool:
        return self.level is InclusionLevel.FULL


PolicyDecision = InclusionDecision


@dataclass(frozen=True, slots=True)
class MatchDecision:
    """Compatibility projection onto the former tree/content booleans."""

    excluded: bool
    reason: InclusionReason | None


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
    target: list[InclusionRule],
    patterns: Iterable[str],
    level: InclusionLevel,
) -> None:
    target.extend(InclusionRule(pattern=str(pattern), level=level) for pattern in patterns)


def rules_from_config(source: dict[str, object]) -> tuple[InclusionRule, ...]:
    """Translate one config source into its ordered inclusion-rule stream."""
    canonical = any(key in source for key in (CONFIG_EXCLUDE, CONFIG_TREE_ONLY, CONFIG_INCLUDE))
    rules: list[InclusionRule] = []

    if canonical:
        _append_rules(rules, _extract_patterns(source, CONFIG_EXCLUDE), InclusionLevel.OMIT)
        _append_rules(
            rules,
            _extract_patterns(source, CONFIG_TREE_ONLY),
            InclusionLevel.TREE_ONLY,
        )
        _append_rules(rules, _extract_patterns(source, CONFIG_INCLUDE), InclusionLevel.FULL)
        return tuple(rules)

    # Compatibility with the former independent scopes. Content exclusions are
    # applied first and tree exclusions second so a path present in both old
    # lists maps to OMIT rather than TREE_ONLY.
    legacy_content_key = CONFIG_EXCLUDE_CONTENT if CONFIG_EXCLUDE_CONTENT in source else CONFIG_EXCLUDE_PRINT
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
    return tuple(rules)


def _compile_rules(rules: Iterable[InclusionRule]) -> tuple[CompiledRule, ...]:
    compiled: list[CompiledRule] = []
    for rule in rules:
        raw = rule.pattern.strip()
        if not raw or raw.startswith("#"):
            continue
        negated = raw.startswith("!")
        core = raw[1:] if negated else raw
        # Legacy/config gitignore negation is an explicit restoration.
        level = InclusionLevel.FULL if negated else rule.level
        compiled.append(
            CompiledRule(
                raw=raw,
                core=core,
                negated=negated,
                level=level,
                spec=PathSpec.from_lines("gitignore", [core]),
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
    value = rel.as_posix()
    if is_dir and not value.endswith("/"):
        return value + "/"
    return value


def _match_candidates(rel: Path, *, is_dir: bool) -> tuple[str, ...]:
    """Return the path plus ancestor directories for gitignore-style matching."""
    candidates = [
        _to_git_path(Path(*rel.parts[:index]), is_dir=True)
        for index in range(1, len(rel.parts))
    ]
    candidates.append(_to_git_path(rel, is_dir=is_dir))
    return tuple(candidates)


def _literal_prefix(core: str) -> tuple[tuple[str, ...], bool, bool]:
    """Return literal components, dynamic-suffix state, and basename scope.

    The result is intentionally conservative. It is used only to prove that an
    omitted directory cannot possibly contain a path restored by a FULL rule.
    """
    anchored = core.startswith("/")
    pattern = core[1:] if anchored else core
    pattern = pattern.rstrip("/")

    if not pattern:
        return (), True, True

    # Gitignore patterns without a slash (after removing a trailing slash) can
    # match a basename at any depth. They therefore have no useful subtree
    # prefix unless explicitly root-anchored.
    if not anchored and "/" not in pattern:
        return (), True, True

    literal: list[str] = []
    dynamic = False
    for component in pattern.split("/"):
        escaped = False
        component_is_dynamic = False
        decoded: list[str] = []
        for char in component:
            if escaped:
                decoded.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char in "*?[":
                component_is_dynamic = True
                break
            decoded.append(char)
        if escaped:
            decoded.append("\\")

        if component_is_dynamic:
            dynamic = True
            break
        literal.append("".join(decoded))

    return tuple(part for part in literal if part), dynamic, False


def _rule_may_match_descendant(rule: CompiledRule, rel_dir: Path) -> bool:
    """Return whether a FULL rule could match at or below rel_dir."""
    literal, dynamic, unanchored_basename = _literal_prefix(rule.core)
    if unanchored_basename or not literal:
        return True

    prefix = Path(*literal)
    if dynamic:
        return prefix.is_relative_to(rel_dir) or rel_dir.is_relative_to(prefix)

    # An exact path can matter only when it is below the omitted directory.
    # Equality is handled by the ordinary inclusion decision for that directory.
    return prefix != rel_dir and prefix.is_relative_to(rel_dir)


@dataclass(frozen=True, slots=True)
class LayeredIgnoreMatcher:
    """Sequential inclusion matcher with per-layer bases."""

    layers: tuple[CompiledLayer, ...]
    has_reinclusions: bool

    @staticmethod
    def _decide(
        layers: tuple[CompiledLayer, ...],
        abs_path: Path,
        *,
        is_dir: bool,
        include_ancestors: bool = False,
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

            candidates = (
                _match_candidates(rel, is_dir=is_dir)
                if include_ancestors
                else (_to_git_path(rel, is_dir=is_dir),)
            )
            for rule in layer.rules:
                if any(rule.spec.match_file(candidate) for candidate in candidates):
                    level = rule.level
                    reason = InclusionReason(
                        raw=rule.raw,
                        core=rule.core,
                        negated=rule.negated,
                        level=rule.level,
                        base_dir=layer.base_dir,
                        source=layer.source,
                        config_path=layer.config_path,
                    )

        return InclusionDecision(level=level, reason=reason)

    def explain_inclusion(self, abs_path: Path, *, is_dir: bool) -> InclusionDecision:
        return self._decide(self.layers, abs_path, is_dir=is_dir)

    def explain_inclusion_with_ancestors(
        self,
        abs_path: Path,
        *,
        is_dir: bool,
    ) -> InclusionDecision:
        """Resolve a path while preserving policy inherited from directory ancestors."""
        return self._decide(
            self.layers,
            abs_path,
            is_dir=is_dir,
            include_ancestors=True,
        )

    def explain_policy(self, abs_path: Path, *, is_dir: bool) -> InclusionDecision:
        """Compatibility wrapper for the policy-migration API."""
        return self.explain_inclusion(abs_path, is_dir=is_dir)

    def explain_tree(self, abs_path: Path, *, is_dir: bool) -> MatchDecision:
        decision = self.explain_inclusion(abs_path, is_dir=is_dir)
        if decision.level is InclusionLevel.OMIT:
            return MatchDecision(excluded=True, reason=decision.reason)
        return MatchDecision(excluded=False, reason=None)

    def explain_content(self, abs_path: Path, *, is_dir: bool) -> MatchDecision:
        decision = self.explain_inclusion(abs_path, is_dir=is_dir)
        if decision.level is InclusionLevel.FULL:
            return MatchDecision(excluded=False, reason=None)
        return MatchDecision(excluded=True, reason=decision.reason)

    def excluded_from_tree(self, abs_path: Path, *, is_dir: bool) -> bool:
        return self.explain_inclusion(abs_path, is_dir=is_dir).level is InclusionLevel.OMIT

    def excluded_from_print(self, abs_path: Path, *, is_dir: bool) -> bool:
        return self.explain_inclusion(abs_path, is_dir=is_dir).level is not InclusionLevel.FULL

    def may_reinclude_descendant(self, directory: Path) -> bool:
        """Return whether any FULL rule could restore a path below directory.

        False is returned only when the rule set proves that no restoration can
        occur in this subtree. Unanchored basename patterns remain deliberately
        conservative because they can match at arbitrary depth.
        """
        if not self.has_reinclusions:
            return False

        for layer in self.layers:
            try:
                if not directory.is_relative_to(layer.base_dir):
                    continue
                rel_dir = directory.relative_to(layer.base_dir)
            except OSError:
                continue

            for rule in layer.rules:
                if (
                    rule.level is InclusionLevel.FULL
                    and _rule_may_match_descendant(rule, rel_dir)
                ):
                    return True
        return False

    @property
    def has_restore_rules(self) -> bool:
        return self.has_reinclusions

    @property
    def tree_has_negations(self) -> bool:
        return self.has_reinclusions

    @property
    def print_has_negations(self) -> bool:
        return self.has_reinclusions


def _config_layer(
    *,
    base_dir: Path,
    source: LayerSource,
    data: dict[str, object],
    config_path: Path | None = None,
) -> InclusionLayer:
    return InclusionLayer(
        base_dir=base_dir,
        rules=rules_from_config(data),
        source=source,
        config_path=config_path,
    )


def _runtime_rules(
    *,
    exclude: Sequence[str],
    tree_only: Sequence[str],
    include: Sequence[str],
    legacy_tree: Sequence[str],
    legacy_content: Sequence[str],
    extra_rules: Sequence[InclusionRule],
) -> tuple[InclusionRule, ...]:
    rules: list[InclusionRule] = []
    _append_rules(rules, legacy_content, InclusionLevel.TREE_ONLY)
    _append_rules(rules, legacy_tree, InclusionLevel.OMIT)
    _append_rules(rules, exclude, InclusionLevel.OMIT)
    _append_rules(rules, tree_only, InclusionLevel.TREE_ONLY)
    _append_rules(rules, include, InclusionLevel.FULL)
    rules.extend(extra_rules)
    return tuple(rules)


def build_layered_ignores(
    *,
    repo_root: Path,
    include_defaults: bool,
    default_cfg: dict[str, object],
    config_layers: Sequence[InclusionLayer] = (),
    runtime_exclude: Sequence[str] = (),
    runtime_tree_only: Sequence[str] = (),
    runtime_include: Sequence[str] = (),
    runtime_tree_patterns: Sequence[str] = (),
    runtime_print_patterns: Sequence[str] = (),
    runtime_rules: Sequence[InclusionRule] = (),
) -> LayeredIgnoreMatcher:
    """Assemble defaults -> hierarchical config -> explicit config -> CLI."""
    layers: list[InclusionLayer] = []

    if include_defaults:
        layers.append(
            _config_layer(
                base_dir=repo_root,
                source=LayerSource.DEFAULTS,
                data=default_cfg,
            )
        )

    layers.extend(config_layers)

    layers.append(
        InclusionLayer(
            base_dir=repo_root,
            rules=_runtime_rules(
                exclude=runtime_exclude,
                tree_only=runtime_tree_only,
                include=runtime_include,
                legacy_tree=runtime_tree_patterns,
                legacy_content=runtime_print_patterns,
                extra_rules=runtime_rules,
            ),
            source=LayerSource.CLI_RUNTIME,
        )
    )

    compiled = compile_layers(layers)
    has_reinclusions = any(rule.level is InclusionLevel.FULL for layer in compiled for rule in layer.rules)
    return LayeredIgnoreMatcher(
        layers=compiled,
        has_reinclusions=has_reinclusions,
    )
