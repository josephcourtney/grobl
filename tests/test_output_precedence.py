from __future__ import annotations

import io
import sys
from pathlib import Path

import pyperclip

from grobl.output import build_writer_from_config


def test_output_goes_to_file_first(tmp_path: Path, monkeypatch: object) -> None:
    out = tmp_path / "out.txt"
    writer = build_writer_from_config(cfg={}, no_clipboard_flag=True, output=out)
    writer("hello")
    assert out.read_text(encoding="utf-8") == "hello"


def test_clipboard_failure_falls_back_to_stdout(monkeypatch: object) -> None:
    # Force TTY so clipboard_allowed() would return True
    class DummyStdout(io.StringIO):
        def isatty(self) -> bool:  # type: ignore[override]
            return True

    buf = DummyStdout()
    monkeypatch.setattr(sys, "stdout", buf)

    # Cause pyperclip to fail
    def boom(_: str) -> None:
        raise pyperclip.PyperclipException("fail")

    monkeypatch.setattr(pyperclip, "copy", boom)
    writer = build_writer_from_config(cfg={}, no_clipboard_flag=False, output=None)
    writer("hi")
    assert "hi" in buf.getvalue()

