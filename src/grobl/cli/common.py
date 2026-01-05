"""Shared CLI helpers used by multiple subcommands."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NoReturn

from grobl.config import LEGACY_TOML_CONFIG, TOML_CONFIG
from grobl.constants import (
    CONFIG_EXCLUDE_PRINT,
    CONFIG_EXCLUDE_TREE,
    EXIT_INTERRUPT,
    EXIT_PATH,
    EXIT_USAGE,
    ContentScope,
    PayloadFormat,
    SummaryFormat,
    TableStyle,
)
from grobl.directory import DirectoryTreeBuilder
from grobl.errors import PathNotFoundError, ScanInterrupted
from grobl.ignore import LayeredIgnoreMatcher
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
    output: Path | None
    add_ignore: tuple[str, ...]
    remove_ignore: tuple[str, ...]
    unignore: tuple[str, ...]
    add_ignore_file: tuple[Path, ...]
    no_ignore: bool
    scope: ContentScope
    summary_style: TableStyle
    config_path: Path | None
    payload: PayloadFormat
    summary: SummaryFormat
    payload_copy: bool
    payload_output: Path | None
    paths: tuple[Path, ...]
    repo_root: Path
    pattern_base: Path | None = None


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
    snapshot = builder.summary_totals()
    print(f"    total_lines       = {snapshot.total_lines}")
    print(f"    total_characters  = {snapshot.total_characters}")
    print(f"    exclude_patterns  = {builder.exclude_patterns}")
    print(")")


def exit_on_broken_pipe() -> None:
    """Terminate cleanly when stdout is closed by the downstream pipe."""
    try:
        sys.stdout.close()
    finally:
        raise SystemExit(0)


def _raise_system_exit(code: int, exc: BaseException, *, message: object | None = None) -> NoReturn:
    """Print any diagnostic text and exit with the provided status code."""
    if message is not None:
        print(message, file=sys.stderr)
    raise SystemExit(code) from exc


def _execute_with_handling(
    *,
    params: ScanParams,
    cfg: dict[str, Any],
    cwd: Path,
    write_fn: Callable[[str], None],
    summary_style: TableStyle,
) -> tuple[str, dict[str, Any]]:
    try:
        executor = ScanExecutor(sink=write_fn)
        ignores = cfg.get("_ignores")
        if not isinstance(ignores, LayeredIgnoreMatcher):
            msg = "internal error: layered ignores missing"
            raise TypeError(msg)
        return executor.execute(
            paths=list(params.paths),
            cfg=cfg,
            options=ScanOptions(
                scope=params.scope,
                payload_format=params.payload,
                summary_format=params.summary,
                summary_style=summary_style,
                repo_root=params.repo_root,
                pattern_base=params.pattern_base,
            ),
        )
    except PathNotFoundError as e:
        _raise_system_exit(EXIT_PATH, e, message=e)
    except ValueError as e:
        _raise_system_exit(EXIT_USAGE, e, message=e)
    except ScanInterrupted as si:
        print_interrupt_diagnostics(si.common, cfg, si.builder)
        _raise_system_exit(EXIT_INTERRUPT, si)
    except KeyboardInterrupt as ki:
        print_interrupt_diagnostics(cwd, cfg, DirectoryTreeBuilder(base_path=cwd, exclude_patterns=[]))
        _raise_system_exit(EXIT_INTERRUPT, ki)
