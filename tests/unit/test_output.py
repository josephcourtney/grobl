from __future__ import annotations

import io
import sys
from pathlib import Path

import pyperclip
import pytest

from grobl.output import build_writer_from_config

pytestmark = pytest.mark.small


def test_writer_copy_uses_clipboard(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_copy(value: str) -> None:  # pragma: no cover - placeholder
        captured["text"] = value

    monkeypatch.setattr(pyperclip, "copy", fake_copy, raising=True)
    writer = build_writer_from_config(copy=True, output=None)
    writer("payload")
    assert captured["text"] == "payload"


def test_writer_output_file(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    writer = build_writer_from_config(copy=False, output=out)
    writer("hello")
    assert out.read_text(encoding="utf-8") == "hello"


def test_writer_output_dash_writes_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf, raising=True)

    writer = build_writer_from_config(copy=False, output=Path("-"))
    writer("line")
    assert buf.getvalue() == "line"


def test_writer_requires_destination() -> None:
    with pytest.raises(ValueError, match="destination"):
        build_writer_from_config(copy=False, output=None)
