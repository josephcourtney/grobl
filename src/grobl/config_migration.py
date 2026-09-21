"""Legacy configuration migration helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError

from grobl.constants import (
    CONFIG_EXCLUDE,
    CONFIG_EXCLUDE_CONTENT,
    CONFIG_EXCLUDE_PRINT,
    CONFIG_EXCLUDE_TREE,
    CONFIG_INCLUDE,
    CONFIG_TREE_ONLY,
)

CANONICAL_POLICY_KEYS = (CONFIG_EXCLUDE, CONFIG_TREE_ONLY, CONFIG_INCLUDE)
LEGACY_POLICY_KEYS = (CONFIG_EXCLUDE_TREE, CONFIG_EXCLUDE_PRINT, CONFIG_EXCLUDE_CONTENT)


class ConfigMigrationError(ValueError):
    """Raised when a configuration cannot be migrated safely."""


@dataclass(frozen=True, slots=True)
class ConfigMigrationResult:
    """Result of translating one TOML document."""

    text: str
    changed: bool
    warnings: tuple[str, ...] = ()


def _patterns(value: object, *, key: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        items = list(value)
        if all(isinstance(item, str) for item in items):
            return [item for item in items if isinstance(item, str)]
    msg = f"{key} must be a string or an array of strings"
    raise ConfigMigrationError(msg)


def _pattern_core(pattern: str) -> str:
    stripped = pattern.strip()
    return stripped[1:] if stripped.startswith("!") else stripped


def _tree_omission_cores(patterns: Sequence[str]) -> set[str]:
    """Return exact pattern cores whose final tree rule is restrictive."""
    final_state: dict[str, bool] = {}
    for pattern in patterns:
        stripped = pattern.strip()
        if not stripped or stripped.startswith("#"):
            continue
        final_state[_pattern_core(stripped)] = not stripped.startswith("!")
    return {core for core, omitted in final_state.items() if omitted}


def migrate_config_text(text: str) -> ConfigMigrationResult:
    """Translate legacy inclusion keys to the canonical three-state schema."""
    try:
        document = tomlkit.parse(text)
    except TOMLKitError as err:
        msg = f"invalid TOML: {err}"
        raise ConfigMigrationError(msg) from err

    canonical = [key for key in CANONICAL_POLICY_KEYS if key in document]
    legacy = [key for key in LEGACY_POLICY_KEYS if key in document]

    if canonical and legacy:
        canonical_names = ", ".join(canonical)
        legacy_names = ", ".join(legacy)
        msg = (
            "config mixes canonical and legacy inclusion keys "
            f"(canonical: {canonical_names}; legacy: {legacy_names})"
        )
        raise ConfigMigrationError(msg)

    if not legacy:
        return ConfigMigrationResult(text=text, changed=False)

    tree_present = CONFIG_EXCLUDE_TREE in document
    print_present = CONFIG_EXCLUDE_PRINT in document
    content_present = CONFIG_EXCLUDE_CONTENT in document

    tree_patterns = _patterns(document.get(CONFIG_EXCLUDE_TREE), key=CONFIG_EXCLUDE_TREE)
    print_patterns = _patterns(document.get(CONFIG_EXCLUDE_PRINT), key=CONFIG_EXCLUDE_PRINT)
    content_patterns = _patterns(document.get(CONFIG_EXCLUDE_CONTENT), key=CONFIG_EXCLUDE_CONTENT)

    warnings: list[str] = []
    if content_present:
        selected_content = content_patterns
        if print_present:
            warnings.append(
                "both exclude_print and exclude_content were present; "
                "exclude_content takes precedence to match the legacy parser"
            )
    else:
        selected_content = print_patterns

    omission_cores = _tree_omission_cores(tree_patterns)
    tree_only_patterns = [
        pattern for pattern in selected_content if _pattern_core(pattern) not in omission_cores
    ]

    if tree_patterns and selected_content:
        warnings.append(
            "legacy tree/content glob scopes can overlap in ways that grouped canonical rules "
            "cannot prove equivalent; exact-pattern tree omissions were preserved, but review "
            "overlapping glob patterns"
        )

    for key in LEGACY_POLICY_KEYS:
        if key in document:
            del document[key]

    if tree_present:
        document[CONFIG_EXCLUDE] = tree_patterns
    if print_present or content_present:
        document[CONFIG_TREE_ONLY] = tree_only_patterns

    return ConfigMigrationResult(
        text=tomlkit.dumps(document),
        changed=True,
        warnings=tuple(warnings),
    )


def migrate_config_file(
    path: Path,
    *,
    backup: bool = True,
) -> tuple[ConfigMigrationResult, Path | None]:
    """Migrate a config file in place and optionally preserve the original."""
    try:
        original = path.read_text(encoding="utf-8")
    except OSError as err:
        msg = f"could not read {path}: {err}"
        raise ConfigMigrationError(msg) from err

    result = migrate_config_text(original)
    if not result.changed:
        return result, None

    backup_path: Path | None = None
    if backup:
        backup_path = Path(f"{path}.bak")
        if backup_path.exists():
            msg = f"backup already exists: {backup_path}; remove it or use --no-backup"
            raise ConfigMigrationError(msg)
        try:
            backup_path.write_text(original, encoding="utf-8")
        except OSError as err:
            msg = f"could not write backup {backup_path}: {err}"
            raise ConfigMigrationError(msg) from err

    try:
        path.write_text(result.text, encoding="utf-8")
    except OSError as err:
        msg = f"could not write migrated config {path}: {err}"
        raise ConfigMigrationError(msg) from err

    return result, backup_path
