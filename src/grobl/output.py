"""Output strategies and factories for writing scan results."""

from __future__ import annotations

import logging
from dataclasses import dataclass
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
    """Output strategy that writes to a file path."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, content: str) -> None:
        self._path.write_text(content, encoding="utf-8")


class ClipboardOutput:
    """Output strategy that writes to the system clipboard."""

    @staticmethod
    def write(content: str) -> None:
        pyperclip.copy(content)


class StdoutOutput:
    """Output strategy that prints to stdout."""

    @staticmethod
    def write(content: str) -> None:
        print(content)


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
    allow_clipboard: bool


@dataclass(slots=True)
class OutputStrategyFactory:
    """Factory responsible for constructing output chains."""

    clipboard_strategy: OutputStrategy | None = None
    stdout_strategy: OutputStrategy | None = None

    def create(self, *, preferences: OutputPreferences) -> StrategyChain:
        stdout_strategy = self.stdout_strategy or StdoutOutput()
        clipboard_strategy = self.clipboard_strategy or ClipboardOutput()
        links: list[StrategyLink] = []
        if preferences.output_file:
            links.append(StrategyLink(strategy=FileOutput(preferences.output_file)))
        if preferences.allow_clipboard:
            links.append(StrategyLink(strategy=clipboard_strategy, suppress_errors=True))
        links.append(StrategyLink(strategy=stdout_strategy))
        return StrategyChain(tuple(links))


@dataclass(frozen=True)
class OutputSinkAdapter:
    """Adapter turning a chain into a plain callable."""

    write_fn: Callable[[str], None]

    def __call__(self, content: str) -> None:
        self.write_fn(content)

    def write(self, content: str) -> None:
        self(content)


def compose_output_strategy(*, output_file: Path | None, allow_clipboard: bool) -> OutputSinkAdapter:
    """Build a writer with precedence: file → clipboard (optional) → stdout."""
    factory = OutputStrategyFactory()
    preferences = OutputPreferences(output_file=output_file, allow_clipboard=allow_clipboard)
    chain = factory.create(preferences=preferences)
    return OutputSinkAdapter(write_fn=chain.write)


def build_writer_from_config(
    *,
    cfg: dict[str, object],
    no_clipboard_flag: bool,
    output: Path | None,
) -> Callable[[str], None]:
    """Centralize writer creation based on config and CLI flags."""
    allow_clipboard = clipboard_allowed(cfg, no_clipboard_flag=no_clipboard_flag)
    return compose_output_strategy(output_file=output, allow_clipboard=allow_clipboard)
