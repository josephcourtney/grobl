"""Shared CLI helpers used by multiple subcommands."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from grobl.config import LEGACY_TOML_CONFIG, TOML_CONFIG
from grobl.constants import (
    CONFIG_EXCLUDE_PRINT,
    CONFIG_EXCLUDE_TREE,
    EXIT_INTERRUPT,
    EXIT_PATH,
    EXIT_USAGE,
    OutputMode,
    SummaryFormat,
    TableStyle,
)
from grobl.directory import DirectoryTreeBuilder
from grobl.errors import PathNotFoundError, ScanInterrupted
from grobl.services import ScanExecutor, ScanOptions
from grobl.utils import is_text

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

MAX_REF_PREVIEW = 50
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScanParams:
    ignore_defaults: bool
    no_clipboard: bool
    output: Path | None
    add_ignore: tuple[str, ...]
    remove_ignore: tuple[str, ...]
    add_ignore_file: tuple[Path, ...]
    no_ignore: bool
    mode: OutputMode
    table: TableStyle
    config_path: Path | None
    quiet: bool
    fmt: SummaryFormat
    paths: tuple[Path, ...]


def iter_legacy_references(base: Path) -> Iterator[tuple[Path, int, str]]:
    for path in base.rglob("*"):
        if path.is_dir():
            continue
        if path.name in {TOML_CONFIG, LEGACY_TOML_CONFIG}:
            continue
        try:
            if not is_text(path):
                continue
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, start=1):
                    if LEGACY_TOML_CONFIG in line:
                        yield path, i, line.rstrip()
        except OSError:
            continue


def _scan_for_legacy_references(base: Path) -> list[tuple[Path, int, str]]:
    return list(iter_legacy_references(base))


def print_interrupt_diagnostics(cwd: Path, cfg: dict[str, object], builder: DirectoryTreeBuilder) -> None:
    print("\nInterrupted by user. Dumping debug info:")
    print(f"cwd: {cwd}")
    print(f"{CONFIG_EXCLUDE_TREE}: {cfg.get(CONFIG_EXCLUDE_TREE)}")
    print(f"{CONFIG_EXCLUDE_PRINT}: {cfg.get(CONFIG_EXCLUDE_PRINT)}")
    print("DirectoryTreeBuilder(")
    print(f"    base_path         = {builder.base_path}")
    print(f"    total_lines       = {builder.total_lines}")
    print(f"    total_characters  = {builder.total_characters}")
    print(f"    exclude_patterns  = {builder.exclude_patterns}")
    print(")")
    raise SystemExit(EXIT_INTERRUPT)


def _execute_with_handling(
    *,
    params: ScanParams,
    cfg: dict[str, Any],
    cwd: Path,
    write_fn: Callable[[str], None],
    table: TableStyle,
) -> tuple[str, dict[str, Any]]:
    try:
        executor = ScanExecutor(sink=write_fn)
        return executor.execute(
            paths=list(params.paths),
            cfg=cfg,
            options=ScanOptions(mode=params.mode, table=table, fmt=params.fmt),
        )
    except PathNotFoundError as e:
        print(e, file=sys.stderr)
        raise SystemExit(EXIT_PATH) from e
    except ValueError as e:
        print(e, file=sys.stderr)
        raise SystemExit(EXIT_USAGE) from e
    except ScanInterrupted as si:
        print_interrupt_diagnostics(si.common, cfg, si.builder)
        raise
    except KeyboardInterrupt:
        print_interrupt_diagnostics(cwd, cfg, DirectoryTreeBuilder(base_path=cwd, exclude_patterns=[]))
        raise
