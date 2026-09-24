"""Generated-artifact provenance and inclusion-policy integration."""

from __future__ import annotations

import posixpath
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from pathspec import PathSpec

from .constants import InclusionLevel
from .directory import DirectoryTreeBuilder
from .errors import ConfigLoadError
from .ignore import (
    InclusionDecision,
    InclusionLayer,
    InclusionReason,
    InclusionRule,
    LayeredIgnoreMatcher,
    MatchDecision,
)

_GENERATED_KEY = "generated"


@dataclass(frozen=True, slots=True)
class GeneratedRelation:
    """One config-declared generated target and its source references."""

    pattern: str
    sources: tuple[str, ...]
    base_dir: Path
    config_path: Path | None


@dataclass(frozen=True, slots=True)
class GeneratedInclusionReason(InclusionReason):
    """Winning inclusion reason derived from a generated relation."""

    generated_from: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _CompiledGeneratedRelation:
    relation: GeneratedRelation
    spec: PathSpec

    def matches(self, path: Path, *, is_dir: bool) -> bool:
        try:
            rel = path.relative_to(self.relation.base_dir)
        except (ValueError, OSError):
            return False
        candidate = rel.as_posix()
        if is_dir and not candidate.endswith("/"):
            candidate += "/"
        return self.spec.match_file(candidate)


def _config_error(config_path: Path | None, detail: str) -> ConfigLoadError:
    location = str(config_path) if config_path is not None else "configuration"
    return ConfigLoadError(f"invalid [[generated]] entry in {location}: {detail}")


def relations_from_config(
    source: Mapping[str, object],
    *,
    base_dir: Path,
    config_path: Path | None,
) -> tuple[GeneratedRelation, ...]:
    """Parse ``[[generated]]`` declarations from one config source."""
    raw_entries = source.get(_GENERATED_KEY)
    if raw_entries is None:
        return ()
    if isinstance(raw_entries, (str, bytes)) or not isinstance(raw_entries, Sequence):
        raise _config_error(config_path, "expected an array of tables")

    relations: list[GeneratedRelation] = []
    for index, raw_entry in enumerate(raw_entries, start=1):
        if not isinstance(raw_entry, Mapping):
            raise _config_error(config_path, f"entry {index} must be a table")

        raw_pattern = raw_entry.get("path")
        if not isinstance(raw_pattern, str) or not raw_pattern.strip():
            raise _config_error(config_path, f"entry {index} requires a non-empty string 'path'")
        pattern = raw_pattern.strip()
        if pattern.startswith("!"):
            raise _config_error(config_path, f"entry {index} path may not use gitignore negation")

        raw_sources = raw_entry.get("from")
        if isinstance(raw_sources, (str, bytes)) or not isinstance(raw_sources, Sequence):
            raise _config_error(config_path, f"entry {index} requires 'from' to be an array of strings")

        sources: list[str] = []
        for source_index, raw_source in enumerate(raw_sources, start=1):
            if not isinstance(raw_source, str) or not raw_source.strip():
                raise _config_error(
                    config_path,
                    f"entry {index} source {source_index} must be a non-empty string",
                )
            value = raw_source.strip()
            if value not in sources:
                sources.append(value)
        if not sources:
            raise _config_error(config_path, f"entry {index} requires at least one source")

        relations.append(
            GeneratedRelation(
                pattern=pattern,
                sources=tuple(sources),
                base_dir=base_dir,
                config_path=config_path,
            )
        )
    return tuple(relations)


def _source_display(source: str, *, source_base: Path, display_base: Path) -> str:
    """Render a config-relative source reference relative to the scan root."""
    try:
        base_rel = source_base.relative_to(display_base).as_posix()
    except (ValueError, OSError):
        if source.startswith("/"):
            return source
        return (source_base / source).as_posix()

    prefix = "" if base_rel in {"", "."} else f"{base_rel}/"
    raw = source[1:] if source.startswith("/") else source
    normalized = posixpath.normpath(f"{prefix}{raw}")
    return raw if normalized == "." else normalized


