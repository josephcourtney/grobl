"""Output strategies and factories for writing scan results."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import pyperclip

from grobl.constants import PayloadSink
from grobl.logging_utils import StructuredLogEvent, get_logger, log_event

from .tty import stdout_is_tty

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = get_logger(__name__)

MAX_CLIPBOARD_RETRIES = 2


class OutputStrategy(Protocol):
    """Write-only sink for the final payload."""

    def write(self, content: str) -> None: ...


class FileOutput:
    """Output strategy that writes to a file path."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, content: str) -> None:
        self._path.write_text(content, encoding="utf-8")


class ClipboardOutput:
    """Output strategy that writes to the system clipboard."""

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
            raise last_error


class StdoutOutput:
    """Output strategy that prints to stdout."""

    @staticmethod
    def write(content: str) -> None:
        sys.stdout.write(content)
        sys.stdout.flush()


@dataclass(frozen=True, slots=True)
class StrategyLink:
    """Chainable link describing how to invoke an :class:`OutputStrategy`."""

    strategy: OutputStrategy
    suppress_errors: bool = False

    def write(self, content: str) -> bool:
        try:
            self.strategy.write(content)
        except Exception:
            if not self.suppress_errors:
                raise
            logger.debug("suppressing writer failure", exc_info=True)
            return False
        return True


@dataclass(slots=True)
class StrategyChain:
    """Compose multiple strategies respecting precedence and fallbacks."""

    links: tuple[StrategyLink, ...]

    def __call__(self, content: str) -> None:
        self.write(content)

    def write(self, content: str) -> None:
        if not content:
            return
        for link in self.links:
            if link.write(content):
                return


@dataclass(frozen=True, slots=True)
class OutputPreferences:
    """Collected CLI/config preferences for output selection."""

    output_file: Path | None
    sink: PayloadSink


@dataclass(slots=True)
class OutputStrategyFactory:
    """Factory responsible for constructing output chains."""

    clipboard_strategy: OutputStrategy | None = None
    stdout_strategy: OutputStrategy | None = None

    def create(self, *, preferences: OutputPreferences) -> StrategyChain:
        stdout_strategy = self.stdout_strategy or StdoutOutput()
        clipboard_strategy = self.clipboard_strategy or ClipboardOutput()
        links: list[StrategyLink] = []
        sink = preferences.sink
        if sink is PayloadSink.AUTO:
            if preferences.output_file is not None:
                links.append(StrategyLink(strategy=FileOutput(preferences.output_file)))
            else:
                if stdout_is_tty():
                    links.append(StrategyLink(strategy=clipboard_strategy, suppress_errors=True))
                links.append(StrategyLink(strategy=stdout_strategy))
        elif sink is PayloadSink.CLIPBOARD:
            clipboard_link = StrategyLink(
                strategy=clipboard_strategy,
                suppress_errors=True,
            )
            stdout_link = StrategyLink(strategy=stdout_strategy)
            links.extend((clipboard_link, stdout_link))
        elif sink is PayloadSink.STDOUT:
            links.append(StrategyLink(strategy=stdout_strategy))
        elif sink is PayloadSink.FILE:
            if preferences.output_file is None:
                msg = "file sink requires an output path"
                raise ValueError(msg)
            links.append(StrategyLink(strategy=FileOutput(preferences.output_file)))
        else:  # pragma: no cover - defensive programming
            msg = f"unsupported sink: {sink}"
            raise ValueError(msg)
        return StrategyChain(tuple(links))


@dataclass(frozen=True)
class OutputSinkAdapter:
    """Adapter turning a chain into a plain callable."""

    write_fn: Callable[[str], None]

    def __call__(self, content: str) -> None:
        self.write_fn(content)

    def write(self, content: str) -> None:
        self(content)


def compose_output_strategy(*, output_file: Path | None, sink: PayloadSink) -> OutputSinkAdapter:
    """Build a writer chain driven by the requested sink preferences."""
    factory = OutputStrategyFactory()
    preferences = OutputPreferences(output_file=output_file, sink=sink)
    chain = factory.create(preferences=preferences)
    return OutputSinkAdapter(write_fn=chain.write)


def build_writer_from_config(
    *,
    sink: PayloadSink,
    output: Path | None,
) -> Callable[[str], None]:
    """Centralize writer creation based on config and CLI flags."""
    return compose_output_strategy(output_file=output, sink=sink)
