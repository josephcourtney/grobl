"""Top-level Click group wiring together all grobl commands."""

from __future__ import annotations

import logging
import sys

import click

from grobl import __version__

# Threshold for -vv to map to DEBUG
VERBOSE_DEBUG_THRESHOLD = 2

CLI_CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "ignore_unknown_options": True,
    "allow_extra_args": True,
}


class _DefaultScanGroup(click.Group):
    """Click group that falls back to the scan command when none is provided."""

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        if args:
            try:
                return super().resolve_command(ctx, args)
            except click.UsageError:
                pass

        scan_cmd = self.get_command(ctx, "scan")
        if scan_cmd is None:
            return super().resolve_command(ctx, args)
        return "scan", scan_cmd, args


@click.group(cls=_DefaultScanGroup, invoke_without_command=True, context_settings=CLI_CONTEXT_SETTINGS)
@click.option("-v", "--verbose", count=True, help="Increase verbosity (use -vv for debug)")
@click.option(
    "--log-level",
    type=click.Choice(["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], case_sensitive=False),
    help="Set log level explicitly",
)
@click.version_option(__version__, "-V", "--version")
@click.pass_context
def cli(ctx: click.Context, verbose: int, log_level: str | None) -> None:
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

    # When invoked without a subcommand, resolve_command routes to ``scan``.
    # ``ctx.invoked_subcommand`` stays ``None`` in that case, so we manually
    # invoke the resolved command with the remaining arguments.
    if ctx.invoked_subcommand is None and isinstance(ctx.command, click.Group):
        command = ctx.command.get_command(ctx, "scan")
        if command is not None:
            command.main(
                args=list(ctx.protected_args) + list(ctx.args),
                prog_name=f"{ctx.command_path} scan",
                standalone_mode=False,
            )


# Import subcommands and register them
from .completions import completions  # noqa: E402
from .init import init  # noqa: E402
from .scan import scan  # noqa: E402
from .version import version  # noqa: E402

cli.add_command(scan)
cli.add_command(version)
cli.add_command(completions)
cli.add_command(init)


def main(argv: list[str] | None = None) -> None:
    """Compat entry that executes the Click group with the provided argv."""
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        cli.main(args=argv, prog_name="grobl", standalone_mode=False)
    except BrokenPipeError:
        try:
            sys.stdout.close()
        finally:
            raise SystemExit(0)