class GeneratedRelationIndex:
    """Compiled generated relationships plus winning-rule provenance."""

    __slots__ = (
        "_compiled",
        "_explicit_tree_only_keys",
        "_generated_rule_keys",
    )

    def __init__(
        self,
        relations: Sequence[GeneratedRelation] = (),
        *,
        explicit_layers: Sequence[InclusionLayer] = (),
    ) -> None:
        self._compiled = tuple(
            _CompiledGeneratedRelation(
                relation=relation,
                spec=PathSpec.from_lines("gitignore", (relation.pattern,)),
            )
            for relation in relations
        )
        self._generated_rule_keys = frozenset(
            (relation.base_dir, relation.config_path, relation.pattern) for relation in relations
        )
        self._explicit_tree_only_keys = frozenset(
            (layer.base_dir, layer.config_path, rule.pattern)
            for layer in explicit_layers
            for rule in layer.rules
            if rule.level is InclusionLevel.TREE_ONLY
        )

    @property
    def empty(self) -> bool:
        return not self._compiled

    def matches(self, path: Path, *, is_dir: bool = False) -> tuple[GeneratedRelation, ...]:
        return tuple(item.relation for item in self._compiled if item.matches(path, is_dir=is_dir))

    def sources_for(
        self,
        path: Path,
        *,
        display_base: Path,
        is_dir: bool = False,
    ) -> tuple[str, ...]:
        """Return deduplicated source references for all matching relations."""
        sources: list[str] = []
        for relation in self.matches(path, is_dir=is_dir):
            for source in relation.sources:
                display = _source_display(
                    source,
                    source_base=relation.base_dir,
                    display_base=display_base,
                )
                if display not in sources:
                    sources.append(display)
        return tuple(sources)

    def reason_is_generated(self, reason: InclusionReason) -> bool:
        if reason.level is not InclusionLevel.TREE_ONLY:
            return False
        key = (reason.base_dir, reason.config_path, reason.raw)
        return key in self._generated_rule_keys and key not in self._explicit_tree_only_keys


def decorate_inclusion_layer(
    layer: InclusionLayer,
    source: Mapping[str, object],
) -> tuple[InclusionLayer, tuple[GeneratedRelation, ...]]:
    """Prepend generated-derived TREE_ONLY rules to one config layer."""
    relations = relations_from_config(
        source,
        base_dir=layer.base_dir,
        config_path=layer.config_path,
    )
    generated_rules = tuple(
        InclusionRule(pattern=relation.pattern, level=InclusionLevel.TREE_ONLY)
        for relation in relations
    )
    return replace(layer, rules=(*generated_rules, *layer.rules)), relations


@dataclass(frozen=True, slots=True)
class GeneratedAwareMatcher(LayeredIgnoreMatcher):
    """Layered inclusion matcher augmented with generated provenance."""

    generated_index: GeneratedRelationIndex
    repo_root: Path

    def _with_generated_reason(
        self,
        path: Path,
        decision: InclusionDecision,
        *,
        is_dir: bool,
    ) -> InclusionDecision:
        reason = decision.reason
        if reason is None or not self.generated_index.reason_is_generated(reason):
            return decision
        sources = self.generated_index.sources_for(
            path,
            display_base=self.repo_root,
            is_dir=is_dir,
        )
        generated_reason = GeneratedInclusionReason(
            raw=reason.raw,
            core=reason.core,
            negated=reason.negated,
            level=reason.level,
            base_dir=reason.base_dir,
            source=reason.source,
            config_path=reason.config_path,
            generated_from=sources,
        )
        return InclusionDecision(level=decision.level, reason=generated_reason)

    def explain_inclusion(self, abs_path: Path, *, is_dir: bool) -> InclusionDecision:
        decision = super().explain_inclusion(abs_path, is_dir=is_dir)
        return self._with_generated_reason(abs_path, decision, is_dir=is_dir)

    def explain_policy(self, abs_path: Path, *, is_dir: bool) -> InclusionDecision:
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

    def generated_sources(
        self,
        path: Path,
        *,
        display_base: Path | None = None,
        is_dir: bool = False,
    ) -> tuple[str, ...]:
        return self.generated_index.sources_for(
            path,
            display_base=self.repo_root if display_base is None else display_base,
            is_dir=is_dir,
        )


class GeneratedDirectoryTreeBuilder(DirectoryTreeBuilder):
    """Directory builder that annotates generated files in rendered tree lines."""

    __slots__ = ("generated_index",)

    def __init__(
        self,
        *,
        base_path: Path,
        exclude_patterns: list[str],
        generated_index: GeneratedRelationIndex,
    ) -> None:
        super().__init__(base_path=base_path, exclude_patterns=exclude_patterns)
        self.generated_index = generated_index

    def generated_sources(self, rel: Path, *, is_dir: bool = False) -> tuple[str, ...]:
        return self.generated_index.sources_for(
            self.base_path / rel,
            display_base=self.base_path,
            is_dir=is_dir,
        )

    def tree_output(self) -> list[str]:
        lines = super().tree_output()
        ordered = self.ordered_entries()
        if len(lines) != len(ordered):
            return lines
        for index, (kind, rel) in enumerate(ordered):
            if kind != "file":
                continue
            sources = self.generated_sources(rel)
            if sources:
                lines[index] = f"{lines[index]} [generated from {', '.join(sources)}]"
        return lines


def builder_for_matcher(
    *,
    base_path: Path,
    exclude_patterns: list[str],
    matcher: LayeredIgnoreMatcher | GeneratedAwareMatcher,
) -> DirectoryTreeBuilder:
    """Create a provenance-aware builder only when generated relations exist."""
    if isinstance(matcher, GeneratedAwareMatcher) and not matcher.generated_index.empty:
        return GeneratedDirectoryTreeBuilder(
            base_path=base_path,
            exclude_patterns=exclude_patterns,
            generated_index=matcher.generated_index,
        )
    return DirectoryTreeBuilder(base_path=base_path, exclude_patterns=exclude_patterns)
