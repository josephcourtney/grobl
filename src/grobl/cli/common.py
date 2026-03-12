"""Compatibility wrappers for CLI-facing imports.

Shared execution helpers live in :mod:`grobl.app.command_support`.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Never

from grobl.app.command_support import (
    MAX_REF_PREVIEW,
    ScanExecutor,
    ScanOptions,
    ScanParams,
    _scan_for_legacy_references,
    exit_on_broken_pipe,
    iter_legacy_references,
    print_interrupt_diagnostics,
)
from grobl.constants import (
    EXIT_INTERRUPT,
    EXIT_PATH,
    EXIT_USAGE,
    TableStyle,
)
from grobl.directory import DirectoryTreeBuilder
from grobl.errors import PathNotFoundError, ScanInterrupted
from grobl.ignore import LayeredIgnoreMatcher

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _execute_with_handling(
    *,
    params: ScanParams,
    cfg: dict[str, Any],
    cwd: Path,
    write_fn: Callable[[str], None],
    summary_style: TableStyle,
) -> tuple[str, dict[str, Any]]:
    """Thin compatibility wrapper that preserves legacy patch points for tests."""
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


def _raise_system_exit(code: int, exc: BaseException, *, message: object | None = None) -> Never:
    if message is not None:
        print(message, file=sys.stderr)
    raise SystemExit(code) from exc


__all__ = [
    "MAX_REF_PREVIEW",
    "ScanExecutor",
    "ScanOptions",
    "ScanParams",
    "_execute_with_handling",
    "_scan_for_legacy_references",
    "exit_on_broken_pipe",
    "iter_legacy_references",
    "print_interrupt_diagnostics",
]
