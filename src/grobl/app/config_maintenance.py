"""Interactive maintenance of legacy project configuration."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from grobl.config_migration import (
    ConfigMigrationError,
    migrate_config_file,
    migrate_config_text,
)
from grobl.config_pruning import ConfigPruneError, inspect_config_pruning, prune_config_file
from grobl.ignore import discover_grobl_toml_files

if TYPE_CHECKING:
    from grobl.config_migration import ConfigMigrationResult


def _is_interactive(*, requested: bool | None) -> bool:
    if requested is not None:
        return requested
    return sys.stdin.isatty() and sys.stderr.isatty()


def _candidate_configs(
    *,
    repo_root: Path,
    scan_paths: tuple[Path, ...],
    explicit_config: Path | None,
) -> tuple[Path, ...]:
    candidates = discover_grobl_toml_files(repo_root=repo_root, scan_paths=scan_paths)
    if explicit_config is not None:
        explicit = explicit_config.resolve(strict=False)
        if explicit.exists() and explicit not in candidates:
            candidates.append(explicit)
    return tuple(candidates)


def _migration_preview(path: Path) -> ConfigMigrationResult | None:
    try:
        result = migrate_config_text(path.read_text(encoding="utf-8"))
    except (OSError, ConfigMigrationError) as err:
        click.echo(f"warning: could not inspect legacy configuration {path}: {err}", err=True)
        return None
    return result


def _emit_warnings(warnings: tuple[str, ...]) -> None:
    for warning in warnings:
        click.echo(f"warning: {warning}", err=True)


def _offer_structural_prune(path: Path, *, repo_root: Path) -> bool:
    try:
        result = inspect_config_pruning(path)
    except ConfigPruneError as err:
        click.echo(f"warning: could not inspect {path} for pruning: {err}", err=True)
        return False

    if result.changed:
        count = result.removal_count
        noun = "entry" if count == 1 else "entries"
        click.echo(f"{path} contains {count} structurally redundant config {noun}.", err=True)
        if not click.confirm("Prune those entries now?", default=True, err=True):
            return False
        try:
            pruned, _ = prune_config_file(path, backup=False)
        except ConfigPruneError as err:
            click.echo(f"warning: could not prune {path}: {err}", err=True)
            return False
        _emit_warnings(pruned.warnings)
        click.echo(f"Pruned {path}.", err=True)

    return _offer_current_tree_prune(path, repo_root=repo_root)


def _offer_current_tree_prune(path: Path, *, repo_root: Path) -> bool:
    try:
        result = inspect_config_pruning(path, current_tree=True, repo_root=repo_root)
    except ConfigPruneError as err:
        click.echo(f"warning: could not inspect {path} for current-tree pruning: {err}", err=True)
        return False
    if not result.changed:
        return True

    count = result.removal_count
    noun = "entry" if count == 1 else "entries"
    click.echo(
        (
            f"{count} additional config {noun} can be removed for the current repository tree. "
            "These removals depend on the paths that exist now."
        ),
        err=True,
    )
    if not click.confirm("Also apply current-tree pruning?", default=False, err=True):
        return True

    try:
        pruned, _ = prune_config_file(path, current_tree=True, backup=False)
    except ConfigPruneError as err:
        click.echo(f"warning: could not apply current-tree pruning to {path}: {err}", err=True)
        return False
    _emit_warnings(pruned.warnings)
    click.echo(f"Applied current-tree pruning to {path}.", err=True)
    return True


def _migrate_interactively(path: Path, *, repo_root: Path) -> None:
    click.echo(f"Legacy Grobl inclusion schema found in {path}.", err=True)
    if not click.confirm(
        "Migrate it to the canonical exclude/tree_only/include schema?",
        default=True,
        err=True,
    ):
        return

    try:
        result, backup_path = migrate_config_file(path, backup=True)
    except ConfigMigrationError as err:
        click.echo(f"warning: could not migrate {path}: {err}", err=True)
        return

    if backup_path is None:
        click.echo(f"Migrated {path}.", err=True)
    else:
        click.echo(f"Migrated {path} (backup: {backup_path}).", err=True)
    _emit_warnings(result.warnings)
    _offer_structural_prune(path, repo_root=repo_root)


def maintain_legacy_project_configs(
    *,
    repo_root: Path,
    scan_paths: tuple[Path, ...],
    explicit_config: Path | None,
    interactive: bool | None,
) -> None:
    """Offer migration/pruning for legacy project configs without blocking scripts."""
    candidates = _candidate_configs(
        repo_root=repo_root,
        scan_paths=scan_paths,
        explicit_config=explicit_config,
    )
    interactive_run = _is_interactive(requested=interactive)

    for path in candidates:
        result = _migration_preview(path)
        if result is None or not result.changed:
            continue
        if interactive_run:
            _migrate_interactively(path, repo_root=repo_root)
        else:
            click.echo(
                (
                    f"warning: {path} uses the legacy inclusion schema; "
                    "run 'grobl config migrate' to update it"
                ),
                err=True,
            )
