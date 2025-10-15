"""CLI command for directory scanning — thin wrapper around service layer."""

from __future__ import annotations

from pathlib import Path

import click

from grobl_cli.service.scan_runner import ScanCommandParams, run_scan_command


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
    params = ScanCommandParams.from_click(
        ctx=ctx,
        ignore_defaults=ignore_defaults,
        no_ignore=no_ignore,
        no_clipboard=no_clipboard,
        output=output,
        add_ignore=add_ignore,
        remove_ignore=remove_ignore,
        ignore_file=ignore_file,
        mode=mode,
        table=table,
        config_path=config_path,
        fmt=fmt,
        quiet=quiet,
        paths=paths,
        yes=yes,
    )
    run_scan_command(params)
