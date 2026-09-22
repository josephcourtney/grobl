"""Configuration maintenance commands."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

from grobl.app.config_defaults import TOML_CONFIG
from grobl.config_migration import (
    ConfigMigrationError,
    migrate_config_file,
    migrate_config_text,
)
from grobl.config_pruning import (
    ConfigPruneError,
    inspect_config_pruning,
    prune_config_file,
)

from .help_format import LiteralEpilogGroup

if TYPE_CHECKING:
    from grobl.config_migration import ConfigMigrationResult
    from grobl.config_pruning import ConfigPruneResult

CONFIG_EPILOG = """\
Examples:
  grobl config migrate
    Migrate .grobl.toml in place and keep .grobl.toml.bak.

  grobl config migrate path/to/.grobl.toml --stdout
    Print the canonical form without changing the file.

  grobl config prune
    Remove rules that are provably shadowed within .grobl.toml.

  grobl config prune --current-tree
    Also remove exact inherited duplicates that do not affect the current scan tree.
"""


@click.group(name="config", cls=LiteralEpilogGroup, epilog=CONFIG_EPILOG)
def config_command() -> None:
    """Inspect and maintain grobl configuration files."""


def _read_migration(path: Path) -> ConfigMigrationResult:
    try:
        source = path.read_text(encoding="utf-8")
        return migrate_config_text(source)
    except (OSError, ConfigMigrationError) as err:
        raise click.ClickException(str(err)) from err


def _emit_migration_warnings(result: ConfigMigrationResult) -> None:
    for warning in result.warnings:
        click.echo(f"warning: {warning}", err=True)


def _run_migration_check(path: Path, result: ConfigMigrationResult) -> None:
    if result.changed:
        msg = f"{path} uses legacy inclusion keys"
        raise click.ClickException(msg)
    click.echo(f"{path} is already canonical")


def _run_migration_preview(path: Path, *, check: bool) -> None:
    result = _read_migration(path)
    if check:
        _run_migration_check(path, result)
        return
    click.echo(result.text, nl=False)
    _emit_migration_warnings(result)


def _run_migration_in_place(path: Path, *, backup: bool) -> None:
    try:
        result, backup_path = migrate_config_file(path, backup=backup)
    except ConfigMigrationError as err:
        raise click.ClickException(str(err)) from err

    if not result.changed:
        click.echo(f"{path} is already canonical")
        return

    if backup_path is None:
        click.echo(f"Migrated {path}")
    else:
        click.echo(f"Migrated {path} (backup: {backup_path})")
    _emit_migration_warnings(result)


def _read_pruning(path: Path, *, current_tree: bool) -> ConfigPruneResult:
    try:
        return inspect_config_pruning(path, current_tree=current_tree)
    except ConfigPruneError as err:
        raise click.ClickException(str(err)) from err


def _emit_prune_warnings(result: ConfigPruneResult) -> None:
    for warning in result.warnings:
        click.echo(f"warning: {warning}", err=True)


def _run_prune_check(path: Path, result: ConfigPruneResult) -> None:
    if result.changed:
        count = len(result.removed)
        msg = f"{path} contains {count} redundant inclusion rule(s)"
        raise click.ClickException(msg)
    click.echo(f"{path} has no redundant inclusion rules")


def _run_prune_preview(path: Path, *, current_tree: bool, check: bool) -> None:
    result = _read_pruning(path, current_tree=current_tree)
    if check:
        _run_prune_check(path, result)
        return
    click.echo(result.text, nl=False)
    _emit_prune_warnings(result)


def _run_prune_in_place(path: Path, *, current_tree: bool, backup: bool) -> None:
    try:
        result, backup_path = prune_config_file(
            path,
            current_tree=current_tree,
            backup=backup,
        )
    except ConfigPruneError as err:
        raise click.ClickException(str(err)) from err

    if not result.changed:
        click.echo(f"{path} has no redundant inclusion rules")
        return

    count = len(result.removed)
    if backup_path is None:
        click.echo(f"Pruned {path} ({count} rules)")
    else:
        click.echo(f"Pruned {path} ({count} rules; backup: {backup_path})")
    _emit_prune_warnings(result)


def _validate_output_modes(*, to_stdout: bool, check: bool) -> None:
    if to_stdout and check:
        msg = "--stdout and --check cannot be used together"
        raise click.UsageError(msg)


@config_command.command("migrate")
@click.argument(
    "path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=Path(TOML_CONFIG),
    required=False,
)
@click.option(
    "--stdout",
    "to_stdout",
    is_flag=True,
    help="Print migrated TOML instead of writing the file.",
)
@click.option(
    "--check",
    is_flag=True,
    help="Do not write; exit 1 when migration is needed.",
)
@click.option(
    "--backup/--no-backup",
    default=True,
    show_default=True,
    help="Keep the original as PATH.bak when writing in place.",
)
def migrate(path: Path, *, to_stdout: bool, check: bool, backup: bool) -> None:
    """Translate legacy inclusion keys to exclude/tree_only/include."""
    _validate_output_modes(to_stdout=to_stdout, check=check)
    if check or to_stdout:
        _run_migration_preview(path, check=check)
        return
    _run_migration_in_place(path, backup=backup)


@config_command.command("prune")
@click.argument(
    "path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=Path(TOML_CONFIG),
    required=False,
)
@click.option(
    "--current-tree",
    is_flag=True,
    help=(
        "Also remove exact inherited duplicates when doing so leaves the current "
        "traversable tree's effective states unchanged."
    ),
)
@click.option(
    "--stdout",
    "to_stdout",
    is_flag=True,
    help="Print pruned TOML instead of writing the file.",
)
@click.option(
    "--check",
    is_flag=True,
    help="Do not write; exit 1 when redundant rules are found.",
)
@click.option(
    "--backup/--no-backup",
    default=True,
    show_default=True,
    help="Keep the original as PATH.bak when writing in place.",
)
def prune(
    path: Path,
    *,
    current_tree: bool,
    to_stdout: bool,
    check: bool,
    backup: bool,
) -> None:
    """Remove redundant canonical inclusion rules conservatively."""
    _validate_output_modes(to_stdout=to_stdout, check=check)
    if check or to_stdout:
        _run_prune_preview(path, current_tree=current_tree, check=check)
        return
    _run_prune_in_place(path, current_tree=current_tree, backup=backup)
