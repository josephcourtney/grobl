"""Payload and summary routing helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from grobl import tty
from grobl.constants import PayloadFormat, SummaryDestination, SummaryFormat, TableStyle

if TYPE_CHECKING:
    from collections.abc import Callable

    from .command_support import ScanParams
    from .scan_runtime import GlobalCLIOptions

resolve_table_style = tty.resolve_table_style
stdout_is_tty = tty.stdout_is_tty


def build_summary_writer(
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


def resolve_summary_settings(
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
        destination = SummaryDestination(summary_to)
        if destination is SummaryDestination.STDOUT:
            is_tty = stdout_is_tty()
        else:
            is_tty = sys.stderr.isatty() or stdout_is_tty()
        actual_summary = SummaryFormat.TABLE if is_tty else SummaryFormat.NONE
        requested_style = TableStyle.AUTO
    else:
        actual_summary = summary_choice
        requested_style = TableStyle(summary_style) if summary_style else TableStyle.AUTO

    actual_style = (
        resolve_table_style(requested_style) if actual_summary is SummaryFormat.TABLE else TableStyle.AUTO
    )
    return actual_summary, actual_style


def normalize_summary_destination(
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


def payload_destination_label(
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


def summary_destination_label(
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


def validate_stream_compatibility(
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
    """Reject merged destinations when either stream is machine-readable."""
    if payload_dest is None:
        payload_dest = payload_destination_label(
            payload_format=payload_format,
            payload_copy=payload_copy,
            payload_output=payload_output,
        )
    if summary_dest is None:
        summary_dest = summary_destination_label(
            summary_format=summary_format,
            summary_destination=summary_destination,
            summary_output=summary_output,
            ctx=ctx,
        )

    payload_machine = payload_format in {PayloadFormat.JSON, PayloadFormat.NDJSON}
    summary_machine = summary_format is SummaryFormat.JSON
    if payload_dest == summary_dest and payload_dest is not None and (payload_machine or summary_machine):
        msg = (
            "Incompatible merged output: two non-empty streams are routed to the same destination, "
            "and at least one stream is machine-readable (json/ndjson).\n"
            "Fix by either:\n"
            "  - Making formats compatible (e.g., use human-readable summary/payload), or\n"
            "  - Routing streams to different destinations (e.g., --summary-to stderr, or --output PATH).\n"
        )
        raise click.UsageError(msg, ctx=ctx)


def emit_scan_outputs(
    *,
    params: ScanParams,
    global_options: GlobalCLIOptions,
    destination: SummaryDestination,
    direct_writer: Callable[[str], None],
    payload_buffer: list[str] | None,
    summary_text: str,
    summary_json: dict[str, object],
) -> None:
    merged_destination = payload_destination_label(
        payload_format=params.payload,
        payload_copy=params.payload_copy,
        payload_output=params.payload_output,
    ) == summary_destination_label(
        summary_format=params.summary,
        summary_destination=destination,
        summary_output=global_options.summary_output,
        ctx=click.get_current_context(),
    )
    if merged_destination:
        merged_text = build_merged_output(
            summary_format=params.summary,
            summary_text=summary_text,
            summary_json=summary_json,
            payload_buffer=payload_buffer,
        )
        if merged_text:
            direct_writer(merged_text)
        return

    summary_writer = build_summary_writer(destination=destination, output=global_options.summary_output)
    if params.summary is SummaryFormat.TABLE and summary_text:
        summary_writer(summary_text)
    elif params.summary is SummaryFormat.JSON:
        summary_writer(f"{json.dumps(summary_json, sort_keys=True, indent=2)}\n")


def build_merged_output(
    *,
    summary_format: SummaryFormat,
    summary_text: str,
    summary_json: dict[str, object],
    payload_buffer: list[str] | None,
) -> str:
    merged_parts: list[str] = []
    if summary_format is SummaryFormat.TABLE and summary_text:
        merged_parts.append(summary_text)
    elif summary_format is SummaryFormat.JSON:
        merged_parts.append(json.dumps(summary_json, sort_keys=True, indent=2) + "\n")
    if payload_buffer:
        merged_parts.extend(payload_buffer)
    return "".join(merged_parts)
