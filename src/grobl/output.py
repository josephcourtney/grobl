"""Output strategies for writing scan results."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pyperclip

from grobl.errors import ClipboardUnavailableError, OutputWriteError
from grobl.logging_utils import StructuredLogEvent, get_logger, log_event

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)
MAX_CLIPBOARD_RETRIES = 2


class FileOutput:
    """Write payload to a file path."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, content: str) -> None:
        try:
            self._path.write_text(content, encoding="utf-8")
        except OSError as err:
            raise OutputWriteError(f"cannot write output {self._path}: {err}") from err


class ClipboardOutput:
    """Write payload to the system clipboard."""

    @staticmethod
    def write(content: str) -> None:
        last_error: Exception | None = None
        for attempt in range(1, MAX_CLIPBOARD_RETRIES + 1):
            try:
                pyperclip.copy(content)
            except pyperclip.PyperclipException as err:  # pragma: no cover - backend dependent
                last_error = err
                if attempt < MAX_CLIPBOARD_RETRIES:
                    log_event(
                        logger,
                        StructuredLogEvent(
                            name="clipboard.retry",
                            message="clipboard copy failed; retrying",
                            level=logging.WARNING,
                            context={"attempt": attempt, "max_attempts": MAX_CLIPBOARD_RETRIES},
                        ),
                    )
                    continue
            else:
                return
        if last_error is not None:
            log_event(
                logger,
                StructuredLogEvent(
                    name="clipboard.failed",
                    message="clipboard copy failed after retries",
                    level=logging.ERROR,
                    context={"max_attempts": MAX_CLIPBOARD_RETRIES},
                ),
            )
            raise ClipboardUnavailableError("clipboard unavailable") from last_error


class StdoutOutput:
    """Write payload to stdout."""

    @staticmethod
    def write(content: str) -> None:
        try:
            sys.stdout.write(content)
            sys.stdout.flush()
        except BrokenPipeError:
            raise
        except OSError as err:
            raise OutputWriteError(f"cannot write output stdout: {err}") from err


def build_writer_from_config(*, copy: bool, output: Path | None) -> Callable[[str], None]:
    """Return a writer that sends payloads to the selected destination."""
    if copy:
        return ClipboardOutput.write
    if output is None:
        msg = "payload destination not specified"
        raise ValueError(msg)
    if output == Path("-"):
        return StdoutOutput.write
    return FileOutput(output).write
