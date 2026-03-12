"""Thin Click wrapper for the ``grobl scan`` application workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from grobl.app.scan_command import run_scan_command

from .options import add_ignore_options, add_paths_argument, add_scope_option

if TYPE_CHECKING:
    from pathlib import Path

SCAN_EPILOG = """\
Examples:
  grobl scan .
  grobl scan src tests --scope all
  grobl scan --format llm --copy
  grobl scan --format json --output payload.json
  grobl scan --summary json --summary-to stdout
  grobl scan --ignore-policy defaults
  grobl scan --ignore-policy none
  grobl scan --add-ignore '*.min.js' --unignore 'vendor/**' src
  grobl explain README.md --format json
  grobl explain docs --include-content 'docs/**'
"""


@click.command(epilog=SCAN_EPILOG)
@add_ignore_options
@add_scope_option
@add_paths_argument
@click.pass_context
def scan(
    ctx: click.Context,
    *,
    exclude: tuple[str, ...],
    include: tuple[str, ...],
    exclude_file: tuple[Path, ...],
    include_file: tuple[Path, ...],
    exclude_tree: tuple[str, ...],
    include_tree: tuple[str, ...],
    exclude_content: tuple[str, ...],
    include_content: tuple[str, ...],
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
    unignore: tuple[str, ...],
    ignore_file: tuple[Path, ...],
    scope: str,
    paths: tuple[Path, ...],
) -> None:
    """Run a directory scan and delegate orchestration to the application layer."""
    run_scan_command(
        ctx=ctx,
        exclude=exclude,
        include=include,
        exclude_file=exclude_file,
        include_file=include_file,
        exclude_tree=exclude_tree,
        include_tree=include_tree,
        exclude_content=exclude_content,
        include_content=include_content,
        add_ignore=add_ignore,
        remove_ignore=remove_ignore,
        unignore=unignore,
        ignore_file=ignore_file,
        scope=scope,
        paths=paths,
    )
