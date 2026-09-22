"""CLI command that bootstraps a minimal project configuration file."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from grobl.config_defaults import TOML_CONFIG, write_starter_config
from grobl.constants import EXIT_IO

from .help_format import LiteralEpilogCommand

INIT_EPILOG = """\
Examples:
  grobl init
    Create `.grobl.toml` in the current directory.

  grobl init --path ..
    Initialize the parent directory instead.

  grobl init --force
    Overwrite an existing config file.
"""


@click.command(cls=LiteralEpilogCommand, epilog=INIT_EPILOG)
@click.option(
    "--path",
    "target",
    type=click.Path(path_type=Path),
    default=Path(),
    help="Directory to initialize",
)
@click.option("--force", is_flag=True, help="Overwrite an existing config file")
def init(*, target: Path, force: bool) -> None:
    """Create a starter `.grobl.toml` in a target directory."""
    target = target.resolve()
    new = target / TOML_CONFIG

    if new.exists() and not force:
        print(
            f"Config '{TOML_CONFIG}' already exists at {target}. Use --force to overwrite.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        write_starter_config(target)
        print(f"Wrote starter config to {new}")
    except OSError as e:
        print(f"error: cannot write config {new}: {e}", file=sys.stderr)
        raise SystemExit(EXIT_IO) from e
