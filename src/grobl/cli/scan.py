"""CLI command implementation for the ``grobl scan`` workflow."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from grobl.config import load_and_adjust_config, resolve_config_base
from grobl.constants import (
    EXIT_CONFIG,
    ContentScope,
    PayloadFormat,
    SummaryDestination,
    SummaryFormat,
    TableStyle,
)
from grobl.errors import ConfigLoadError
from grobl.output import build_writer_from_config
from grobl.tty import resolve_table_style, stdout_is_tty
from grobl.utils import resolve_repo_root

from .common import (
    ScanParams,
    _execute_with_handling,
    exit_on_broken_pipe,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@click.command()
@click.option("--ignore-defaults", "-I", is_flag=True, help="Ignore bundled default exclude patterns")
@click.option(
    "--no-ignore",
    is_flag=True,
    help="Disable all ignore patterns (overrides defaults and config)",
)
@click.option("--add-ignore", multiple=True, help="Additional ignore pattern for this run")
@click.option("--remove-ignore", multiple=True, help="Ignore pattern to remove for this run")
@click.option("--unignore", multiple=True, help="Ignore exception pattern for this run")
@click.option(
    "--ignore-file",
    multiple=True,
    type=click.Path(path_type=Path),
    help="Read ignore patterns from file (one per line)",
)
@click.option("--config", "config_path", type=click.Path(path_type=Path), help="Explicit config file path")
@click.option(
    "--scope",
    type=click.Choice([s.value for s in ContentScope], case_sensitive=False),
    default=ContentScope.ALL.value,
    help="Content scope for payload generation",
)
@click.option(
    "--format",
    "payload_format",
    type=click.Choice([p.value for p in PayloadFormat], case_sensitive=False),
    default=PayloadFormat.LLM.value,
    help="Payload format to emit",
)
@click.option(
    "--summary",
    type=click.Choice([s.value for s in SummaryFormat], case_sensitive=False),
    default=SummaryFormat.AUTO.value,
    help="Summary mode to display",
)
@click.option(
    "--summary-style",
    type=click.Choice([t.value for t in TableStyle], case_sensitive=False),
    default=None,
    help="Summary table style (auto/full/compact; only valid with --summary table)",
)
@click.option(
    "--summary-to",
    type=click.Choice([d.value for d in SummaryDestination], case_sensitive=False),
    default=SummaryDestination.STDERR.value,
    help="Destination for summary output (defaults to stderr)",
)
@click.option(
    "--summary-output",
    type=click.Path(path_type=Path),
    help="File path to write the summary when --summary-to file is selected",
)
@click.option("--copy", is_flag=True, help="Copy the payload to the clipboard")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Write the payload to a file path (use '-' for stdout)",
)
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def scan(
    *,
    ignore_defaults: bool,
    no_ignore: bool,
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
    unignore: tuple[str, ...],
    ignore_file: tuple[Path, ...],
    config_path: Path | None,
    scope: str,
    payload_format: str,
    summary: str,
    summary_style: str | None,
    summary_to: str,
    summary_output: Path | None,
    copy: bool,
    output: Path | None,
    paths: tuple[Path, ...],
) -> None:
    """Run a directory scan based on CLI flags and paths, then emit/copy output."""
    ctx = click.get_current_context()

    cwd = Path()
    requested_paths = paths or (Path(),)

    repo_root = resolve_repo_root(cwd=cwd, paths=requested_paths)
    config_base = resolve_config_base(base_path=repo_root, explicit_config=config_path)

    if copy and output is not None:
        msg = "--copy cannot be combined with --output"
        raise click.UsageError(msg, ctx=ctx)
    payload_copy = copy or output is None

    actual_summary, actual_summary_style = _resolve_summary_settings(
        summary=summary,
        summary_style=summary_style,
        ctx=ctx,
    )
    params = ScanParams(
        ignore_defaults=ignore_defaults,
        output=output,
        no_ignore=no_ignore,
        add_ignore=add_ignore,
        remove_ignore=remove_ignore,
        unignore=unignore,
        add_ignore_file=ignore_file,
        scope=ContentScope(scope),
        summary_style=actual_summary_style,
        config_path=config_path,
        payload=PayloadFormat(payload_format),
        summary=actual_summary,
        payload_copy=payload_copy,
        payload_output=None if payload_copy else output,
        paths=requested_paths,
        repo_root=repo_root,
        pattern_base=config_base,
    )

    if params.payload is PayloadFormat.NONE and params.summary is SummaryFormat.NONE:
        msg = "payload and summary cannot both be 'none'"
        raise click.UsageError(msg, ctx=ctx)

    try:
        cfg = load_and_adjust_config(
            base_path=config_base,
            explicit_config=params.config_path,
            ignore_defaults=params.ignore_defaults,
            add_ignore=params.add_ignore,
            remove_ignore=params.remove_ignore,
            add_ignore_files=params.add_ignore_file,
            unignore=params.unignore,
            no_ignore=params.no_ignore,
        )
    except ConfigLoadError as err:
        print(err, file=sys.stderr)
        raise SystemExit(EXIT_CONFIG) from err

    summary, summary_json = _execute_with_handling(
        params=params,
        cfg=cfg,
        cwd=cwd,
        write_fn=build_writer_from_config(
            copy=params.payload_copy,
            output=params.payload_output,
        ),
        summary_style=params.summary_style,
    )

    summary_writer = _build_summary_writer(
        destination=_normalize_summary_destination(
            summary_to=summary_to,
            summary_output=summary_output,
            ctx=ctx,
        ),
        output=summary_output,
    )

    try:
        if params.summary is SummaryFormat.TABLE and summary:
            summary_writer(summary)
        elif params.summary is SummaryFormat.JSON:
            payload = json.dumps(summary_json, sort_keys=True, indent=2)
            summary_writer(f"{payload}\n")
    except BrokenPipeError:
        exit_on_broken_pipe()


def _build_summary_writer(
    *,
    destination: SummaryDestination,
    output: Path | None,
) -> Callable[[str], None]:
    """Return a writer that routes summary text to the requested destination."""
    if destination is SummaryDestination.STDERR:

        def _write(text: str) -> None:
            sys.stderr.write(text)
            sys.stderr.flush()

        return _write

    if destination is SummaryDestination.STDOUT:

        def _write(text: str) -> None:
            sys.stdout.write(text)
            sys.stdout.flush()

        return _write

    if output is None:
        msg = "summary file path must be provided when writing to file"
        raise ValueError(msg)

    def _write(text: str) -> None:
        output.write_text(text, encoding="utf-8")

    return _write


def _resolve_summary_settings(
    *,
    summary: str,
    summary_style: str | None,
    ctx: click.Context,
) -> tuple[SummaryFormat, TableStyle]:
    summary_choice = SummaryFormat(summary)
    if summary_style is not None and summary_choice is not SummaryFormat.TABLE:
        msg = "--summary-style is only valid when --summary table"
        raise click.UsageError(msg, ctx=ctx)

    if summary_choice is SummaryFormat.AUTO:
        actual_summary = SummaryFormat.TABLE if stdout_is_tty() else SummaryFormat.NONE
        requested_style = TableStyle.AUTO
    else:
        actual_summary = summary_choice
        requested_style = TableStyle(summary_style) if summary_style else TableStyle.AUTO

    if actual_summary is SummaryFormat.TABLE:
        actual_style = resolve_table_style(requested_style)
    else:
        actual_style = TableStyle.AUTO

    return actual_summary, actual_style


def _normalize_summary_destination(
    *,
    summary_to: str,
    summary_output: Path | None,
    ctx: click.Context,
) -> SummaryDestination:
    destination = SummaryDestination(summary_to)
    if destination is SummaryDestination.FILE and summary_output is None:
        msg = "--summary-output is required when --summary-to file"
        raise click.UsageError(msg, ctx=ctx)
    if summary_output is not None and destination is not SummaryDestination.FILE:
        msg = "--summary-output can only be used with --summary-to file"
        raise click.UsageError(msg, ctx=ctx)
    return destination
