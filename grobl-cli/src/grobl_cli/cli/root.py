"""Top-level Click group wiring together all grobl commands."""

from __future__ import annotations

import logging
import sys

import click
from grobl.constants import EXIT_USAGE

from grobl import __version__

# Threshold for -vv to map to DEBUG
VERBOSE_DEBUG_THRESHOLD = 2


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", count=True, help="Increase verbosity (use -vv for debug)")
@click.option(
    "--log-level",
    type=click.Choice(["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], case_sensitive=False),
    help="Set log level explicitly",
)
@click.version_option(__version__, "-V", "--version")
@click.pass_context
def cli(_ctx: click.Context, verbose: int, log_level: str | None) -> None:
    """Directory-to-Markdown utility with TOML config support."""
    if log_level:
        level = getattr(logging, log_level.upper())
    elif verbose >= VERBOSE_DEBUG_THRESHOLD:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(level=level, force=True)


# Import subcommands and register them
from .completions import completions  # noqa: E402
from .init import init  # noqa: E402
from .scan import scan  # noqa: E402
from .version import version  # noqa: E402

cli.add_command(scan)
cli.add_command(version)
cli.add_command(completions)
cli.add_command(init)

SUBCOMMANDS = {"scan", "version", "init", "completions"}


def main(argv: list[str] | None = None) -> None:
    """Compat entry that injects `scan` when a subcommand is omitted."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["scan"]
    elif argv[0] not in SUBCOMMANDS and argv[0] not in {"-h", "--help", "-V", "--version"}:
        idx = 0
        while idx < len(argv):
            arg = argv[idx]
            if arg.startswith("-v"):
                idx += 1
                continue
            if arg == "--log-level":
                idx += 2
                continue
            if arg.startswith("--log-level="):
                idx += 1
                continue
            break
        argv.insert(idx, "scan")
    try:
        cli.main(args=argv, prog_name="grobl", standalone_mode=False)
    except BrokenPipeError:
        try:
            sys.stdout.close()
        finally:
            raise SystemExit(0)
