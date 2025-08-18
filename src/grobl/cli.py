"""Command line interface for grobl."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from grobl import __version__
from grobl.config import LEGACY_TOML_CONFIG, TOML_CONFIG, load_and_adjust_config, write_default_config
from grobl.constants import (
    CONFIG_EXCLUDE_PRINT,
    CONFIG_EXCLUDE_TREE,
    HEAVY_DIRS,
    OutputMode,
    TableStyle,
)
from grobl.directory import DirectoryTreeBuilder
from grobl.errors import ConfigLoadError, PathNotFoundError, ScanInterrupted
from grobl.output import OutputSinkAdapter, build_writer_from_config
from grobl.services import ScanExecutor, ScanOptions
from grobl.utils import is_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanParams:
    """Grouped CLI parameters to reduce argument noise."""

    ignore_defaults: bool
    no_clipboard: bool
    output: Path | None
    add_ignore: tuple[str, ...]
    remove_ignore: tuple[str, ...]
    mode: OutputMode
    table: TableStyle
    paths: tuple[Path, ...]


ConfirmFn = Callable[[str], bool]


def _default_confirm(msg: str) -> bool:
    """'Return True iff the user typed y'."""
    resp = input(msg).strip().lower()
    return resp == "y"


def _detect_heavy_dirs(paths: tuple[Path, ...]) -> set[str]:
    """Return heavy dir names found beneath any path (pure function for testing)."""
    found: set[str] = set()
    for p in paths:
        for d in HEAVY_DIRS:
            if (p / d).exists():
                found.add(d)
    return found


def _maybe_warn_on_common_heavy_dirs(
    *,
    paths: tuple[Path, ...],
    ignore_defaults: bool,
    assume_yes: bool,
    confirm: ConfirmFn = _default_confirm,  # "injected for tests"
) -> None:
    """Warn only when default ignores are disabled; skip if --yes was passed."""
    if assume_yes or not ignore_defaults:
        return
    found = _detect_heavy_dirs(paths)
    if not found:
        return
    joined = ", ".join(sorted(found))
    msg = f"Warning: this scan may include heavy directories: {joined}. Continue? (y/N): "
    if not confirm(msg):
        raise SystemExit(1)


def _scan_for_legacy_references(base: Path) -> list[tuple[Path, int, str]]:
    """Return [(path, line_no, line)] where the legacy filename string appears."""
    hits: list[tuple[Path, int, str]] = []
    for path in base.rglob("*"):
        # Skip directories and the legacy file itself (we handle it separately)
        if path.is_dir():
            continue
        if path.name in {TOML_CONFIG, LEGACY_TOML_CONFIG}:
            continue
        # Cheap heuristics: only check text files
        try:
            if not is_text(path):
                continue
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, start=1):
                    if LEGACY_TOML_CONFIG in line:
                        hits.append((path, i, line.rstrip()))
        except OSError:
            continue
    return hits


def _maybe_offer_legacy_migration(
    base: Path, *, assume_yes: bool, confirm: ConfirmFn = _default_confirm
) -> None:
    """Prompt to rename legacy .grobl.config.toml -> .grobl.toml and alert references."""
    legacy = base / LEGACY_TOML_CONFIG
    if not legacy.exists():
        return
    new = base / TOML_CONFIG

    # Find references across the repo (do this before any rename so line numbers are stable)
    refs = _scan_for_legacy_references(base)
    if refs:
        print(f"Found references to '{LEGACY_TOML_CONFIG}' in the repository:")
        for p, ln, text in refs[:50]:
            print(f"  - {p}:{ln}: {text}")
        if len(refs) > 50:
            print(f"  ... and {len(refs) - 50} more matches")
        print("Consider updating these to the new filename '.grobl.toml'.")

    if new.exists():
        print(
            f"Note: Both '{LEGACY_TOML_CONFIG}' and '{TOML_CONFIG}' exist. "
            f"'{TOML_CONFIG}' will be preferred; you can delete the legacy file when ready."
        )
        return

    if assume_yes or confirm(
        f"Detected legacy config '{LEGACY_TOML_CONFIG}'. Rename it to '{TOML_CONFIG}' now? (y/N): "
    ):
        try:
            legacy.rename(new)
            print(f"Renamed '{LEGACY_TOML_CONFIG}' -> '{TOML_CONFIG}'.")
        except OSError as e:
            print(f"Could not rename legacy config: {e}", file=sys.stderr)


def _execute_with_handling(
    *,
    params: ScanParams,
    cfg: dict[str, Any],
    cwd: Path,
    write_fn: Callable[[str], None],
) -> str:
    """Run the scan service and keep `scan()` slim; return human summary text."""
    try:
        executor = ScanExecutor(sink=OutputSinkAdapter(write_fn))
        return executor.execute(
            paths=list(params.paths),
            cfg=cfg,
            options=ScanOptions(mode=params.mode, table=params.table),
        )
    except PathNotFoundError as e:
        print(e, file=sys.stderr)
        raise SystemExit(1) from e
    except ValueError as e:
        print(e, file=sys.stderr)
        raise SystemExit(1) from e
    except ScanInterrupted as si:
        print_interrupt_diagnostics(si.common, cfg, si.builder)
        raise
    except KeyboardInterrupt:
        print_interrupt_diagnostics(cwd, cfg, DirectoryTreeBuilder(base_path=cwd, exclude_patterns=[]))
        raise


def print_interrupt_diagnostics(cwd: Path, cfg: dict[str, object], builder: DirectoryTreeBuilder) -> None:
    """Print diagnostics when the user interrupts execution."""
    print("\nInterrupted by user. Dumping debug info:")
    print(f"cwd: {cwd}")
    print(f"{CONFIG_EXCLUDE_TREE}: {cfg.get(CONFIG_EXCLUDE_TREE)}")
    print(
        f"{CONFIG_EXCLUDE_PRINT}: {cfg.get(CONFIG_EXCLUDE_PRINT)}"
    )  # "use constant for both label and lookup"
    print("DirectoryTreeBuilder(")
    print(f"    base_path         = {builder.base_path}")
    print(f"    total_lines       = {builder.total_lines}")
    print(f"    total_characters  = {builder.total_characters}")
    print(f"    exclude_patterns  = {builder.exclude_patterns}")
    print(")")
    raise SystemExit(130)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
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
    level: int
    if log_level:
        level = getattr(logging, log_level.upper())
    elif verbose >= 2:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(level=level, force=True)


@cli.command()
def version() -> None:
    """Print version and exit."""
    print(__version__)


@cli.command()
@click.option(
    "--yes", is_flag=True, help="Assume 'yes' for interactive prompts (skip heavy-dir confirmation)."
)
@click.option("--ignore-defaults", "-I", is_flag=True, help="Ignore bundled default exclude patterns")
@click.option("--no-clipboard", is_flag=True, help="Print output to stdout instead of copying to clipboard")
@click.option("--output", type=click.Path(path_type=Path), help="Write output to a file")
@click.option("--add-ignore", multiple=True, help="Additional ignore pattern for this run")
@click.option("--remove-ignore", multiple=True, help="Ignore pattern to remove for this run")
@click.option(
    "--mode",
    type=click.Choice([m.value for m in OutputMode], case_sensitive=False),
    default=OutputMode.ALL.value,
    help="Output mode",
)
@click.option(
    "--table",
    type=click.Choice([t.value for t in TableStyle], case_sensitive=False),
    default=TableStyle.FULL.value,
    help="Summary table style",
)
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def scan(
    *,
    ignore_defaults: bool,
    no_clipboard: bool,
    output: Path | None,
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
    mode: str,
    table: str,
    paths: tuple[Path, ...],
    yes: bool,
) -> None:
    """Run a directory scan based on CLI flags and paths, then emit/copy output."""
    params = ScanParams(
        ignore_defaults=ignore_defaults,
        no_clipboard=no_clipboard,
        output=output,
        add_ignore=add_ignore,
        remove_ignore=remove_ignore,
        mode=OutputMode(mode),
        table=TableStyle(table),
        paths=paths or (Path(),),
    )

    cwd = Path()
    # Handle legacy config detection / migration prompts and cross-repo alerts.
    _maybe_offer_legacy_migration(cwd, assume_yes=yes)

    _maybe_warn_on_common_heavy_dirs(
        paths=params.paths, ignore_defaults=params.ignore_defaults, assume_yes=yes
    )

    try:
        cfg = load_and_adjust_config(
            cwd=cwd,
            ignore_defaults=params.ignore_defaults,
            add_ignore=params.add_ignore,
            remove_ignore=params.remove_ignore,
        )
    except ConfigLoadError as err:
        print(err, file=sys.stderr)
        raise SystemExit(1) from err

    write_fn = build_writer_from_config(
        cfg=cfg,
        no_clipboard_flag=params.no_clipboard,
        output=params.output,
    )

    summary = _execute_with_handling(params=params, cfg=cfg, cwd=cwd, write_fn=write_fn)
    if summary:
        print(summary, end="")


@cli.command()
@click.option(
    "--path", "target", type=click.Path(path_type=Path), default=Path(), help="Directory to initialize"
)
@click.option("--force", is_flag=True, help="Overwrite an existing config file")
@click.option(
    "--yes",
    is_flag=True,
    help="Assume 'yes' for interactive prompts (auto-migrate legacy filename and suppress questions).",
)
def init(*, target: Path, force: bool, yes: bool) -> None:
    """Create a default .grobl.toml in the target directory (no auto-creation elsewhere)."""
    target = target.resolve()
    legacy = target / LEGACY_TOML_CONFIG
    new = target / TOML_CONFIG

    if legacy.exists() and not new.exists():
        if yes or _default_confirm(
            f"Found legacy '{LEGACY_TOML_CONFIG}'. Rename to '{TOML_CONFIG}' instead of creating a new one? (y/N): "
        ):
            try:
                legacy.rename(new)
                print(f"Renamed '{LEGACY_TOML_CONFIG}' -> '{TOML_CONFIG}'.")
            except OSError as e:
                print(f"Could not rename legacy config: {e}", file=sys.stderr)
                raise SystemExit(1) from e
        else:
            # Fall through to create new file alongside legacy (explicitly allowed)
            pass

    if new.exists() and not force:
        print(
            f"Config '{TOML_CONFIG}' already exists at {target}. Use --force to overwrite.", file=sys.stderr
        )
        raise SystemExit(1)

    try:
        write_default_config(target)
        print(f"Wrote default config to {new}")
    except OSError as e:
        print(f"Failed to write '{TOML_CONFIG}': {e}", file=sys.stderr)
        raise SystemExit(1) from e

    # After writing, scan for legacy references and alert the user
    refs = _scan_for_legacy_references(target)
    if refs:
        print(f"Heads up: found {len(refs)} reference(s) to '{LEGACY_TOML_CONFIG}' in this repository:")
        for p, ln, text in refs[:50]:
            print(f"  - {p}:{ln}: {text}")
        if len(refs) > 50:
            print("  ... (truncated)")
        print("Update these to '.grobl.toml' to avoid confusion.")


SUBCOMMANDS = {"scan", "version", "init"}


def main(argv: list[str] | None = None) -> None:
    """Compat entry point that injects the `scan` subcommand when omitted."""
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
    cli.main(args=argv, prog_name="grobl", standalone_mode=False)


if __name__ == "__main__":
    main()
