"""Top-level Click group wiring together all grobl commands."""

from __future__ import annotations

import logging
import sys

import click
from rich.console import Console
from rich.table import Table

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
        self,
        ctx: click.Context,
        args: list[str],
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

    def get_help(self, ctx: click.Context) -> str:  # type: ignore[override]
        """Return rich-formatted help for the root command.

        Layout:
          - Usage lines (global vs command forms)
          - Short description and default-command note
          - Global options
          - Scan options (default when no command is specified)
          - Commands list (with scan marked as default)
        """
        console = Console(record=True)

        # ------------------------------------------------------------------
        # Usage + description
        # ------------------------------------------------------------------
        console.print("[bold]Usage:[/bold] grobl [GLOBAL OPTIONS] [SCAN OPTIONS] [PATHS...]")
        console.print("       grobl [GLOBAL OPTIONS] COMMAND [ARGS...]")
        console.print()
        console.print("  grobl scans directories and emits LLM/Markdown/JSON payloads.")
        console.print("  If no COMMAND is given, the default command is: [bold]scan[/bold].")
        console.print()

        # ------------------------------------------------------------------
        # Global options (group-level options)
        # ------------------------------------------------------------------
        console.print("[bold]Global Options:[/bold]")
        global_table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            pad_edge=False,
            expand=False,
        )
        global_table.add_column(style="cyan", no_wrap=True)
        global_table.add_column(style="default")

        for param in self.params:
            if not isinstance(param, click.Option):
                continue
            record = param.get_help_record(ctx)
            if not record:
                continue
            opts, help_text = record
            global_table.add_row(opts, help_text or "")

        console.print(global_table)
        console.print()

        # ------------------------------------------------------------------
        # Scan options (default command)
        # ------------------------------------------------------------------
        scan_cmd = self.get_command(ctx, "scan")
        if isinstance(scan_cmd, click.Command):
            scan_ctx = click.Context(scan_cmd, info_name="scan", parent=ctx)
            console.print("[bold]Scan options (default when no command is specified):[/bold]")

            scan_table = Table(
                show_header=False,
                show_edge=False,
                box=None,
                pad_edge=False,
                expand=False,
            )
            scan_table.add_column(style="cyan", no_wrap=True)
            scan_table.add_column(style="default")

            for param in scan_cmd.params:
                if not isinstance(param, click.Option):
                    continue
                record = param.get_help_record(scan_ctx)
                if not record:
                    continue
                opts, help_text = record
                # Avoid duplicating the scan-level help option; the global
                # help flag is already shown above.
                if opts.lstrip().startswith("-h, --help"):
                    continue
                scan_table.add_row(opts, help_text or "")

            console.print(scan_table)
            console.print()

        # ------------------------------------------------------------------
        # Commands
        # ------------------------------------------------------------------
        console.print("[bold]Commands:[/bold]")
        cmd_table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            pad_edge=False,
            expand=False,
        )
        cmd_table.add_column(style="cyan", no_wrap=True)
        cmd_table.add_column(style="default")

        for name in sorted(self.commands):
            command = self.commands[name]
            if not isinstance(command, click.Command):
                continue
            help_text = (command.short_help or command.help or "").strip()
            if name == "scan":
                # Make the default behavior explicit in the commands list.
                if help_text:
                    help_text = f"{help_text} (default when no COMMAND is given)"
                else:
                    help_text = "Run a directory scan (default when no COMMAND is given)"
            cmd_table.add_row(name, help_text)

        console.print(cmd_table)

        # Export as a plain string (including any ANSI colour codes).
        return console.export_text()


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
    """Scan directories and emit LLM/Markdown/JSON payloads.

    If no COMMAND is given, this behaves like: grobl scan [PATHS...]
    """
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
