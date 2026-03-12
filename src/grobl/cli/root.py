"""Top-level CLI wiring that enforces spec-compliant behavior."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from grobl import __version__
from grobl.app.command_support import exit_on_broken_pipe
from grobl.app.root_context import (
    build_command_option_map,
    inject_default_scan,
    normalize_argv,
    resolve_log_level,
    store_root_context,
)
from grobl.constants import IgnorePolicy, PayloadFormat, SummaryDestination, SummaryFormat, TableStyle

from .completions import completions
from .explain import explain
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
  grobl .
  grobl src tests
  grobl scan --format json --output payload.json
  grobl scan --summary json --summary-to stdout
  grobl scan --ignore-policy defaults --add-ignore '*.min.js' src
  grobl explain README.md --format json
  grobl explain docs --include-content 'docs/**'
"""


class RootGroup(click.Group):
    """Group subclass that injects scan and keeps help concise."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        command_options = build_command_option_map(self.commands)
        normalized = normalize_argv(list(args), command_options=command_options)
        normalized = inject_default_scan(list(normalized), command_names=self.commands)
        normalized = normalize_argv(list(normalized), command_options=command_options)
        return super().parse_args(ctx, normalized)

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        super().format_help(ctx, formatter)
        formatter.write_paragraph()
        formatter.write_text("Use `grobl scan --help` for scan options and examples.")


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
@click.option("--config", "config_path", type=click.Path(path_type=Path), help="Explicit config file path")
@click.option(
    "--format",
    "payload_format",
    type=click.Choice([p.value for p in PayloadFormat], case_sensitive=False),
    default=PayloadFormat.LLM.value,
    help="Payload format to emit",
)
@click.option("--copy", is_flag=True, help="Copy the payload to the clipboard")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Write the payload to a file path (use '-' for stdout).",
)
@click.option(
    "--summary",
    type=click.Choice([s.value for s in SummaryFormat], case_sensitive=False),
    default=SummaryFormat.AUTO.value,
    help="Summary mode to display",
)
@click.option(
    "--summary-style",
    type=click.Choice([t.value for t in TableStyle], case_sensitive=False),
    default=None,
    help="Summary table style (auto/full/compact; only valid with --summary table)",
)
@click.option(
    "--summary-to",
    type=click.Choice([d.value for d in SummaryDestination], case_sensitive=False),
    default=SummaryDestination.STDERR.value,
    help="Destination for summary output (defaults to stderr)",
)
@click.option(
    "--summary-output",
    type=click.Path(path_type=Path),
    help="File path to write the summary when --summary-to file is selected",
)
@click.option(
    "-I",
    "--ignore-defaults",
    is_flag=True,
    help="Disable bundled default ignore rules (alias for --ignore-policy config)",
)
@click.option(
    "--no-ignore-config",
    is_flag=True,
    help="Disable ignore rules from discovered .grobl.toml files (alias for --ignore-policy defaults)",
)
@click.option(
    "--no-ignore",
    is_flag=True,
    help="Disable all ignore patterns (alias for --ignore-policy none)",
)
@click.option(
    "--ignore-policy",
    type=click.Choice([p.value for p in IgnorePolicy], case_sensitive=False),
    default=IgnorePolicy.AUTO.value,
    help="Ignore source policy: auto|all|none|defaults|config|cli",
)
@click.version_option(__version__, "-V", "--version", message="%(version)s")
def cli(
    *,
    verbose: int,
    log_level: str | None,
    config_path: Path | None,
    payload_format: str,
    copy: bool,
    output: Path | None,
    summary: str,
    summary_style: str | None,
    summary_to: str,
    summary_output: Path | None,
    ignore_defaults: bool,
    no_ignore_config: bool,
    no_ignore: bool,
    ignore_policy: str,
) -> None:
    """Scan directories and emit LLM/Markdown/JSON payloads (default scan command)."""
    store_root_context(
        ctx=click.get_current_context(silent=True),
        config_path=config_path,
        payload_format=payload_format,
        copy=copy,
        output=output,
        summary=summary,
        summary_style=summary_style,
        summary_to=summary_to,
        summary_output=summary_output,
        ignore_defaults=ignore_defaults,
        no_ignore_config=no_ignore_config,
        no_ignore=no_ignore,
        ignore_policy=ignore_policy,
    )
    logging.basicConfig(level=resolve_log_level(verbose=verbose, log_level=log_level), force=True)


def main(argv: list[str] | None = None) -> None:
    """Entry-point wrapper invoked from ``python -m grobl``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        cli.main(args=argv, prog_name="grobl", standalone_mode=False)
    except BrokenPipeError:
        exit_on_broken_pipe()


cli.add_command(scan)
cli.add_command(explain)
cli.add_command(version)
cli.add_command(completions)
cli.add_command(init)
