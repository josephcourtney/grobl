"""Top-level CLI wiring that enforces spec-compliant behavior."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from grobl import __version__

from .common import exit_on_broken_pipe
from .completions import completions
from .init import init
from .scan import scan
from .version import version

if TYPE_CHECKING:
    from collections.abc import Iterable

# Threshold for -vv to map to DEBUG
VERBOSE_DEBUG_THRESHOLD = 2

CLI_CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
}

_HELP_FLAGS = {"-h", "--help", "-V", "--version"}
_VERBOSE_FLAGS = {"--verbose"}


class RootGroup(click.Group):
    """Group subclass that injects scan and keeps help concise."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        normalized = _inject_default_scan(list(args), commands=self.commands)
        return super().parse_args(ctx, normalized)

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        super().format_help(ctx, formatter)
        formatter.write_paragraph()
        formatter.write_text("Default command: scan. Use `grobl scan --help` for command details.")


@click.group(cls=RootGroup, context_settings=CLI_CONTEXT_SETTINGS)
@click.option("-v", "--verbose", count=True, help="Increase verbosity (use -vv for debug)")
@click.option(
    "--log-level",
    type=click.Choice(["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], case_sensitive=False),
    help="Set log level explicitly",
)
@click.version_option(__version__, "-V", "--version", message="%(version)s")
def cli(verbose: int, log_level: str | None) -> None:
    """Scan directories and emit LLM/Markdown/JSON payloads (default scan command)."""
    if log_level:
        level = getattr(logging, log_level.upper())
    elif verbose >= VERBOSE_DEBUG_THRESHOLD:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(level=level, force=True)


def main(argv: list[str] | None = None) -> None:
    """Entry-point wrapper invoked from ``python -m grobl``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        cli.main(args=argv, prog_name="grobl", standalone_mode=False)
    except BrokenPipeError:
        exit_on_broken_pipe()


cli.add_command(scan)
cli.add_command(version)
cli.add_command(completions)
cli.add_command(init)


def _inject_default_scan(
    args: list[str],
    *,
    commands: Iterable[str] | None = None,
) -> list[str]:
    """Insert ``scan`` when the first non-global token warrants it."""
    normalized = list(args)
    if commands is None:
        return normalized

    command_names = set(commands)
    if not command_names:
        return normalized

    scan_exists = "scan" in command_names
    idx = _first_non_global_index(normalized)
    if idx is None:
        if scan_exists:
            normalized.append("scan")
        return normalized

    token = normalized[idx]
    if token in command_names:
        return normalized

    if _should_inject_for_token(token):
        normalized.insert(idx, "scan")
        return normalized

    msg = f"Unknown command: {token}"
    raise click.UsageError(msg)


def _first_non_global_index(args: list[str]) -> int | None:
    """Return the index after skipping global options, or None if none remain."""
    idx = 0
    while idx < len(args):
        token = args[idx]
        if token in _HELP_FLAGS:
            idx += 1
            continue
        if _is_verbose_flag(token):
            idx += 1
            continue
        skip = _log_level_skip(token)
        if skip:
            idx += skip
            continue
        break
    return None if idx >= len(args) else idx


def _is_verbose_flag(flag: str) -> bool:
    if flag in _VERBOSE_FLAGS:
        return True
    if flag == "-":
        return False
    stripped = flag.lstrip("-")
    return bool(stripped) and set(stripped) == {"v"}


def _log_level_skip(flag: str) -> int:
    if flag == "--log-level":
        return 2
    if flag.startswith("--log-level="):
        return 1
    return 0


def _should_inject_for_token(token: str) -> bool:
    if token.startswith("-"):
        return True
    return _is_path_like(token) or _resolves_to_existing_path(token)


def _is_path_like(token: str) -> bool:
    return any(char in token for char in (".", "~", "/", "\\"))


def _resolves_to_existing_path(token: str) -> bool:
    try:
        candidate = Path(token).expanduser()
    except OSError:
        return False
    return candidate.exists()
