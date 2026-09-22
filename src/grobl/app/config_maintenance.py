"""Read-only detection of legacy project configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from grobl.config_loading import LEGACY_TOML_CONFIG
from grobl.config_migration import ConfigMigrationError, migrate_config_text
from grobl.ignore import discover_grobl_toml_files

if TYPE_CHECKING:
    from pathlib import Path


def _candidate_configs(
    *,
    repo_root: Path,
    scan_paths: tuple[Path, ...],
    explicit_config: Path | None,
) -> tuple[Path, ...]:
    candidates = discover_grobl_toml_files(repo_root=repo_root, scan_paths=scan_paths)
    legacy_path = (repo_root / LEGACY_TOML_CONFIG).resolve(strict=False)
    if legacy_path.exists() and legacy_path not in candidates:
        candidates.append(legacy_path)
    if explicit_config is not None:
        explicit = explicit_config.resolve(strict=False)
        if explicit.exists() and explicit not in candidates:
            candidates.append(explicit)
    return tuple(candidates)


def warn_legacy_project_configs(
    *,
    repo_root: Path,
    scan_paths: tuple[Path, ...],
    explicit_config: Path | None,
) -> None:
    """Warn about legacy config without modifying files.

    Read-oriented commands must never migrate, back up, or prune configuration.
    Those operations belong exclusively to grobl config migrate and
    grobl config prune.
    """
    for path in _candidate_configs(
        repo_root=repo_root,
        scan_paths=scan_paths,
        explicit_config=explicit_config,
    ):
        try:
            result = migrate_config_text(path.read_text(encoding="utf-8"))
        except (OSError, ConfigMigrationError) as err:
            click.echo(f"warning: could not inspect legacy configuration {path}: {err}", err=True)
            continue
        if not result.changed:
            continue
        click.echo(
            (
                f"warning: {path} uses the legacy inclusion schema; "
                f"run 'grobl config migrate {path}' to update it"
            ),
            err=True,
        )
