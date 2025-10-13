"""Shared CLI helpers used by multiple subcommands."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from grobl.config import LEGACY_TOML_CONFIG, TOML_CONFIG
from grobl.constants import (
    CONFIG_EXCLUDE_PRINT,
    CONFIG_EXCLUDE_TREE,
    EXIT_INTERRUPT,
    EXIT_PATH,
    EXIT_USAGE,
    HEAVY_DIRS,
    OutputMode,
    SummaryFormat,
    TableStyle,
)
from grobl.directory import DirectoryTreeBuilder
from grobl.errors import PathNotFoundError, ScanInterrupted
from grobl.services import ScanExecutor, ScanOptions
from grobl.utils import is_text

if TYPE_CHECKING:
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


ConfirmFn = Callable[[str], bool]


def _default_confirm(msg: str) -> bool:
    resp = input(msg).strip().lower()
    return resp == "y"


def _detect_heavy_dirs(paths: tuple[Path, ...]) -> set[str]:
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
    confirm: ConfirmFn = _default_confirm,
) -> None:
    if assume_yes:
        return
    found = _detect_heavy_dirs(paths)
    explicit_heavy = any({p.name for p in paths} & HEAVY_DIRS) or any(
        d in set(p.parts) for p in paths for d in HEAVY_DIRS
    )
    if not ignore_defaults and not explicit_heavy:
        return
    if not found:
        return
    joined = ", ".join(sorted(found))
    msg = f"Warning: this scan may include heavy directories: {joined}. Continue? (y/N): "
    logger.warning("potential heavy scan; dirs=%s", joined)
    if not confirm(msg):
        raise SystemExit(EXIT_USAGE)


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


def _maybe_offer_legacy_migration(
    base: Path, *, assume_yes: bool, confirm: ConfirmFn = _default_confirm
) -> None:
    legacy = base / LEGACY_TOML_CONFIG
    if not legacy.exists():
        return
    new = base / TOML_CONFIG
    refs = _scan_for_legacy_references(base)
    if refs:
        logger.warning("found references to legacy config '%s'", LEGACY_TOML_CONFIG)
        print(f"Found references to '{LEGACY_TOML_CONFIG}' in the repository:")
        for p, ln, text in refs[:MAX_REF_PREVIEW]:
            print(f"  - {p}:{ln}: {text}")
        if len(refs) > MAX_REF_PREVIEW:
            print(f"  ... and {len(refs) - MAX_REF_PREVIEW} more matches")
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
            logger.info("renamed legacy config '%s' -> '%s'", LEGACY_TOML_CONFIG, TOML_CONFIG)
            print(f"Renamed '{LEGACY_TOML_CONFIG}' -> '{TOML_CONFIG}'.")
        except OSError as e:
            logger.exception("could not rename legacy config")
            print(f"Could not rename legacy config: {e}", file=sys.stderr)


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
