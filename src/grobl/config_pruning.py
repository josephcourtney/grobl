"""Conservative pruning helpers for canonical inclusion configuration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import tomlkit
from tomlkit.exceptions import TOMLKitError
from tomlkit.items import Array

from grobl.config_defaults import TOML_CONFIG, load_default_config
from grobl.config_loading import load_toml_config
from grobl.constants import (
    CONFIG_EXCLUDE,
    CONFIG_EXCLUDE_CONTENT,
    CONFIG_EXCLUDE_PRINT,
    CONFIG_EXCLUDE_TREE,
    CONFIG_INCLUDE,
    CONFIG_TREE_ONLY,
    InclusionLevel,
)
from grobl.errors import ConfigLoadError
from grobl.ignore import (
    InclusionLayer,
    InclusionRule,
    LayerSource,
    LayeredIgnoreMatcher,
    compile_layers,
    discover_grobl_toml_files,
    rules_from_config,
)
from grobl.utils import resolve_repo_root

if TYPE_CHECKING:
    from tomlkit.toml_document import TOMLDocument

CANONICAL_POLICY_KEYS = (CONFIG_EXCLUDE, CONFIG_TREE_ONLY, CONFIG_INCLUDE)
LEGACY_POLICY_KEYS = (CONFIG_EXCLUDE_TREE, CONFIG_EXCLUDE_PRINT, CONFIG_EXCLUDE_CONTENT)
_POLICY_LEVELS = {
    CONFIG_EXCLUDE: InclusionLevel.OMIT,
    CONFIG_TREE_ONLY: InclusionLevel.TREE_ONLY,
    CONFIG_INCLUDE: InclusionLevel.FULL,
}


class ConfigPruneError(ValueError):
    """Raised when a configuration cannot be pruned safely."""


@dataclass(frozen=True, slots=True)
class PrunedRule:
    """One rule removed by configuration pruning."""

    key: str
    pattern: str
    reason: str


@dataclass(frozen=True, slots=True)
class ConfigPruneResult:
    """Result of pruning one canonical TOML document."""

    text: str
    changed: bool
    removed: tuple[PrunedRule, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _RuleRef:
    key: str
    index: int
    pattern: str
    core: str
    level: InclusionLevel


@dataclass(frozen=True, slots=True)
class _PruneContext:
    path: Path
    repo_root: Path
    lower_layers: tuple[InclusionLayer, ...]


def _parse_document(text: str) -> TOMLDocument:
    try:
        return tomlkit.parse(text)
    except TOMLKitError as err:
        msg = f"invalid TOML: {err}"
        raise ConfigPruneError(msg) from err


def _validate_canonical(document: TOMLDocument) -> None:
    legacy = [key for key in LEGACY_POLICY_KEYS if key in document]
    if not legacy:
        return
    names = ", ".join(legacy)
    msg = f"config uses legacy inclusion keys ({names}); run 'grobl config migrate' first"
    raise ConfigPruneError(msg)


def _patterns(value: object, *, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        items = tuple(value)
        if all(isinstance(item, str) for item in items):
            return tuple(item for item in items if isinstance(item, str))
    msg = f"{key} must be a string or an array of strings"
    raise ConfigPruneError(msg)


def _rule_identity(pattern: str, level: InclusionLevel) -> tuple[str, InclusionLevel] | None:
    raw = pattern.strip()
    if not raw or raw.startswith("#"):
        return None
    negated = raw.startswith("!")
    core = raw.removeprefix("!")
    effective = InclusionLevel.FULL if negated else level
    return core, effective


def _rule_refs(document: TOMLDocument) -> tuple[_RuleRef, ...]:
    refs: list[_RuleRef] = []
    for key in CANONICAL_POLICY_KEYS:
        level = _POLICY_LEVELS[key]
        for index, pattern in enumerate(_patterns(document.get(key), key=key)):
            identity = _rule_identity(pattern, level)
            if identity is None:
                continue
            core, effective = identity
            refs.append(
                _RuleRef(
                    key=key,
                    index=index,
                    pattern=pattern,
                    core=core,
                    level=effective,
                )
            )
    return tuple(refs)


def _delete_rule(document: TOMLDocument, ref: _RuleRef) -> None:
    value = document.get(ref.key)
    if isinstance(value, str):
        document[ref.key] = []
        return
    if isinstance(value, Array):
        del value[ref.index]
        return
    msg = f"{ref.key} must be a string or an array of strings"
    raise ConfigPruneError(msg)


def _prune_shadowed_rules(document: TOMLDocument) -> list[PrunedRule]:
    refs = _rule_refs(document)
    last_index: dict[str, int] = {}
    for position, ref in enumerate(refs):
        last_index[ref.core] = position

    doomed = [ref for position, ref in enumerate(refs) if last_index[ref.core] != position]
    for key in CANONICAL_POLICY_KEYS:
        key_refs = sorted(
            (ref for ref in doomed if ref.key == key),
            key=lambda ref: ref.index,
            reverse=True,
        )
        for ref in key_refs:
            _delete_rule(document, ref)

    return [
        PrunedRule(
            key=ref.key,
            pattern=ref.pattern,
            reason="shadowed by a later identical matcher in this config",
        )
        for ref in doomed
    ]


def prune_config_text(text: str) -> ConfigPruneResult:
    """Remove rules that are provably shadowed within one canonical source."""
    document = _parse_document(text)
    _validate_canonical(document)
    removed = tuple(_prune_shadowed_rules(document))
    if not removed:
        return ConfigPruneResult(text=text, changed=False)
    return ConfigPruneResult(
        text=tomlkit.dumps(document),
        changed=True,
        removed=removed,
    )


def _config_layer(path: Path, data: dict[str, object], *, source: LayerSource) -> InclusionLayer:
    return InclusionLayer(
        base_dir=path.parent.resolve(),
        rules=rules_from_config(data),
        source=source,
        config_path=path.resolve(),
    )


def _lower_layers(
    path: Path,
    *,
    repo_root: Path,
    default_cfg: dict[str, object],
) -> tuple[InclusionLayer, ...]:
    layers = [
        InclusionLayer(
            base_dir=repo_root,
            rules=rules_from_config(default_cfg),
            source=LayerSource.DEFAULTS,
        )
    ]
    target = path.resolve()
    for config_path in discover_grobl_toml_files(repo_root=repo_root, scan_paths=[path.parent]):
        real = config_path.resolve()
        if real == target:
            continue
        layers.append(
            _config_layer(
                real,
                load_toml_config(real),
                source=LayerSource.CONFIG,
            )
        )
    return tuple(layers)


def _extends_entries(document: TOMLDocument) -> tuple[str, ...]:
    value = document.get("extends")
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _target_data(document: TOMLDocument, path: Path) -> dict[str, object]:
    data: dict[str, object] = {}
    for entry in _extends_entries(document):
        ext_path = Path(entry)
        if not ext_path.is_absolute():
            ext_path = (path.parent / ext_path).resolve()
        if ext_path.exists() and ext_path != path.resolve():
            data |= load_toml_config(ext_path)
    data |= {str(key): value for key, value in document.items() if key != "extends"}
    return data


def _matcher(layers: Sequence[InclusionLayer]) -> LayeredIgnoreMatcher:
    compiled = compile_layers(layers)
    has_reinclusions = any(
        rule.level is InclusionLevel.FULL for layer in compiled for rule in layer.rules
    )
    return LayeredIgnoreMatcher(layers=compiled, has_reinclusions=has_reinclusions)


def _matcher_for_document(
    document: TOMLDocument,
    *,
    context: _PruneContext,
) -> LayeredIgnoreMatcher:
    source = LayerSource.CONFIG if context.path.name == TOML_CONFIG else LayerSource.EXPLICIT_CONFIG
    target = _config_layer(
        context.path,
        _target_data(document, context.path),
        source=source,
    )
    return _matcher((*context.lower_layers, target))


def _same_current_tree(
    left: LayeredIgnoreMatcher,
    right: LayeredIgnoreMatcher,
    *,
    root: Path,
) -> bool:
    root = root.resolve()
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            items = sorted(directory.iterdir(), key=lambda item: item.as_posix().casefold())
        except OSError:
            continue
        for item in items:
            is_dir = item.is_dir()
            left_decision = left.explain_inclusion(item, is_dir=is_dir)
            right_decision = right.explain_inclusion(item, is_dir=is_dir)
            if left_decision.level is not right_decision.level:
                return False
            if not is_dir or item.is_symlink():
                continue
            if left_decision.level is InclusionLevel.OMIT and not (
                left.has_reinclusions or right.has_reinclusions
            ):
                continue
            stack.append(item)
    return True


def _inherited_identities(context: _PruneContext) -> frozenset[tuple[str, InclusionLevel]]:
    identities: set[tuple[str, InclusionLevel]] = set()
    base = context.path.parent.resolve()
    for layer in context.lower_layers:
        if layer.base_dir != base:
            continue
        for rule in layer.rules:
            identity = _rule_identity(rule.pattern, rule.level)
            if identity is not None:
                identities.add(identity)
    return frozenset(identities)


def _prune_current_tree(document: TOMLDocument, *, context: _PruneContext) -> list[PrunedRule]:
    inherited = _inherited_identities(context)
    if not inherited:
        return []

    removed: list[PrunedRule] = []
    while True:
        baseline = _matcher_for_document(document, context=context)
        candidate: _RuleRef | None = None
        for ref in _rule_refs(document):
            if (ref.core, ref.level) not in inherited:
                continue
            variant = _parse_document(tomlkit.dumps(document))
            _delete_rule(variant, ref)
            without = _matcher_for_document(variant, context=context)
            if _same_current_tree(baseline, without, root=context.path.parent):
                candidate = ref
                break
        if candidate is None:
            return removed
        _delete_rule(document, candidate)
        removed.append(
            PrunedRule(
                key=candidate.key,
                pattern=candidate.pattern,
                reason="duplicates inherited policy without changing the current scan tree",
            )
        )


def inspect_config_pruning(
    path: Path,
    *,
    current_tree: bool = False,
    repo_root: Path | None = None,
    default_cfg: dict[str, object] | None = None,
) -> ConfigPruneResult:
    """Return the pruned representation of ``path`` without writing it."""
    try:
        original = path.read_text(encoding="utf-8")
    except OSError as err:
        msg = f"could not read {path}: {err}"
        raise ConfigPruneError(msg) from err

    document = _parse_document(original)
    _validate_canonical(document)
    removed = _prune_shadowed_rules(document)
    warnings: tuple[str, ...] = ()

    if current_tree:
        resolved_root = (
            repo_root.resolve()
            if repo_root is not None
            else resolve_repo_root(cwd=path.parent, paths=(path.parent,))
        )
        try:
            defaults = load_default_config() if default_cfg is None else default_cfg
            context = _PruneContext(
                path=path.resolve(),
                repo_root=resolved_root,
                lower_layers=_lower_layers(path, repo_root=resolved_root, default_cfg=defaults),
            )
            current_removed = _prune_current_tree(document, context=context)
        except (OSError, ConfigLoadError) as err:
            msg = f"could not resolve inherited configuration for {path}: {err}"
            raise ConfigPruneError(msg) from err
        removed.extend(current_removed)
        if current_removed:
            warnings = (
                "current-tree pruning depends on the repository paths that exist now; "
                "future paths may make an inherited duplicate relevant again",
            )

    if not removed:
        return ConfigPruneResult(text=original, changed=False)
    return ConfigPruneResult(
        text=tomlkit.dumps(document),
        changed=True,
        removed=tuple(removed),
        warnings=warnings,
    )


def prune_config_file(
    path: Path,
    *,
    current_tree: bool = False,
    backup: bool = True,
) -> tuple[ConfigPruneResult, Path | None]:
    """Prune a config file in place and optionally preserve the original."""
    result = inspect_config_pruning(path, current_tree=current_tree)
    if not result.changed:
        return result, None

    try:
        original = path.read_text(encoding="utf-8")
    except OSError as err:
        msg = f"could not reread {path}: {err}"
        raise ConfigPruneError(msg) from err

    backup_path: Path | None = None
    if backup:
        backup_path = Path(f"{path}.bak")
        if backup_path.exists():
            msg = f"backup already exists: {backup_path}; remove it or use --no-backup"
            raise ConfigPruneError(msg)
        try:
            backup_path.write_text(original, encoding="utf-8")
        except OSError as err:
            msg = f"could not write backup {backup_path}: {err}"
            raise ConfigPruneError(msg) from err

    try:
        path.write_text(result.text, encoding="utf-8")
    except OSError as err:
        msg = f"could not write pruned config {path}: {err}"
        raise ConfigPruneError(msg) from err

    return result, backup_path
