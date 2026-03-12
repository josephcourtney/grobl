"""Thin Click wrapper for the ``grobl scan`` application workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from grobl.app.scan_command import run_scan_command

from .help_format import LiteralEpilogCommand
from .options import (
    add_config_option,
    add_ignore_options,
    add_ignore_policy_options,
    add_paths_argument,
    add_scan_output_options,
    add_scope_option,
)

if TYPE_CHECKING:
    from pathlib import Path

SCAN_EPILOG = """\
Examples:
  grobl scan .
    Scan the current directory using the default interactive behavior.

  grobl scan src tests --scope all
    Build one payload from multiple paths.

  grobl scan --copy
    Force the payload to the clipboard.

  grobl scan --json
    Emit a JSON payload to stdout with no summary.

  grobl scan --stdout --summary table
    Write the payload to stdout and keep the table summary on stderr.

  grobl scan --summary json --summary-to stdout --format none
    Emit only a machine-readable summary.

  grobl scan --no-tokens --no-inclusion-status --format json --output payload.json
    Omit selected metadata fields from emitted payload and summaries.

  grobl scan --exclude '*.min.js' --include 'vendor/**' src
    Exclude minified assets but re-include selected sources for this run.

  grobl explain docs --include-content 'docs/**'
    Verify why docs content is included or excluded before scanning.
"""


@click.command(cls=LiteralEpilogCommand, epilog=SCAN_EPILOG)
@add_config_option
@add_ignore_policy_options
@add_ignore_options
@add_scan_output_options
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
    config_path: Path | None,
    ignore_defaults: bool,
    no_ignore_config: bool,
    no_ignore: bool,
    ignore_policy: str,
    payload_format: str,
    copy: bool,
    output: Path | None,
    write_to_stdout: bool,
    json_mode: bool,
    summary: str,
    summary_style: str | None,
    summary_to: str,
    summary_output: Path | None,
    show_lines: bool,
    show_chars: bool,
    show_tokens: bool,
    show_inclusion_status: bool,
    scope: str,
    paths: tuple[Path, ...],
) -> None:
    """Build a prompt-ready snapshot of a directory tree and file contents."""
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
        config_path=config_path,
        ignore_defaults=ignore_defaults,
        no_ignore_config=no_ignore_config,
        no_ignore=no_ignore,
        ignore_policy=ignore_policy,
        payload_format=payload_format,
        copy=copy,
        output=output,
        write_to_stdout=write_to_stdout,
        json_mode=json_mode,
        summary=summary,
        summary_style=summary_style,
        summary_to=summary_to,
        summary_output=summary_output,
        show_lines=show_lines,
        show_chars=show_chars,
        show_tokens=show_tokens,
        show_inclusion_status=show_inclusion_status,
        scope=scope,
        paths=paths,
    )
