"""Reusable Click option builders for CLI subcommands."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from grobl.constants import (
    ContentScope,
    IgnorePolicy,
    PayloadFormat,
    SummaryDestination,
    SummaryFormat,
    TableStyle,
)

CommandDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]

_IGNORE_OPTION_DECORATORS: tuple[CommandDecorator, ...] = (
    click.option("--exclude", multiple=True, help="Add a tree+content exclude pattern"),
    click.option("--include", multiple=True, help="Add a tree+content include (negated) pattern"),
    click.option(
        "--exclude-file",
        "exclude_file",
        multiple=True,
        type=click.Path(path_type=Path, exists=False),
        help="Exclude a specific file path (tree + content)",
    ),
    click.option(
        "--include-file",
        "include_file",
        multiple=True,
        type=click.Path(path_type=Path, exists=False),
        help="Include a specific file path (tree + content; negated internally)",
    ),
    click.option("--exclude-tree", multiple=True, help="Add a tree-only exclude pattern"),
    click.option("--include-tree", multiple=True, help="Add a tree-only include (negated) pattern"),
    click.option(
        "--exclude-content",
        multiple=True,
        help="Add a content-only exclude pattern (controls text capture)",
    ),
    click.option(
        "--include-content",
        multiple=True,
        help="Add a content-only include (negated) pattern",
    ),
)

_CONFIG_OPTION_DECORATORS: tuple[CommandDecorator, ...] = (
    click.option(
        "--config",
        "config_path",
        type=click.Path(path_type=Path),
        help="Explicit config file path",
    ),
)

_IGNORE_POLICY_OPTION_DECORATORS: tuple[CommandDecorator, ...] = (
    click.option(
        "-I",
        "--ignore-defaults",
        is_flag=True,
        help="Disable bundled default ignore rules (alias for --ignore-policy config)",
    ),
    click.option(
        "--no-ignore-config",
        is_flag=True,
        help="Disable ignore rules from discovered .grobl.toml files (alias for --ignore-policy defaults)",
    ),
    click.option(
        "--no-ignore",
        is_flag=True,
        help="Disable all ignore patterns (alias for --ignore-policy none)",
    ),
    click.option(
        "--ignore-policy",
        type=click.Choice([p.value for p in IgnorePolicy], case_sensitive=False),
        default=IgnorePolicy.AUTO.value,
        help="Ignore source policy: auto|all|none|defaults|config|cli",
    ),
)

_SCAN_OUTPUT_OPTION_DECORATORS: tuple[CommandDecorator, ...] = (
    click.option(
        "--format",
        "payload_format",
        type=click.Choice([p.value for p in PayloadFormat], case_sensitive=False),
        default=PayloadFormat.LLM.value,
        help="Payload format to emit",
    ),
    click.option("--copy", is_flag=True, help="Copy the payload to the clipboard"),
    click.option(
        "--output",
        type=click.Path(path_type=Path),
        help="Write the payload to a file path (use '-' for stdout).",
    ),
    click.option(
        "--stdout",
        "write_to_stdout",
        is_flag=True,
        help="Write the payload to stdout (shorthand for --output -)",
    ),
    click.option(
        "--json",
        "json_mode",
        is_flag=True,
        help="Emit machine-oriented JSON to stdout with no summary",
    ),
    click.option(
        "--summary",
        type=click.Choice([s.value for s in SummaryFormat], case_sensitive=False),
        default=SummaryFormat.AUTO.value,
        help="Summary mode to display",
    ),
    click.option(
        "--summary-style",
        type=click.Choice([t.value for t in TableStyle], case_sensitive=False),
        default=None,
        help="Summary table style (auto/full/compact; only valid with --summary table)",
    ),
    click.option(
        "--summary-to",
        type=click.Choice([d.value for d in SummaryDestination], case_sensitive=False),
        default=SummaryDestination.STDERR.value,
        help="Destination for summary output (defaults to stderr)",
    ),
    click.option(
        "--summary-output",
        type=click.Path(path_type=Path),
        help="File path to write the summary when --summary-to file is selected",
    ),
    click.option(
        "--lines/--no-lines",
        "show_lines",
        default=True,
        help="Include line counts in payload metadata and summaries",
    ),
    click.option(
        "--characters/--no-characters",
        "show_chars",
        default=True,
        help="Include character counts in payload metadata and summaries",
    ),
    click.option(
        "--tokens/--no-tokens",
        "show_tokens",
        default=True,
        help="Include token counts in payload metadata and summaries",
    ),
    click.option(
        "--inclusion-status/--no-inclusion-status",
        "show_inclusion_status",
        default=True,
        help="Include inclusion markers in tree views and machine-readable file metadata",
    ),
)

_PATHS_ARGUMENT: CommandDecorator = click.argument(
    "paths",
    nargs=-1,
    type=click.Path(path_type=Path),
)


def _apply_decorators(
    func: Callable[..., Any],
    decorators: tuple[CommandDecorator, ...],
) -> Callable[..., Any]:
    wrapped: Callable[..., Any] = func
    for decorator in reversed(decorators):
        wrapped = decorator(wrapped)
    return wrapped


def add_ignore_options(func: Callable[..., Any]) -> Callable[..., Any]:
    """Attach the shared ignore/runtime options to a subcommand."""
    return _apply_decorators(func, _IGNORE_OPTION_DECORATORS)


def add_config_option(func: Callable[..., Any]) -> Callable[..., Any]:
    """Attach the shared config option to a subcommand."""
    return _apply_decorators(func, _CONFIG_OPTION_DECORATORS)


def add_ignore_policy_options(func: Callable[..., Any]) -> Callable[..., Any]:
    """Attach ignore source selection options to a subcommand."""
    return _apply_decorators(func, _IGNORE_POLICY_OPTION_DECORATORS)


def add_scope_option(func: Callable[..., Any]) -> Callable[..., Any]:
    """Attach the shared scan scope option."""
    decorators: tuple[CommandDecorator, ...] = (
        click.option(
            "--scope",
            type=click.Choice([scope.value for scope in ContentScope], case_sensitive=False),
            default=ContentScope.ALL.value,
            help="Content scope for payload generation",
        ),
    )
    return _apply_decorators(func, decorators)


def add_paths_argument(func: Callable[..., Any]) -> Callable[..., Any]:
    """Attach the shared paths argument."""
    return _PATHS_ARGUMENT(func)


def add_scan_output_options(func: Callable[..., Any]) -> Callable[..., Any]:
    """Attach the payload/summary routing options used by ``scan``."""
    return _apply_decorators(func, _SCAN_OUTPUT_OPTION_DECORATORS)
