"""CLI command implementation for the ``grobl scan`` workflow."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, cast

import click

from grobl import tty
from grobl.config import load_config, resolve_config_base
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

from .common import (
    ScanParams,
    _execute_with_handling,
    exit_on_broken_pipe,
)
from .options import add_ignore_options, add_paths_argument, add_scope_option
from .runtime import (
    IgnoreCLIArgs,
    assemble_layered_ignores,
    ensure_paths_within_repo,
    gather_runtime_ignore_patterns,
    global_cli_options,
    resolve_runtime_paths,
    warn_legacy_ignore_flags,
)

if TYPE_CHECKING:
    from collections.abc import Callable

resolve_table_style = tty.resolve_table_style
stdout_is_tty = tty.stdout_is_tty

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
def scan(  # noqa: C901,PLR0912,PLR0915,PLR0914
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
    """Run a directory scan based on CLI flags and paths, then emit/copy output.

    Payload destination defaults to stdout. Use --copy to additionally copy the payload
    to the clipboard, or --output to write to a file (use '-' for stdout).
    """
    global_options = global_cli_options(ctx)
    ignore_args = IgnoreCLIArgs.from_values(
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
    )
    warn_legacy_ignore_flags(ignore_args)

    cwd = Path()
    requested_paths, repo_root = resolve_runtime_paths(paths)

    # Spec §3 pins repo_root to git root when in a worktree; make behavior deterministic
    # by rejecting scan targets outside repo_root.
    ensure_paths_within_repo(repo_root=repo_root, requested_paths=requested_paths, ctx=ctx)

    config_base = resolve_config_base(base_path=repo_root, explicit_config=global_options.config_path)

    if global_options.copy and global_options.output is not None:
        msg = "--copy cannot be combined with --output"
        raise click.UsageError(msg, ctx=ctx)
    params = _build_scan_params(
        ctx=ctx,
        config_path=global_options.config_path,
        scope=scope,
        payload_format=global_options.payload_format,
        summary=global_options.summary,
        summary_style=global_options.summary_style,
        summary_to=global_options.summary_to,
        copy=global_options.copy,
        output=global_options.output,
        add_ignore=add_ignore,
        remove_ignore=remove_ignore,
        unignore=unignore,
        ignore_file=ignore_file,
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
            # Reviewer: "--no-ignore-defaults" is about ignore layers only; keep default config
            # values (like tag defaults) stable.
            ignore_defaults=False,
        )
    except ConfigLoadError as err:
        print(err, file=sys.stderr)
        raise SystemExit(EXIT_CONFIG) from err

    # Build layered ignores per spec; ignore defaults/config can be disabled independently.
    ignores = assemble_layered_ignores(
        repo_root=repo_root,
        scan_paths=requested_paths,
        params=params,
        global_options=global_options,
        runtime_exclude=runtime_exclude,
        runtime_include=runtime_include,
        runtime_exclude_tree=runtime_exclude_tree,
        runtime_include_tree=runtime_include_tree,
        runtime_exclude_content=runtime_exclude_content,
        runtime_include_content=runtime_include_content,
    )

    destination = _normalize_summary_destination(
        summary_to=global_options.summary_to,
        summary_output=global_options.summary_output,
        ctx=ctx,
    )

    payload_dest = _payload_destination_label(
        payload_format=params.payload,
        payload_copy=params.payload_copy,
        payload_output=params.payload_output,
    )
    summary_dest = _summary_destination_label(
        summary_format=params.summary,
        summary_destination=destination,
        summary_output=global_options.summary_output,
        ctx=ctx,
    )
    merged_destination = (
        payload_dest is not None and summary_dest is not None and payload_dest == summary_dest
    )

    _validate_stream_compatibility(
        ctx=ctx,
        payload_format=params.payload,
        payload_copy=params.payload_copy,
        payload_output=params.payload_output,
        summary_format=params.summary,
        summary_destination=destination,
        summary_output=global_options.summary_output,
        payload_dest=payload_dest,
        summary_dest=summary_dest,
    )

    direct_writer = build_writer_from_config(
        copy=params.payload_copy,
        output=params.payload_output,
    )
    payload_buffer: list[str] | None = [] if merged_destination else None

    if merged_destination:
        buffered_payload = cast("list[str]", payload_buffer)

        def _buffered_writer(text: str) -> None:
            buffered_payload.append(text)

        payload_writer = _buffered_writer
    else:
        payload_writer = direct_writer

    summary_text, summary_json = _execute_with_handling(
        params=params,
        cfg={**cfg, "_ignores": ignores},
        cwd=cwd,
        write_fn=payload_writer,
        summary_style=params.summary_style,
    )

    try:
        if merged_destination:
            merged_parts: list[str] = []
            if params.summary is SummaryFormat.TABLE and summary_text:
                merged_parts.append(summary_text)
            elif params.summary is SummaryFormat.JSON:
                merged_parts.append(json.dumps(summary_json, sort_keys=True, indent=2) + "\n")

            if payload_buffer:
                merged_parts.extend(payload_buffer)

            merged_text = "".join(merged_parts)
            if merged_text:
                direct_writer(merged_text)
        else:
            summary_writer = _build_summary_writer(
                destination=destination,
                output=global_options.summary_output,
            )
            if params.summary is SummaryFormat.TABLE and summary_text:
                summary_writer(summary_text)
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
    summary_to: str,
    ctx: click.Context,
) -> tuple[SummaryFormat, TableStyle]:
    summary_choice = SummaryFormat(summary)
    if summary_style is not None and summary_choice is not SummaryFormat.TABLE:
        msg = "--summary-style is only valid when --summary table"
        raise click.UsageError(msg, ctx=ctx)

    if summary_choice is SummaryFormat.AUTO:
        # AUTO is intended to be "human-friendly when attached to a terminal".
        # Use the effective destination TTY-ness (stderr by default).
        destination = SummaryDestination(summary_to)
        if destination is SummaryDestination.STDOUT:
            is_tty = stdout_is_tty()
        else:
            # In tests, stderr is captured; in real shells, stderr may be a TTY even when stdout is piped.
            # Treat stdout TTY-ness as a sufficient signal for "interactive" mode.
            is_tty = sys.stderr.isatty() or stdout_is_tty()
        actual_summary = SummaryFormat.TABLE if is_tty else SummaryFormat.NONE
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


def _payload_destination_label(
    *,
    payload_format: PayloadFormat,
    payload_copy: bool,
    payload_output: Path | None,
) -> str | None:
    if payload_format is PayloadFormat.NONE:
        return None
    if payload_copy:
        return "clipboard"
    if payload_output is None:
        return "clipboard"
    if payload_output == Path("-"):
        return "stdout"
    return f"file:{payload_output}"


def _summary_destination_label(
    *,
    summary_format: SummaryFormat,
    summary_destination: SummaryDestination,
    summary_output: Path | None,
    ctx: click.Context,
) -> str | None:
    if summary_format is SummaryFormat.NONE:
        return None
    if summary_destination is SummaryDestination.STDERR:
        return "stderr"
    if summary_destination is SummaryDestination.STDOUT:
        return "stdout"
    if summary_output is None:
        msg = "--summary-output is required when --summary-to file"
        raise click.UsageError(msg, ctx=ctx)
    return f"file:{summary_output}"


def _string_sequence_from_config(cfg: dict[str, object], key: str) -> Sequence[str]:
    """Return a typed string sequence for the given config key, defaulting to empty."""
    value = cfg.get(key)
    if (isinstance(value, Sequence) and not isinstance(value, str)) and all(
        isinstance(item, str) for item in value
    ):
        return cast("tuple[str, ...]", tuple(value))
    return ()


def _build_scan_params(
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
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
    unignore: tuple[str, ...],
    ignore_file: tuple[Path, ...],
    requested_paths: tuple[Path, ...],
    repo_root: Path,
    pattern_base: Path | None,
) -> ScanParams:
    actual_summary, actual_summary_style = _resolve_summary_settings(
        summary=summary,
        summary_style=summary_style,
        summary_to=summary_to,
        ctx=ctx,
    )

    # --- payload destination auto-selection ---
    # User explicitly chose a destination.
    if copy or output is not None:
        payload_copy = copy
        payload_output = output
    # No explicit destination: choose based on whether stdout is a terminal.
    elif stdout_is_tty():
        payload_copy = True
        payload_output = None
    else:
        payload_copy = False
        # Use '-' sentinel (your writer already documents this) to mean stdout.
        payload_output = Path("-")
    # -----------------------------------------

    return ScanParams(
        output=output,
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
        payload_output=payload_output,
        paths=requested_paths,
        repo_root=repo_root,
        pattern_base=pattern_base,
    )


def _validate_stream_compatibility(
    *,
    ctx: click.Context,
    payload_format: PayloadFormat,
    payload_copy: bool,
    payload_output: Path | None,
    summary_format: SummaryFormat,
    summary_destination: SummaryDestination,
    summary_output: Path | None,
    payload_dest: str | None = None,
    summary_dest: str | None = None,
) -> None:
    """
    Enforce spec stream compatibility.

      - If any non-empty stream to a destination is machine-readable,
        exactly one non-empty stream may go there.
      - Otherwise, merging is allowed (summary then payload).
    """
    if payload_dest is None:
        payload_dest = _payload_destination_label(
            payload_format=payload_format,
            payload_copy=payload_copy,
            payload_output=payload_output,
        )
    if summary_dest is None:
        summary_dest = _summary_destination_label(
            summary_format=summary_format,
            summary_destination=summary_destination,
            summary_output=summary_output,
            ctx=ctx,
        )

    payload_machine = payload_format in {PayloadFormat.JSON, PayloadFormat.NDJSON}
    summary_machine = summary_format is SummaryFormat.JSON

    if (
        payload_dest is not None
        and summary_dest is not None
        and payload_dest == summary_dest
        and (payload_machine or summary_machine)
    ):
        msg = (
            "Incompatible merged output: two non-empty streams are routed to the same destination, "
            "and at least one stream is machine-readable (json/ndjson).\n"
            "Fix by either:\n"
            "  - Making formats compatible (e.g., use human-readable summary/payload), or\n"
            "  - Routing streams to different destinations (e.g., --summary-to stderr, or --output PATH).\n"
        )
        raise click.UsageError(msg, ctx=ctx)
