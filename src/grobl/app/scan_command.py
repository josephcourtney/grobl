"""Application workflow behind the ``grobl scan`` CLI wrapper."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import click

from grobl.constants import EXIT_CONFIG, ContentScope, PayloadFormat, SummaryDestination, SummaryFormat
from grobl.errors import ConfigLoadError
from grobl.output import build_writer_from_config

from . import output_routing
from .command_support import ScanParams, execute_scan_with_handling, exit_on_broken_pipe
from .config_loading import load_config, resolve_config_base
from .output_routing import (
    emit_scan_outputs,
    normalize_summary_destination,
    payload_destination_label,
    resolve_summary_settings,
    summary_destination_label,
    validate_stream_compatibility,
)
from .scan_runtime import (
    IgnoreCLIArgs,
    assemble_layered_ignores,
    ensure_paths_within_repo,
    gather_runtime_ignore_patterns,
    resolve_runtime_paths,
)


def run_scan_command(  # noqa: PLR0914
    *,
    ctx: click.Context,
    exclude: tuple[str, ...],
    include: tuple[str, ...],
    exclude_file: tuple[Path, ...],
    include_file: tuple[Path, ...],
    exclude_tree: tuple[str, ...],
    include_tree: tuple[str, ...],
    exclude_content: tuple[str, ...],
    include_content: tuple[str, ...],
    config_path: Path | None,
    payload_format: str,
    copy: bool,
    output: Path | None,
    write_to_stdout: bool,
    json_mode: bool,
    summary: str,
    summary_style: str | None,
    summary_to: str,
    summary_output: Path | None,
    ignore_defaults: bool,
    no_ignore_config: bool,
    no_ignore: bool,
    ignore_policy: str,
    scope: str,
    paths: tuple[Path, ...],
) -> None:
    """Execute the scan workflow from validated CLI inputs."""
    ignore_args = IgnoreCLIArgs.from_values(
        exclude=exclude,
        include=include,
        exclude_file=exclude_file,
        include_file=include_file,
        exclude_tree=exclude_tree,
        include_tree=include_tree,
        exclude_content=exclude_content,
        include_content=include_content,
    )

    cwd = Path()
    requested_paths, repo_root = resolve_runtime_paths(paths)
    ensure_paths_within_repo(repo_root=repo_root, requested_paths=requested_paths, ctx=ctx)
    config_base = resolve_config_base(base_path=repo_root, explicit_config=config_path)

    params = build_scan_params(
        ctx=ctx,
        config_path=config_path,
        scope=scope,
        payload_format=payload_format,
        summary=summary,
        summary_style=summary_style,
        summary_to=summary_to,
        copy=copy,
        output=output,
        write_to_stdout=write_to_stdout,
        json_mode=json_mode,
        requested_paths=requested_paths,
        repo_root=repo_root,
        pattern_base=config_base,
    )

    (
        runtime_exclude,
        runtime_include,
        runtime_exclude_tree,
        runtime_include_tree,
        runtime_exclude_content,
        runtime_include_content,
    ) = gather_runtime_ignore_patterns(
        repo_root=repo_root,
        ignore_args=ignore_args,
    )

    try:
        cfg = load_config(
            base_path=config_base,
            explicit_config=params.config_path,
            ignore_defaults=False,
        )
    except ConfigLoadError as err:
        print(err, file=sys.stderr)
        raise SystemExit(EXIT_CONFIG) from err

    ignores = assemble_layered_ignores(
        repo_root=repo_root,
        scan_paths=requested_paths,
        params=params,
        ignore_policy=ignore_policy,
        ignore_defaults_flag=ignore_defaults,
        no_ignore_config_flag=no_ignore_config,
        no_ignore_flag=no_ignore,
        runtime_exclude=runtime_exclude,
        runtime_include=runtime_include,
        runtime_exclude_tree=runtime_exclude_tree,
        runtime_include_tree=runtime_include_tree,
        runtime_exclude_content=runtime_exclude_content,
        runtime_include_content=runtime_include_content,
    )

    destination = normalize_summary_destination(
        summary_to=summary_to,
        summary_output=summary_output,
        ctx=ctx,
    )
    payload_dest = payload_destination_label(
        payload_format=params.payload,
        payload_copy=params.payload_copy,
        payload_output=params.payload_output,
    )
    summary_dest = summary_destination_label(
        summary_format=params.summary,
        summary_destination=destination,
        summary_output=summary_output,
        ctx=ctx,
    )
    merged_destination = (
        payload_dest is not None and summary_dest is not None and payload_dest == summary_dest
    )

    validate_stream_compatibility(
        ctx=ctx,
        payload_format=params.payload,
        payload_copy=params.payload_copy,
        payload_output=params.payload_output,
        summary_format=params.summary,
        summary_destination=destination,
        summary_output=summary_output,
        payload_dest=payload_dest,
        summary_dest=summary_dest,
    )

    direct_writer = build_writer_from_config(copy=params.payload_copy, output=params.payload_output)
    payload_buffer: list[str] | None = [] if merged_destination else None

    if merged_destination:
        buffered_payload = cast("list[str]", payload_buffer)

        def _buffered_writer(text: str) -> None:
            buffered_payload.append(text)

        payload_writer = _buffered_writer
    else:
        payload_writer = direct_writer

    summary_text, summary_json = execute_scan_with_handling(
        params=params,
        cfg={**cfg, "_ignores": ignores},
        cwd=cwd,
        write_fn=payload_writer,
        summary_style=params.summary_style,
    )

    try:
        emit_scan_outputs(
            params=params,
            summary_output=summary_output,
            destination=destination,
            direct_writer=direct_writer,
            payload_buffer=payload_buffer,
            summary_text=summary_text,
            summary_json=summary_json,
        )
    except BrokenPipeError:
        exit_on_broken_pipe()


def build_scan_params(
    *,
    ctx: click.Context,
    config_path: Path | None,
    scope: str,
    payload_format: str,
    summary: str,
    summary_style: str | None,
    summary_to: str,
    copy: bool,
    output: Path | None,
    write_to_stdout: bool,
    json_mode: bool,
    requested_paths: tuple[Path, ...],
    repo_root: Path,
    pattern_base: Path | None,
) -> ScanParams:
    if copy and output is not None:
        msg = "--copy cannot be combined with --output"
        raise click.UsageError(msg, ctx=ctx)
    if copy and write_to_stdout:
        msg = "--copy cannot be combined with --stdout"
        raise click.UsageError(msg, ctx=ctx)
    if output is not None and write_to_stdout:
        msg = "--output cannot be combined with --stdout"
        raise click.UsageError(msg, ctx=ctx)
    json_conflicts = (
        payload_format != PayloadFormat.LLM.value,
        summary != SummaryFormat.AUTO.value,
        summary_style is not None,
        copy,
        output is not None,
        write_to_stdout,
        summary_to != SummaryDestination.STDERR.value,
    )
    if json_mode and any(json_conflicts):
        msg = "--json cannot be combined with other payload or summary routing flags"
        raise click.UsageError(msg, ctx=ctx)

    if json_mode:
        payload_format = PayloadFormat.JSON.value
        summary = SummaryFormat.NONE.value
        output = Path("-")

    actual_summary, actual_summary_style = resolve_summary_settings(
        summary=summary,
        summary_style=summary_style,
        summary_to=summary_to,
        ctx=ctx,
    )

    if copy or output is not None or write_to_stdout:
        payload_copy = copy
        payload_output = Path("-") if write_to_stdout else output
    elif output_routing.stdout_is_tty():
        payload_copy = True
        payload_output = None
    else:
        payload_copy = False
        payload_output = Path("-")

    payload = PayloadFormat(payload_format)
    if payload is PayloadFormat.NONE and actual_summary is SummaryFormat.NONE:
        msg = "nothing to do: choose a payload format, a summary mode, or both"
        raise click.UsageError(msg, ctx=ctx)

    return ScanParams(
        scope=ContentScope(scope),
        summary_style=actual_summary_style,
        config_path=config_path,
        payload=payload,
        summary=actual_summary,
        payload_copy=payload_copy,
        payload_output=payload_output,
        paths=requested_paths,
        repo_root=repo_root,
        pattern_base=pattern_base,
    )


def string_sequence_from_config(cfg: dict[str, object], key: str) -> Sequence[str]:
    """Return a typed string sequence for the given config key, defaulting to empty."""
    value = cfg.get(key)
    if (isinstance(value, Sequence) and not isinstance(value, str)) and all(
        isinstance(item, str) for item in value
    ):
        return cast("tuple[str, ...]", tuple(value))
    return ()
