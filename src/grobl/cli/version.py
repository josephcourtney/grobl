"""CLI command reporting the installed grobl version."""

from __future__ import annotations

import click

from grobl import __version__, __version_source__


@click.command()
def version() -> None:
    """Print version and exit."""
    print(f"{__version__} ({__version_source__})")
