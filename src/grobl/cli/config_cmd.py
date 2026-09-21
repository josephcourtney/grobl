"""Configuration maintenance commands."""

from __future__ import annotations

from pathlib import Path

import click

from grobl.app.config_defaults import TOML_CONFIG
from grobl.config_migration import (
    ConfigMigrationError,
    migrate_config_file,
    migrate_config_text,
)

from .help_format import LiteralEpilogGroup

CONFIG_EPILOG = """\
Examples:
  grobl config migrate
    Migrate .grobl.toml in place and keep .grobl.toml.bak.

  grobl config migrate path/to/.grobl.toml --stdout
    Print the canonical form without changing the file.

  grobl config migrate --check
    Exit nonzero when the config still uses legacy inclusion keys.
"""


@click.group(name="config", cls=LiteralEpilogGroup, epilog=CONFIG_EPILOG)
def config_command() -> None:
    """Inspect and maintain grobl configuration files."""


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
    if to_stdout and check:
        raise click.UsageError("--stdout and --check cannot be used together")

    if check or to_stdout:
        try:
            source = path.read_text(encoding="utf-8")
            result = migrate_config_text(source)
        except (OSError, ConfigMigrationError) as err:
            raise click.ClickException(str(err)) from err

        if check:
            if result.changed:
                click.echo(f"{path} uses legacy inclusion keys", err=True)
                raise click.exceptions.Exit(1)
            click.echo(f"{path} is already canonical")
            return

        click.echo(result.text, nl=False)
        for warning in result.warnings:
            click.echo(f"warning: {warning}", err=True)
        return

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

    for warning in result.warnings:
        click.echo(f"warning: {warning}", err=True)
