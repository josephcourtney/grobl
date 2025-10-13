"""CLI command that bootstraps a default configuration file."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from grobl.config import LEGACY_TOML_CONFIG, TOML_CONFIG, write_default_config

from .common import MAX_REF_PREVIEW, _default_confirm, _scan_for_legacy_references


@click.command()
@click.option(
    "--path",
    "target",
    type=click.Path(path_type=Path),
    default=Path(),
    help="Directory to initialize",
)
@click.option("--force", is_flag=True, help="Overwrite an existing config file")
@click.option(
    "--yes",
    is_flag=True,
    help="Assume 'yes' for interactive prompts (auto-migrate legacy filename and suppress questions).",
)
def init(*, target: Path, force: bool, yes: bool) -> None:
    """Create a default .grobl.toml in the target directory (no auto-creation elsewhere)."""
    target = target.resolve()
    legacy = target / LEGACY_TOML_CONFIG
    new = target / TOML_CONFIG

    if (
        legacy.exists()
        and not new.exists()
        and (
            yes
            or _default_confirm(
                f"Found legacy '{LEGACY_TOML_CONFIG}'. Rename to '{TOML_CONFIG}' "
                "instead of creating a new one? (y/N): "
            )
        )
    ):
        try:
            legacy.rename(new)
            print(f"Renamed '{LEGACY_TOML_CONFIG}' -> '{TOML_CONFIG}'.")
        except OSError as e:
            print(f"Could not rename legacy config: {e}", file=sys.stderr)
            raise SystemExit(1) from e

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
