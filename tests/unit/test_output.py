from __future__ import annotations

import io
import sys
from pathlib import Path

import pyperclip
import pytest

from grobl.errors import ClipboardUnavailableError, OutputWriteError
from grobl.output import build_writer_from_config

pytestmark = pytest.mark.medium


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


def test_writer_file_failure_is_domain_error(tmp_path: Path) -> None:
    writer = build_writer_from_config(copy=False, output=tmp_path)

    with pytest.raises(OutputWriteError, match="cannot write output"):
        writer("payload")


def test_writer_clipboard_failure_is_domain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_copy(_value: str) -> None:
        msg = "clipboard backend missing"
        raise pyperclip.PyperclipException(msg)

    monkeypatch.setattr(pyperclip, "copy", fail_copy, raising=True)

    writer = build_writer_from_config(copy=True, output=None)
    with pytest.raises(ClipboardUnavailableError, match="clipboard unavailable"):
        writer("payload")


def test_writer_stdout_failure_is_domain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingStdout(io.StringIO):
        def write(self, value: str) -> int:
            _ = value
            msg = "stream unavailable"
            raise OSError(msg)

    monkeypatch.setattr(sys, "stdout", FailingStdout(), raising=True)
    writer = build_writer_from_config(copy=False, output=Path("-"))

    with pytest.raises(OutputWriteError, match="cannot write output stdout"):
        writer("payload")
