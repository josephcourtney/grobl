"""CLI command implementation for the ``grobl scan`` workflow."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click
from click.core import ParameterSource

from grobl.config import load_and_adjust_config
from grobl.constants import EXIT_CONFIG, OutputMode, SummaryFormat, TableStyle
from grobl.errors import ConfigLoadError, PathNotFoundError
from grobl.output import ClipboardOutput, FileOutput, StdoutOutput, build_writer_from_config
from grobl.tty import clipboard_allowed, resolve_table_style, stdout_is_tty
from grobl.utils import find_common_ancestor

from .common import (
    ScanParams,
    _execute_with_handling,
    _maybe_offer_legacy_migration,
    _maybe_warn_on_common_heavy_dirs,
)


def _env_assume_yes() -> bool:
    value = os.environ.get("GROBL_ASSUME_YES", "").strip().lower()
    return value in {"1", "true", "yes"}


def _parameter_source(ctx: click.Context, name: str) -> ParameterSource:
    getter = getattr(ctx, "get_parameter_source", None)
    if getter is None:
        return ParameterSource.DEFAULT
    source = getter(name)
    return ParameterSource.DEFAULT if source is None else source


def _should_default_to_summary(ctx: click.Context) -> bool:
    if not stdout_is_tty():
        return False
    tracked = ("mode", "fmt", "table", "quiet", "output", "no_clipboard")
    return all(_parameter_source(ctx, name) is ParameterSource.DEFAULT for name in tracked)


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
    """Run a directory scan based on CLI flags and paths, then emit/copy output."""
    assume_yes = yes or _env_assume_yes()

    chosen_mode = OutputMode(mode)
    chosen_fmt = SummaryFormat(fmt)
    chosen_table = TableStyle(table)

    if _should_default_to_summary(ctx):
        chosen_mode = OutputMode.SUMMARY

    params = ScanParams(
        ignore_defaults=ignore_defaults,
        no_ignore=no_ignore,
        no_clipboard=no_clipboard,
        output=output,
        add_ignore=add_ignore,
        remove_ignore=remove_ignore,
        add_ignore_file=ignore_file,
        mode=chosen_mode,
        table=chosen_table,
        config_path=config_path,
        quiet=quiet,
        fmt=chosen_fmt,
        paths=paths or (Path(),),
    )

    cwd = Path()
    _maybe_offer_legacy_migration(cwd, assume_yes=assume_yes)
    _maybe_warn_on_common_heavy_dirs(
        paths=params.paths, ignore_defaults=params.ignore_defaults, assume_yes=assume_yes
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

    allow_clipboard = clipboard_allowed(cfg, no_clipboard_flag=params.no_clipboard)
    write_fn = build_writer_from_config(
        cfg=cfg, no_clipboard_flag=params.no_clipboard, output=params.output
    )
    actual_table = resolve_table_style(params.table)

    if params.mode is OutputMode.SUMMARY and actual_table is TableStyle.NONE:
        msg = (
            "No output would be produced."
            " Avoid combinations like '--mode summary --table none'"
            " (and future '--payload none --emit none')."
            " Choose a visible summary table or emit JSON with --format json."
        )
        raise click.UsageError(msg)

    summary, summary_json = _execute_with_handling(
        params=params, cfg=cfg, cwd=cwd, write_fn=write_fn, table=actual_table
    )

    def _emit(content: str) -> None:
        if not content:
            return
        try:
            write_fn(content)
        except BrokenPipeError:
            try:
                sys.stdout.close()
            finally:
                raise SystemExit(0)

    if params.fmt is SummaryFormat.HUMAN and not params.quiet:
        if params.output:
            FileOutput(params.output).write(summary)
        if allow_clipboard:
            try:
                ClipboardOutput.write(summary)
            except Exception:
                pass
        try:
            StdoutOutput.write(summary)
        except BrokenPipeError:
            try:
                sys.stdout.close()
            finally:
                raise SystemExit(0)
    elif params.fmt is SummaryFormat.JSON and params.mode is OutputMode.SUMMARY:
        json_text = json.dumps(summary_json, sort_keys=True, indent=2)
        _emit(json_text)
