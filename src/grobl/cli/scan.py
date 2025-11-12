"""CLI command implementation for the ``grobl scan`` workflow."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from grobl.config import load_and_adjust_config
from grobl.constants import (
    EXIT_CONFIG,
    ContentScope,
    PayloadFormat,
    PayloadSink,
    SummaryFormat,
    TableStyle,
)
from grobl.errors import ConfigLoadError, PathNotFoundError
from grobl.output import build_writer_from_config
from grobl.tty import resolve_table_style
from grobl.utils import find_common_ancestor

from .common import (
    ScanParams,
    _execute_with_handling,
)


@click.command()
@click.option("--ignore-defaults", "-I", is_flag=True, help="Ignore bundled default exclude patterns")
@click.option(
    "--no-ignore",
    is_flag=True,
    help="Disable all ignore patterns (overrides defaults and config)",
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
@click.option(
    "--scope",
    type=click.Choice([s.value for s in ContentScope], case_sensitive=False),
    default=ContentScope.ALL.value,
    help="Content scope for payload generation",
)
@click.option(
    "--payload",
    type=click.Choice([p.value for p in PayloadFormat], case_sensitive=False),
    default=PayloadFormat.LLM.value,
    help="Payload format to emit",
)
@click.option(
    "--summary",
    type=click.Choice([s.value for s in SummaryFormat], case_sensitive=False),
    default=SummaryFormat.HUMAN.value,
    help="Summary format to display",
)
@click.option(
    "--summary-style",
    type=click.Choice([t.value for t in TableStyle], case_sensitive=False),
    default=TableStyle.AUTO.value,
    help="Summary table style (auto/full/compact/none)",
)
@click.option(
    "--sink",
    type=click.Choice([s.value for s in PayloadSink], case_sensitive=False),
    default=PayloadSink.AUTO.value,
    help="Destination for machine-readable payload output",
)
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def scan(
    *,
    ignore_defaults: bool,
    no_ignore: bool,
    output: Path | None,
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
    ignore_file: tuple[Path, ...],
    scope: str,
    payload: str,
    summary: str,
    summary_style: str,
    sink: str,
    config_path: Path | None,
    paths: tuple[Path, ...],
) -> None:
    """Run a directory scan based on CLI flags and paths, then emit/copy output."""
    ctx = click.get_current_context()

    params = ScanParams(
        ignore_defaults=ignore_defaults,
        no_ignore=no_ignore,
        output=output,
        add_ignore=add_ignore,
        remove_ignore=remove_ignore,
        add_ignore_file=ignore_file,
        scope=ContentScope(scope),
        summary_style=TableStyle(summary_style),
        config_path=config_path,
        payload=PayloadFormat(payload),
        summary=SummaryFormat(summary),
        sink=PayloadSink(sink),
        paths=paths or (Path(),),
    )

    if params.payload is PayloadFormat.NONE and params.summary is SummaryFormat.NONE:
        msg = "payload and summary cannot both be 'none'"
        raise click.UsageError(msg, ctx=ctx)

    if params.sink is PayloadSink.FILE and params.output is None:
        msg = "--sink file requires --output to be provided"
        raise click.UsageError(msg, ctx=ctx)

    cwd = Path()

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

    write_fn = build_writer_from_config(
        sink=params.sink,
        output=params.output,
    )
    actual_table = resolve_table_style(params.summary_style)

    summary, summary_json = _execute_with_handling(
        params=params,
        cfg=cfg,
        cwd=cwd,
        write_fn=write_fn,
        summary_style=actual_table,
    )

    try:
        if params.summary is SummaryFormat.HUMAN and summary:
            print(summary, end="")
        elif params.summary is SummaryFormat.JSON:
            print(json.dumps(summary_json, sort_keys=True, indent=2))
    except BrokenPipeError:
        try:
            sys.stdout.close()
        finally:
            raise SystemExit(0)
