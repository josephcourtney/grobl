from __future__ import annotations

import io
import sys
from typing import TYPE_CHECKING

import pyperclip
import pytest

from grobl.constants import PayloadSink
from grobl.output import build_writer_from_config

if TYPE_CHECKING:
    from pathlib import Path


def test_sink_auto_prefers_file_when_output_provided(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    writer = build_writer_from_config(sink=PayloadSink.AUTO, output=out)
    writer("hello")
    assert out.read_text(encoding="utf-8") == "hello"


def test_sink_auto_prefers_clipboard_when_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    from grobl import output as output_mod

    monkeypatch.setattr(output_mod, "stdout_is_tty", lambda: True, raising=True)

    captured: dict[str, str] = {}

    def fake_copy(value: str) -> None:
        captured["text"] = value

    monkeypatch.setattr(output_mod.pyperclip, "copy", fake_copy, raising=True)

    class ExplodingStdout(io.StringIO):
        def write(self, _: str) -> int:  # type: ignore[override]
            msg = "stdout should not be used when clipboard succeeds"
            raise AssertionError(msg)

        def flush(self) -> None:  # type: ignore[override]
            return None

    monkeypatch.setattr(sys, "stdout", ExplodingStdout(), raising=True)

    writer = build_writer_from_config(sink=PayloadSink.AUTO, output=None)
    writer("payload")
    assert captured["text"] == "payload"


def test_sink_auto_uses_stdout_when_not_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    from grobl import output as output_mod

    monkeypatch.setattr(output_mod, "stdout_is_tty", lambda: False, raising=True)
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf, raising=True)
    writer = build_writer_from_config(sink=PayloadSink.AUTO, output=None)
    writer("plain")
    assert buf.getvalue() == "plain"


def test_sink_clipboard_falls_back_to_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf, raising=True)

    def boom(_: str) -> None:
        msg = "fail"
        raise pyperclip.PyperclipException(msg)

    monkeypatch.setattr(pyperclip, "copy", boom, raising=True)
    writer = build_writer_from_config(sink=PayloadSink.CLIPBOARD, output=None)
    writer("fallback")
    assert buf.getvalue() == "fallback"


def test_sink_stdout_writes_exact_even_with_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf, raising=True)
    out = tmp_path / "ignored.txt"
    writer = build_writer_from_config(sink=PayloadSink.STDOUT, output=out)
    writer("exact")
    assert buf.getvalue() == "exact"
    assert not out.exists()


def test_sink_file_requires_output_path() -> None:
    with pytest.raises(ValueError, match="file sink requires"):
        build_writer_from_config(sink=PayloadSink.FILE, output=None)
