"""Shared application helpers invoked by CLI wrappers."""

from __future__ import annotations

import io
import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NoReturn

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

from .execution import ScanExecutor, ScanOptions
from .legacy import scan_legacy_references

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

logger = logging.getLogger(__name__)
MAX_REF_PREVIEW = 50


@dataclass(frozen=True, slots=True)
class ScanParams:
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
    """Yield files that still reference the legacy config filename."""
    yield from scan_legacy_references(base)


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
    sys.stdout = io.StringIO()
    raise SystemExit(0)


def execute_scan_with_handling(
    *,
    params: ScanParams,
    cfg: dict[str, Any],
    cwd: Path,
    write_fn: Callable[[str], None],
    summary_style: TableStyle,
) -> tuple[str, dict[str, Any]]:
    """Run the application scan executor and translate failures into exit codes."""
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
    except PathNotFoundError as err:
        _raise_system_exit(EXIT_PATH, err, message=err)
    except ValueError as err:
        _raise_system_exit(EXIT_USAGE, err, message=err)
    except ScanInterrupted as interrupted:
        print_interrupt_diagnostics(interrupted.common, cfg, interrupted.builder)
        _raise_system_exit(EXIT_INTERRUPT, interrupted)
    except KeyboardInterrupt as err:
        print_interrupt_diagnostics(cwd, cfg, DirectoryTreeBuilder(base_path=cwd, exclude_patterns=[]))
        _raise_system_exit(EXIT_INTERRUPT, err)


def _raise_system_exit(code: int, exc: BaseException, *, message: object | None = None) -> NoReturn:
    if message is not None:
        print(message, file=sys.stderr)
    raise SystemExit(code) from exc
