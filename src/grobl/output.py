from __future__ import annotations

import contextlib
import logging
import sys
from typing import TYPE_CHECKING, Protocol

import pyperclip
from .tty import clipboard_allowed

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)


class OutputStrategy(Protocol):
    """Write-only sink for the final payload."""

    def write(self, content: str) -> None: ...


class FileOutput:
    """OutputStrategy that writes to a file path."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, content: str) -> None:
        self._path.write_text(content, encoding="utf-8")


class ClipboardOutput:
    """OutputStrategy that writes to clipboard."""

    @staticmethod
    def write(content: str) -> None:  # keep static contract simple
        pyperclip.copy(content)


class StdoutOutput:
    """OutputStrategy that writes to stdout."""

    @staticmethod
    def write(content: str) -> None:
        print(content)


class OutputSinkAdapter:
    """
    Tiny adapter to turn a bare write-function into an OutputStrategy.

    Why: simplifies injection from the CLI without reflection hacks.
    """

    def __init__(self, write_fn: Callable[[str], None]) -> None:
        self._write = write_fn

    def write(self, content: str) -> None:
        self._write(content)


def compose_output_strategy(
    *,
    output_file: Path | None,
    allow_clipboard: bool,
) -> Callable[[str], None]:
    """
    Build a writer with precedence: file → clipboard (optional) → stdout.

    Returns a callable `write(str)`.
    """
    file_strategy = FileOutput(output_file) if output_file else None
    clip_strategy = ClipboardOutput() if allow_clipboard else None
    out_strategy = StdoutOutput()

    def write(content: str) -> None:
        if not content:
            return
        if file_strategy:
            file_strategy.write(content)
            return
        if clip_strategy:
            with contextlib.suppress(Exception):
                clip_strategy.write(content)
                return
        out_strategy.write(content)

    return write


def build_writer_from_config(
    *,
    cfg: dict[str, object],
    no_clipboard_flag: bool,
    output: Path | None,
) -> Callable[[str], None]:
    """Centralize writer creation based on config and CLI flags."""
    # auto-disable clipboard for non-TTY stdout or when explicitly disabled
    allow_clipboard = clipboard_allowed(cfg, no_clipboard_flag=no_clipboard_flag)
    return compose_output_strategy(output_file=output, allow_clipboard=allow_clipboard)
