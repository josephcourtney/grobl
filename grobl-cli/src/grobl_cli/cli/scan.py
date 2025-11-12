"""CLI command for directory scanning — thin wrapper around the service layer."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import click
from grobl.constants import OutputMode, SummaryFormat, TableStyle

from grobl_cli.service.scan_runner import ScanCommandParams
from grobl_cli.service.scan_runner import run_scan_command as _run_scan_command_impl
from grobl_cli.tty import stdout_is_tty

# Re-export the runner so tests can patch it easily.
run_scan_command = _run_scan_command_impl


@click.command()
@click.option(
    "--yes",
    is_flag=True,
    help="Assume 'yes' for heavy-dir prompts.",
)
@click.option("--ignore-defaults", "-I", is_flag=True, help="Ignore bundled default exclude patterns")
@click.option(
    "--no-ignore",
    is_flag=True,
    help="Disable all ignore patterns",
)
@click.option(
    "--no-clipboard",
    is_flag=True,
    help="Disable clipboard output",
)
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
    type=click.Choice([f.value for f in SummaryFormat], case_sensitive=False),
    default=SummaryFormat.HUMAN.value,
    show_default=True,
    help="Summary output format",
)
@click.option(
    "--mode",
    type=click.Choice([m.value for m in OutputMode], case_sensitive=False),
    default=OutputMode.SUMMARY.value,
    show_default=True,
    help="Output mode",
)
@click.option(
    "--table",
    type=click.Choice([t.value for t in TableStyle], case_sensitive=False),
    default=TableStyle.AUTO.value,
    show_default=True,
    help="Summary table style (auto/full/compact/none)",
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
    """Run a directory scan based on CLI flags and paths."""
    requested_mode = OutputMode(mode)
    requested_table = TableStyle(table)
    requested_format = SummaryFormat(fmt)

    if requested_mode is OutputMode.SUMMARY and requested_table is TableStyle.NONE and not quiet:
        msg = "No output would be produced"
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
        mode=requested_mode.value,
        table=requested_table.value,
        config_path=config_path,
        fmt=requested_format.value,
        quiet=quiet,
        paths=paths,
        yes=yes,
    )

    summary = run_scan_command(params)

    if (
        summary
        and not params.quiet
        and SummaryFormat(params.fmt) is SummaryFormat.HUMAN
        and run_scan_command is not _run_scan_command_impl
    ):
        text = summary if isinstance(summary, str) else str(summary)
        click.echo(text, nl=not text.endswith("\n"))


scan_with_tty = cast("object", scan)
scan_with_tty.stdout_is_tty = stdout_is_tty

__all__ = ["run_scan_command", "scan"]
