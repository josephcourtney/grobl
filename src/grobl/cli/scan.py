"""CLI command implementation for the ``grobl scan`` workflow."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from grobl.config import load_and_adjust_config
from grobl.constants import EXIT_CONFIG, OutputMode, SummaryFormat, TableStyle
from grobl.errors import ConfigLoadError, PathNotFoundError
from grobl.output import build_writer_from_config
from grobl.tty import resolve_table_style
from grobl.utils import find_common_ancestor

from .common import (
    ScanParams,
    _execute_with_handling,
    _maybe_offer_legacy_migration,
    _maybe_warn_on_common_heavy_dirs,
)


@click.command()
@click.option(
    "--yes",
    is_flag=True,
    help="Assume 'yes' for interactive prompts (skip heavy-dir confirmation).",
)
@click.option("--ignore-defaults", "-I", is_flag=True, help="Ignore bundled default exclude patterns")
@click.option(
    "--no-ignore",
    is_flag=True,
    help="Disable all ignore patterns (overrides defaults and config)",
)
@click.option(
    "--no-clipboard",
    is_flag=True,
    help="Print output to stdout instead of copying to clipboard",
)
@click.option("--output", type=click.Path(path_type=Path), help="Write output to a file")
@click.option("--add-ignore", multiple=True, help="Additional ignore pattern for this run")
@click.option("--remove-ignore", multiple=True, help="Ignore pattern to remove for this run")
@click.option(
    "--ignore-file",
    multiple=True,
    type=click.Path(path_type=Path),
    help="Read ignore patterns from file (one per line)",
)
@click.option("--config", "config_path", type=click.Path(path_type=Path), help="Explicit config file path")
@click.option("--quiet", is_flag=True, help="Suppress human summary output")
@click.option(
    "--format",
    "fmt",
    type=click.Choice([f.value for f in SummaryFormat], case_sensitive=False),
    default=SummaryFormat.HUMAN.value,
    help="Summary output format",
)
@click.option(
    "--mode",
    type=click.Choice([m.value for m in OutputMode], case_sensitive=False),
    default=OutputMode.ALL.value,
    help="Output mode",
)
@click.option(
    "--table",
    type=click.Choice([t.value for t in TableStyle], case_sensitive=False),
    default=TableStyle.AUTO.value,
    help="Summary table style (auto/full/compact/none)",
)
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def scan(
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
    """Run a directory scan based on CLI flags and paths, then emit/copy output."""
    params = ScanParams(
        ignore_defaults=ignore_defaults,
        no_ignore=no_ignore,
        no_clipboard=no_clipboard,
        output=output,
        add_ignore=add_ignore,
        remove_ignore=remove_ignore,
        add_ignore_file=ignore_file,
        mode=OutputMode(mode),
        table=TableStyle(table),
        config_path=config_path,
        quiet=quiet,
        fmt=SummaryFormat(fmt),
        paths=paths or (Path(),),
    )

    cwd = Path()
    _maybe_offer_legacy_migration(cwd, assume_yes=yes)
    _maybe_warn_on_common_heavy_dirs(
        paths=params.paths, ignore_defaults=params.ignore_defaults, assume_yes=yes
    )

    try:
        common_base = find_common_ancestor(list(params.paths) or [cwd])
    except (ValueError, PathNotFoundError):
        common_base = cwd

    try:
        cfg = load_and_adjust_config(
            base_path=common_base,
            explicit_config=params.config_path,
            ignore_defaults=params.ignore_defaults,
            add_ignore=params.add_ignore,
            remove_ignore=params.remove_ignore,
            add_ignore_files=params.add_ignore_file,
            no_ignore=params.no_ignore,
        )
    except ConfigLoadError as err:
        print(err, file=sys.stderr)
        raise SystemExit(EXIT_CONFIG) from err

    write_fn = build_writer_from_config(cfg=cfg, no_clipboard_flag=params.no_clipboard, output=params.output)
    actual_table = resolve_table_style(params.table)

    if (
        params.fmt is SummaryFormat.HUMAN
        and not params.quiet
        and params.mode is OutputMode.SUMMARY
        and actual_table is TableStyle.NONE
    ):
        print("warning: --mode summary with --table none produces no output", file=sys.stderr)

    summary, summary_json = _execute_with_handling(
        params=params, cfg=cfg, cwd=cwd, write_fn=write_fn, table=actual_table
    )

    if not params.quiet:
        try:
            if params.fmt is SummaryFormat.HUMAN and summary:
                print(summary, end="")
            elif params.fmt is SummaryFormat.JSON and params.mode is OutputMode.SUMMARY:
                print(json.dumps(summary_json, sort_keys=True, indent=2))
        except BrokenPipeError:
            try:
                sys.stdout.close()
            finally:
                raise SystemExit(0)
