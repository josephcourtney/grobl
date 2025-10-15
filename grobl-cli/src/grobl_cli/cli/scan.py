"""CLI command for directory scanning — thin wrapper around service layer."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import click
from grobl.constants import OutputMode, SummaryFormat, TableStyle

from grobl_cli.service.scan_runner import ScanCommandParams, run_scan_command
from grobl_cli.tty import resolve_table_style, stdout_is_tty


@click.command()
@click.option("--yes", is_flag=True, help="Assume 'yes' for heavy-dir prompts.")
@click.option("--ignore-defaults", "-I", is_flag=True, help="Ignore bundled default exclude patterns")
@click.option("--no-ignore", is_flag=True, help="Disable all ignore patterns")
@click.option("--no-clipboard", is_flag=True, help="Disable clipboard output")
@click.option("--output", type=click.Path(path_type=Path), help="Write output to a file")
@click.option("--add-ignore", multiple=True, help="Add extra ignore patterns")
@click.option("--remove-ignore", multiple=True, help="Remove ignore patterns")
@click.option(
    "--ignore-file",
    multiple=True,
    type=click.Path(path_type=Path),
    help="Read ignore patterns from file",
)
@click.option("--config", "config_path", type=click.Path(path_type=Path), help="Explicit config path")
@click.option("--quiet", is_flag=True, help="Suppress human summary output")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["human"], case_sensitive=False),
    default="human",
    help="Summary output format",
)
@click.option(
    "--mode",
    type=click.Choice(["summary", "tree", "files", "all"], case_sensitive=False),
    default="summary",
    help="Output mode (default: summary).",
)
@click.option(
    "--table",
    type=click.Choice(["auto", "full", "compact", "none"], case_sensitive=False),
    default="auto",
    help="Summary table style",
)
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
@click.pass_context
def scan(
    ctx: click.Context,
    *,
    ignore_defaults: bool,
    no_ignore: bool,
    no_clipboard: bool,
    output: Path | None,
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
    ignore_file: tuple[Path, ...],
    mode: str,
    table: str,
    config_path: Path | None,
    fmt: str,
    quiet: bool,
    paths: tuple[Path, ...],
    yes: bool,
) -> None:
    """Run a directory scan and emit the configured outputs."""
    chosen_mode = OutputMode(mode)
    chosen_table = TableStyle(table)
    chosen_fmt = SummaryFormat(fmt)

    actual_table = resolve_table_style(chosen_table)
    if chosen_mode is OutputMode.SUMMARY and actual_table is TableStyle.NONE:
        msg = "No output would be produced. Avoid combinations like '--mode summary --table none'"
        raise click.UsageError(msg)

    params = ScanCommandParams.from_click(
        ctx=ctx,
        ignore_defaults=ignore_defaults,
        no_ignore=no_ignore,
        no_clipboard=no_clipboard,
        output=output,
        add_ignore=add_ignore,
        remove_ignore=remove_ignore,
        ignore_file=ignore_file,
        mode=chosen_mode.value,
        table=chosen_table.value,
        config_path=config_path,
        fmt=chosen_fmt.value,
        quiet=quiet,
        paths=paths,
        yes=yes,
    )
    result = run_scan_command(params)
    if result and not params.quiet and params.fmt == SummaryFormat.HUMAN.value:
        try:
            click.echo(result)
        except BrokenPipeError:
            try:
                sys.stdout.close()
            finally:
                raise SystemExit(0)


scan_with_tty = cast("Any", scan)
scan_with_tty.stdout_is_tty = stdout_is_tty
