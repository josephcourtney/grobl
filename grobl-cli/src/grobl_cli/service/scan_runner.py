"""High-level orchestration for running a grobl scan command."""

from __future__ import annotations

import contextlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from grobl.constants import EXIT_CONFIG, EXIT_PATH, OutputMode, SummaryFormat, TableStyle
from grobl.errors import PathNotFoundError, ScanInterrupted
from grobl.services import ScanExecutor, ScanOptions
from grobl.utils import find_common_ancestor
from grobl_config import ConfigLoadError, load_and_adjust_config

from grobl_cli.output import (
    ClipboardOutput,
    FileOutput,
    build_writer_from_config,
)
from grobl_cli.service.prompt import env_assume_yes, maybe_warn_on_common_heavy_dirs
from grobl_cli.tty import clipboard_allowed, resolve_table_style

if TYPE_CHECKING:
    import click


@dataclass(frozen=True, slots=True)
class ScanCommandParams:
    """Parameter object capturing CLI inputs."""

    ignore_defaults: bool
    no_ignore: bool
    no_clipboard: bool
    output: Path | None
    add_ignore: tuple[str, ...]
    remove_ignore: tuple[str, ...]
    ignore_file: tuple[Path, ...]
    mode: str
    table: str
    config_path: Path | None
    fmt: str
    quiet: bool
    paths: tuple[Path, ...]
    yes: bool

    @classmethod
    def from_click(
        cls,
        *,
        ctx: click.Context,
        ignore_defaults: bool,
        no_ignore: bool,
        no_clipboard: bool,
        output: Path | None,
        add_ignore: tuple[str, ...],
        remove_ignore: tuple[str, ...],
        ignore_file: tuple[Path, ...],
        mode: str,
        table: str,
        config_path: Path | None,
        fmt: str,
        quiet: bool,
        paths: tuple[Path, ...],
        yes: bool,
    ) -> ScanCommandParams:
        """Convert Click args into structured params."""
        # Determine defaults for omitted parameters
        chosen_mode = OutputMode(mode)
        chosen_fmt = SummaryFormat(fmt)
        chosen_table = TableStyle(table)
        _ = ctx  # Click context reserved for future use; preserve signature parity.
        return cls(
            ignore_defaults=ignore_defaults,
            no_ignore=no_ignore,
            no_clipboard=no_clipboard,
            output=output,
            add_ignore=add_ignore,
            remove_ignore=remove_ignore,
            ignore_file=ignore_file,
            mode=chosen_mode.value,
            table=chosen_table.value,
            config_path=config_path,
            fmt=chosen_fmt.value,
            quiet=quiet,
            paths=paths or (Path(),),
            yes=yes,
        )


def run_scan_command(params: ScanCommandParams) -> str:
    """Execute a scan according to CLI parameters; return the human summary text."""
    assume_yes = params.yes or env_assume_yes()

    maybe_warn_on_common_heavy_dirs(
        paths=params.paths,
        ignore_defaults=params.ignore_defaults,
        assume_yes=assume_yes,
        confirm=lambda msg: input(msg).strip().lower() == "y",
    )

    cwd = Path()
    try:
        common_base = find_common_ancestor(list(params.paths) or [cwd])
    except (ValueError, PathNotFoundError):
        common_base = cwd

    try:
        cfg = load_and_adjust_config(
            base_path=common_base,
            explicit_config=params.config_path,
            ignore_defaults=params.ignore_defaults,
            add_ignore=params.add_ignore,
            remove_ignore=params.remove_ignore,
            add_ignore_files=params.ignore_file,
            no_ignore=params.no_ignore,
        )
    except ConfigLoadError as err:
        print(err, file=sys.stderr)
        raise SystemExit(EXIT_CONFIG) from err

    allow_clipboard = clipboard_allowed(cfg, no_clipboard_flag=params.no_clipboard)
    write_fn = build_writer_from_config(
        cfg=cfg,
        no_clipboard_flag=params.no_clipboard,
        output=params.output,
    )
    actual_table = resolve_table_style(TableStyle(params.table))

    executor = ScanExecutor(sink=write_fn)

    try:
        execution_result = executor.execute(
            paths=list(params.paths),
            cfg=cfg,
            options=ScanOptions(
                mode=OutputMode(params.mode),
                table=actual_table,
                fmt=SummaryFormat(params.fmt),
            ),
        )
    except PathNotFoundError as err:
        print(err, file=sys.stderr)
        raise SystemExit(EXIT_PATH) from err
    except (ScanInterrupted, KeyboardInterrupt) as si:
        print("\nInterrupted by user during scan.", file=sys.stderr)
        raise SystemExit(130) from si

    summary = execution_result[0] if isinstance(execution_result, tuple) else execution_result

    # Emit results according to output configuration
    if not params.quiet and params.fmt == SummaryFormat.HUMAN.value:
        if params.output:
            FileOutput(params.output).write(summary)
        if allow_clipboard:
            with contextlib.suppress(Exception):
                ClipboardOutput.write(summary)

    return summary
