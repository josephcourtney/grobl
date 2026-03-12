"""CLI command reporting the installed grobl version."""

from __future__ import annotations

import click

from grobl import __version__


@click.command()
def version() -> None:
    """Print the installed grobl version."""
    print(__version__)
