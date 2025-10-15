"""CLI command that bootstraps a default configuration file."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from grobl_config import TOML_CONFIG, write_default_config


@click.command()
@click.option(
    "--path",
    "target",
    type=click.Path(path_type=Path),
    default=Path(),
    help="Directory to initialize",
)
@click.option("--force", is_flag=True, help="Overwrite an existing config file")
def init(*, target: Path, force: bool) -> None:
    """Create a default .grobl.toml in the target directory (no auto-creation elsewhere)."""
    target = target.resolve()
    config_path = target / TOML_CONFIG

    if config_path.exists() and not force:
        print(
            f"Config '{TOML_CONFIG}' already exists at {target}. Use --force to overwrite.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        write_default_config(target)
        print(f"Wrote default config to {config_path}")
    except OSError as e:
        print(f"Failed to write '{TOML_CONFIG}': {e}", file=sys.stderr)
        raise SystemExit(1) from e
