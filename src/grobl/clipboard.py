from __future__ import annotations

from pathlib import Path

import pyperclip  # type: ignore[import-untyped]


class ClipboardInterface:
    def copy(self, content: str) -> None:
        raise NotImplementedError


class PyperclipClipboard(ClipboardInterface):
    def __init__(self, fallback: "ClipboardInterface" | None = None) -> None:
        self.fallback = fallback

    def copy(self, content: str) -> None:  # noqa: PLR6301
        try:
            pyperclip.copy(content)
        except pyperclip.PyperclipException:
            if self.fallback:
                self.fallback.copy(content)
            else:
                print(content)


class StdoutClipboard(ClipboardInterface):
    def __init__(self, path: Path | None = None) -> None:
        self.path = path

    def copy(self, content: str) -> None:  # noqa: PLR6301
        if self.path:
            Path(self.path).write_text(content, encoding="utf-8")
        else:
            print(content)
