"""Clipboard backends used by the CLI."""

from __future__ import annotations

from pathlib import Path

import pyperclip  # type: ignore[import-untyped]


class ClipboardInterface:
    """Abstract clipboard interface."""

    def copy(self, content: str) -> None:  # pragma: no cover - interface method
        """Copy ``content`` to the clipboard."""
        raise NotImplementedError


class PyperclipClipboard(ClipboardInterface):
    """Clipboard implementation using :mod:`pyperclip`."""

    def __init__(self, fallback: "ClipboardInterface" | None = None) -> None:
        self.fallback = fallback

    def copy(self, content: str) -> None:  # noqa: PLR6301
        """Copy ``content`` to the system clipboard."""

        try:
            pyperclip.copy(content)
        except pyperclip.PyperclipException:
            if self.fallback:
                self.fallback.copy(content)
            else:
                print(content)


class StdoutClipboard(ClipboardInterface):
    """Fallback clipboard that writes to stdout or a file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path

    def copy(self, content: str) -> None:  # noqa: PLR6301
        """Write ``content`` to ``path`` or stdout."""

        if self.path:
            Path(self.path).write_text(content, encoding="utf-8")
        else:
            print(content)
