"""CLI command that bootstraps a default configuration file."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from grobl.app.command_support import MAX_REF_PREVIEW, _scan_for_legacy_references
from grobl.app.config_defaults import TOML_CONFIG, write_default_config
from grobl.app.config_loading import LEGACY_TOML_CONFIG

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
        write_default_config(target)
        print(f"Wrote default config to {new}")
    except OSError as e:
        print(f"Failed to write '{TOML_CONFIG}': {e}", file=sys.stderr)
        raise SystemExit(1) from e

    refs = _scan_for_legacy_references(target)
    if refs:
        print(f"Heads up: found {len(refs)} reference(s) to '{LEGACY_TOML_CONFIG}' in this repository:")
        for p, ln, text in refs[:50]:
            print(f"  - {p}:{ln}: {text}")
        if len(refs) > MAX_REF_PREVIEW:
            print("  ... (truncated)")
        print("Update these to '.grobl.toml' to avoid confusion.")
