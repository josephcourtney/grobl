"""Top-level CLI wiring."""

from __future__ import annotations

import logging
import sys

import click

from grobl import __version__
from grobl.app.command_support import exit_on_broken_pipe
from grobl.app.root_context import (
    build_command_option_map,
    inject_default_scan,
    normalize_argv,
    resolve_log_level,
)

from .completions import completions
from .explain import explain
from .help_format import LiteralEpilogGroup
from .init import init
from .scan import scan
from .version import version

CLI_CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
}

ROOT_EPILOG = """\
Default behavior:
  Running `grobl` or `grobl <path>` is shorthand for `grobl scan <path>`.
  If you intended to scan a path but it does not exist, use `grobl scan <path>`
  to see scan-specific diagnostics.

Examples:
  grobl
    Scan the current directory using the default interactive behavior.

  grobl src tests
    Build a prompt-ready snapshot from multiple paths.

  grobl scan --json
    Emit a JSON payload to stdout with no summary.

  grobl explain README.md --format json
    Show inclusion and content-capture decisions for a specific path.

  grobl init
    Create a starter `.grobl.toml` in the current directory.
"""


class RootGroup(LiteralEpilogGroup):
    """Group subclass that injects scan for path-like invocations."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        command_options = build_command_option_map(self.commands)
        normalized = normalize_argv(list(args), command_options=command_options)
        normalized = inject_default_scan(list(normalized), command_names=self.commands)
        normalized = normalize_argv(list(normalized), command_options=command_options)
        return super().parse_args(ctx, normalized)

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        super().format_help(ctx, formatter)
        formatter.write_paragraph()
        formatter.write_text(
            "Use `grobl scan --help` for scan options and `grobl explain --help` for diagnostics."
        )


@click.group(cls=RootGroup, context_settings=CLI_CONTEXT_SETTINGS, epilog=ROOT_EPILOG)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (use -vv for debug)",
)
@click.option(
    "--log-level",
    type=click.Choice(["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], case_sensitive=False),
    help="Set log level explicitly (overrides -v / -vv).",
)
@click.version_option(__version__, "-V", "--version", message="%(version)s")
def cli(
    *,
    verbose: int,
    log_level: str | None,
) -> None:
    """Build prompt-ready project snapshots and explain filtering decisions."""
    logging.basicConfig(level=resolve_log_level(verbose=verbose, log_level=log_level), force=True)


def main(argv: list[str] | None = None) -> None:
    """Entry-point wrapper invoked from ``python -m grobl``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        cli.main(args=argv, prog_name="grobl", standalone_mode=False)
    except click.ClickException as err:
        err.show()
        raise SystemExit(err.exit_code) from err
    except BrokenPipeError:
        exit_on_broken_pipe()


cli.add_command(scan)
cli.add_command(explain)
cli.add_command(version)
cli.add_command(completions)
cli.add_command(init)
