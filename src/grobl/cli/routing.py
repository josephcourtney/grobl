"""Compatibility wrappers for routing helpers moved to :mod:`grobl.app.output_routing`."""

from grobl.app.output_routing import (
    build_merged_output,
    build_summary_writer,
    emit_scan_outputs,
    normalize_summary_destination,
    payload_destination_label,
    resolve_summary_settings,
    resolve_table_style,
    stdout_is_tty,
    summary_destination_label,
    validate_stream_compatibility,
)

__all__ = [
    "build_merged_output",
    "build_summary_writer",
    "emit_scan_outputs",
    "normalize_summary_destination",
    "payload_destination_label",
    "resolve_summary_settings",
    "resolve_table_style",
    "stdout_is_tty",
    "summary_destination_label",
    "validate_stream_compatibility",
]
