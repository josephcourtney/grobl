"""Conservative pruning helpers for canonical inclusion configuration."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import tomlkit
from tomlkit.exceptions import TOMLKitError
from tomlkit.items import Array

from grobl.config_defaults import TOML_CONFIG, load_default_config
from grobl.config_loading import (
    LEGACY_TOML_CONFIG,
    PYPROJECT_TOML,
    discover_grobl_toml_files,
    load_toml_config,
)
from grobl.constants import (
    CONFIG_EXCLUDE,
    CONFIG_EXCLUDE_CONTENT,
    CONFIG_EXCLUDE_PRINT,
    CONFIG_EXCLUDE_TREE,
    CONFIG_INCLUDE,
    CONFIG_INHERIT_DEFAULTS,
    CONFIG_TREE_ONLY,
    InclusionLevel,
)
from grobl.errors import ConfigLoadError
from grobl.ignore import (
    InclusionLayer,
    LayeredIgnoreMatcher,
    LayerSource,
    compile_layers,
    rules_from_config,
)
from grobl.utils import logical_absolute, resolve_repo_root

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
    removed_settings: tuple[str, ...] = ()
    removed_empty_keys: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def removal_count(self) -> int:
        """Total number of removed config entries."""
        return len(self.removed) + len(self.removed_settings) + len(self.removed_empty_keys)


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


@dataclass(frozen=True, slots=True)
class _CurrentTreeEntry:
    path: Path
    is_dir: bool
    level: InclusionLevel


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


def _policy_array_key(line: str) -> str | None:
    stripped = line.strip()
    return next(
        (
            candidate
            for candidate in CANONICAL_POLICY_KEYS
            if stripped.startswith(f"{candidate} = [") and "]" not in stripped
        ),
        None,
    )


def _split_nonblank_segments(lines: Sequence[str]) -> list[list[str]]:
    segments: list[list[str]] = []
    segment: list[str] = []
    for line in lines:
        if line.strip():
            segment.append(line)
        elif segment:
            segments.append(segment)
            segment = []
    if segment:
        segments.append(segment)
    return segments


def _comment_signature(group: Sequence[str]) -> tuple[str, ...]:
    return tuple(line.strip() for line in group if line.lstrip().startswith("#"))


def _has_value(group: Sequence[str]) -> bool:
    return any(not line.lstrip().startswith("#") for line in group)


def _comment_groups_with_values(text: str) -> set[tuple[str, tuple[str, ...]]]:
    """Return policy-array comment groups that originally described values."""
    lines = text.splitlines()
    associated: set[tuple[str, tuple[str, ...]]] = set()
    index = 0

    while index < len(lines):
        key = _policy_array_key(lines[index])
        if key is None:
            index += 1
            continue

        index += 1
        inner: list[str] = []
        while index < len(lines) and lines[index].strip() != "]":
            inner.append(lines[index])
            index += 1

        for group in _split_nonblank_segments(inner):
            comments = _comment_signature(group)
            if comments and _has_value(group):
                associated.add((key, comments))
        index += 1

    return associated


def _keep_comment_group(
    key: str,
    group: Sequence[str],
    *,
    associated: set[tuple[str, tuple[str, ...]]],
) -> bool:
    comments = _comment_signature(group)
    return _has_value(group) or not comments or (key, comments) not in associated


def _clean_orphan_array_comments(text: str, *, original_text: str) -> str:
    """Drop comment groups made empty by policy-array pruning."""
    associated = _comment_groups_with_values(original_text)
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    index = 0

    while index < len(lines):
        key = _policy_array_key(lines[index])
        if key is None:
            output.append(lines[index])
            index += 1
            continue

        output.append(lines[index])
        index += 1
        inner: list[str] = []
        while index < len(lines) and lines[index].strip() != "]":
            inner.append(lines[index])
            index += 1

        kept = [
            group
            for group in _split_nonblank_segments(inner)
            if _keep_comment_group(key, group, associated=associated)
        ]
        for group_index, group in enumerate(kept):
            if group_index:
                output.append("\n")
            output.extend(group)

        if index < len(lines):
            output.append(lines[index])
            index += 1

    return "".join(output)


def prune_config_text(text: str) -> ConfigPruneResult:
    """Remove rules that are provably shadowed within one canonical source."""
    document = _parse_document(text)
    _validate_canonical(document)
    removed = tuple(_prune_shadowed_rules(document))
    if not removed:
        return ConfigPruneResult(text=text, changed=False)
    return ConfigPruneResult(
        text=_clean_orphan_array_comments(tomlkit.dumps(document), original_text=text),
        changed=True,
        removed=removed,
    )


def _config_layer(path: Path, data: dict[str, object], *, source: LayerSource) -> InclusionLayer:
    logical = logical_absolute(path)
    return InclusionLayer(
        base_dir=logical.parent,
        rules=rules_from_config(data),
        source=source,
        config_path=logical,
    )


def _lower_layers(
    path: Path,
    *,
    repo_root: Path,
    default_cfg: dict[str, object],
    include_defaults: bool = True,
) -> tuple[InclusionLayer, ...]:
    layers: list[InclusionLayer] = []
    if include_defaults:
        layers.append(
            InclusionLayer(
                base_dir=repo_root,
                rules=rules_from_config(default_cfg),
                source=LayerSource.DEFAULTS,
            )
        )
    target = logical_absolute(path)
    for config_path in discover_grobl_toml_files(repo_root=repo_root, scan_paths=[target.parent]):
        logical = logical_absolute(config_path)
        if logical == target:
            continue
        layers.append(
            _config_layer(
                logical,
                load_toml_config(logical),
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


def _extends_base(document: TOMLDocument, path: Path) -> dict[str, object]:
    data: dict[str, object] = {}
    for entry in _extends_entries(document):
        ext_path = Path(entry)
        if not ext_path.is_absolute():
            ext_path = (path.parent / ext_path).resolve()
        if ext_path.exists() and ext_path != path.resolve():
            data |= load_toml_config(ext_path)
    return data


def _target_data(document: TOMLDocument, path: Path) -> dict[str, object]:
    data = _extends_base(document, path)
    data |= {str(key): value for key, value in document.items() if key != "extends"}
    return data


def _xdg_config_path() -> Path:
    xdg_home = os.environ.get("XDG_CONFIG_HOME")
    xdg_dir = Path(xdg_home) if xdg_home else Path.home() / ".config"
    return xdg_dir / "grobl" / "config.toml"


def _merge_config_file(config: dict[str, object], path: Path) -> None:
    if path.exists():
        config |= load_toml_config(path)


def _merge_pyproject_config(config: dict[str, object], path: Path) -> None:
    if not path.exists():
        return
    try:
        document = tomlkit.loads(path.read_text(encoding="utf-8"))
    except TOMLKitError as err:
        msg = f"invalid TOML in {path}: {err}"
        raise ConfigPruneError(msg) from err
    tool = document.get("tool")
    if not isinstance(tool, dict):
        return
    grobl_config = tool.get("grobl")
    if isinstance(grobl_config, dict):
        config |= {str(key): value for key, value in grobl_config.items()}


def _lower_general_config(
    path: Path,
    *,
    default_cfg: dict[str, object],
) -> dict[str, object]:
    """Resolve general config values that precede the target in merge precedence."""
    logical_target = logical_absolute(path)
    physical_target = path.resolve()
    base = logical_target.parent
    config = dict(default_cfg)

    for source in (
        _xdg_config_path(),
        base / LEGACY_TOML_CONFIG,
        base / TOML_CONFIG,
    ):
        if logical_absolute(source) == logical_target or source.resolve(strict=False) == physical_target:
            return config
        _merge_config_file(config, source)

    _merge_pyproject_config(config, base / PYPROJECT_TOML)

    env_path = os.environ.get("GROBL_CONFIG_PATH")
    if env_path:
        source = Path(env_path)
        if logical_absolute(source) == logical_target or source.resolve(strict=False) == physical_target:
            return config
        _merge_config_file(config, source)

    return config


def _plain_value(value: object) -> object:
    unwrap = getattr(value, "unwrap", None)
    return unwrap() if callable(unwrap) else value


def _prune_redundant_settings(
    document: TOMLDocument,
    *,
    inherited: dict[str, object],
) -> list[str]:
    removed: list[str] = []
    excluded = {*CANONICAL_POLICY_KEYS, *LEGACY_POLICY_KEYS, "extends"}
    for key in tuple(document):
        name = str(key)
        if name in excluded or name not in inherited:
            continue
        if _plain_value(document[key]) != _plain_value(inherited[name]):
            continue
        del document[key]
        removed.append(name)
    return removed


def _prune_empty_policy_keys(document: TOMLDocument, *, path: Path) -> list[str]:
    """Remove empty canonical keys only when their absence preserves source rules."""
    removed: list[str] = []
    for key in CANONICAL_POLICY_KEYS:
        if key not in document or _patterns(document.get(key), key=key):
            continue
        before = rules_from_config(_target_data(document, path))
        variant = _parse_document(tomlkit.dumps(document))
        del variant[key]
        after = rules_from_config(_target_data(variant, path))
        if before != after:
            continue
        del document[key]
        removed.append(key)
    return removed


def _matcher(layers: Sequence[InclusionLayer]) -> LayeredIgnoreMatcher:
    compiled = compile_layers(layers)
    has_reinclusions = any(rule.level is InclusionLevel.FULL for layer in compiled for rule in layer.rules)
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


def _snapshot_current_tree(
    matcher: LayeredIgnoreMatcher,
    *,
    root: Path,
) -> tuple[_CurrentTreeEntry, ...]:
    """Capture the reachable current tree and its baseline inclusion states once."""
    root = logical_absolute(root)
    stack = [root]
    entries: list[_CurrentTreeEntry] = []
    while stack:
        directory = stack.pop()
        try:
            items = sorted(directory.iterdir(), key=lambda item: item.as_posix().casefold())
        except OSError:
            continue
        for item in items:
            is_dir = item.is_dir()
            decision = matcher.explain_inclusion(item, is_dir=is_dir)
            entries.append(_CurrentTreeEntry(path=item, is_dir=is_dir, level=decision.level))
            if not is_dir or item.is_symlink():
                continue
            if decision.level is InclusionLevel.OMIT and not matcher.may_reinclude_descendant(item):
                continue
            stack.append(item)
    return tuple(entries)


def _matches_current_tree_snapshot(
    matcher: LayeredIgnoreMatcher,
    snapshot: Sequence[_CurrentTreeEntry],
) -> bool:
    """Return whether ``matcher`` preserves every state in a captured current tree."""
    return all(
        matcher.explain_inclusion(entry.path, is_dir=entry.is_dir).level is entry.level for entry in snapshot
    )


def _inherited_identities(context: _PruneContext) -> frozenset[tuple[str, InclusionLevel]]:
    identities: set[tuple[str, InclusionLevel]] = set()
    base = logical_absolute(context.path).parent
    for layer in context.lower_layers:
        if layer.base_dir != base:
            continue
        for rule in layer.rules:
            identity = _rule_identity(rule.pattern, rule.level)
            if identity is not None:
                identities.add(identity)
    return frozenset(identities)


def _rule_ref_signature(ref: _RuleRef) -> tuple[str, str, str, InclusionLevel]:
    return ref.key, ref.pattern, ref.core, ref.level


def _delete_rule_group(document: TOMLDocument, refs: Sequence[_RuleRef]) -> None:
    wanted = {_rule_ref_signature(ref) for ref in refs}
    live = [ref for ref in _rule_refs(document) if _rule_ref_signature(ref) in wanted]
    for key in CANONICAL_POLICY_KEYS:
        key_refs = sorted(
            (ref for ref in live if ref.key == key),
            key=lambda ref: ref.index,
            reverse=True,
        )
        for ref in key_refs:
            _delete_rule(document, ref)


def _pruned_rule(ref: _RuleRef) -> PrunedRule:
    return PrunedRule(
        key=ref.key,
        pattern=ref.pattern,
        reason="duplicates inherited policy without changing the current scan tree",
    )


def _prune_candidate_group(
    document: TOMLDocument,
    candidates: Sequence[_RuleRef],
    *,
    context: _PruneContext,
    snapshot: Sequence[_CurrentTreeEntry],
    removed: list[PrunedRule],
) -> None:
    if not candidates:
        return

    variant = _parse_document(tomlkit.dumps(document))
    _delete_rule_group(variant, candidates)
    without = _matcher_for_document(variant, context=context)
    if _matches_current_tree_snapshot(without, snapshot):
        _delete_rule_group(document, candidates)
        removed.extend(_pruned_rule(ref) for ref in candidates)
        return

    if len(candidates) == 1:
        return
    midpoint = len(candidates) // 2
    _prune_candidate_group(
        document,
        candidates[:midpoint],
        context=context,
        snapshot=snapshot,
        removed=removed,
    )
    _prune_candidate_group(
        document,
        candidates[midpoint:],
        context=context,
        snapshot=snapshot,
        removed=removed,
    )


def _prune_current_tree(document: TOMLDocument, *, context: _PruneContext) -> list[PrunedRule]:
    inherited = _inherited_identities(context)
    if not inherited:
        return []

    candidates = tuple(ref for ref in _rule_refs(document) if (ref.core, ref.level) in inherited)
    if not candidates:
        return []

    baseline = _matcher_for_document(document, context=context)
    snapshot = _snapshot_current_tree(baseline, root=context.path.parent)
    removed: list[PrunedRule] = []
    _prune_candidate_group(
        document,
        candidates,
        context=context,
        snapshot=snapshot,
        removed=removed,
    )
    return removed


def _apply_contextual_pruning(
    document: TOMLDocument,
    *,
    path: Path,
    current_tree: bool,
    repo_root: Path | None,
    default_cfg: dict[str, object] | None,
) -> tuple[list[PrunedRule], list[str], list[str], tuple[str, ...]]:
    defaults = load_default_config() if default_cfg is None else default_cfg
    current_removed: list[PrunedRule] = []
    warnings: tuple[str, ...] = ()
    logical_path = logical_absolute(path)

    if current_tree:
        resolved_root = (
            logical_absolute(repo_root)
            if repo_root is not None
            else resolve_repo_root(cwd=logical_path.parent, paths=(logical_path.parent,))
        )
        inherited_general = _lower_general_config(logical_path, default_cfg=defaults)
        effective_target = dict(inherited_general)
        effective_target |= _target_data(document, logical_path)
        inherit_defaults = effective_target.get(CONFIG_INHERIT_DEFAULTS, True)
        if not isinstance(inherit_defaults, bool):
            msg = f"{CONFIG_INHERIT_DEFAULTS} must be true or false"
            raise ConfigPruneError(msg)
        context = _PruneContext(
            path=logical_path,
            repo_root=resolved_root,
            lower_layers=_lower_layers(
                logical_path,
                repo_root=resolved_root,
                default_cfg=defaults,
                include_defaults=inherit_defaults,
            ),
        )
        current_removed = _prune_current_tree(document, context=context)
        if current_removed:
            warnings = (
                (
                    "current-tree pruning depends on the repository paths that exist now; "
                    "future paths may make an inherited duplicate relevant again"
                ),
            )

    removed_empty_keys = _prune_empty_policy_keys(document, path=logical_path)
    inherited = _lower_general_config(logical_path, default_cfg=defaults)
    inherited |= _extends_base(document, logical_path)
    removed_settings = _prune_redundant_settings(document, inherited=inherited)
    return current_removed, removed_empty_keys, removed_settings, warnings


def inspect_config_pruning(
    path: Path,
    *,
    current_tree: bool = False,
    repo_root: Path | None = None,
    default_cfg: dict[str, object] | None = None,
) -> ConfigPruneResult:
    """Return the pruned representation of a config file without writing it."""
    try:
        original = path.read_text(encoding="utf-8")
    except OSError as err:
        msg = f"could not read {path}: {err}"
        raise ConfigPruneError(msg) from err

    document = _parse_document(original)
    _validate_canonical(document)
    removed = _prune_shadowed_rules(document)
    try:
        current_removed, removed_empty_keys, removed_settings, warnings = _apply_contextual_pruning(
            document,
            path=path,
            current_tree=current_tree,
            repo_root=repo_root,
            default_cfg=default_cfg,
        )
    except (OSError, ConfigLoadError) as err:
        msg = f"could not resolve inherited configuration for {path}: {err}"
        raise ConfigPruneError(msg) from err

    removed.extend(current_removed)
    if not removed and not removed_settings and not removed_empty_keys:
        return ConfigPruneResult(text=original, changed=False)

    return ConfigPruneResult(
        text=_clean_orphan_array_comments(tomlkit.dumps(document), original_text=original),
        changed=True,
        removed=tuple(removed),
        removed_settings=tuple(removed_settings),
        removed_empty_keys=tuple(removed_empty_keys),
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
