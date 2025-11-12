from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from grobl import tty
from grobl.tty import TableStyle

if TYPE_CHECKING:
    import pytest


def test_stdout_is_tty_handles_missing_attribute(monkeypatch: pytest.MonkeyPatch) -> None:
    # Replace stdout with an object that lacks .isatty
    monkeypatch.setattr(sys, "stdout", object(), raising=True)
    assert tty.stdout_is_tty() is False


def test_resolve_table_style_auto_and_clipboard_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    # Auto -> FULL when tty, COMPACT otherwise
    monkeypatch.setattr(tty, "stdout_is_tty", lambda: True, raising=True)
    assert tty.resolve_table_style(TableStyle.AUTO) is TableStyle.FULL
    monkeypatch.setattr(tty, "stdout_is_tty", lambda: False, raising=True)
    assert tty.resolve_table_style(TableStyle.AUTO) is TableStyle.COMPACT

    # clipboard_allowed depends on TTY and flags/config
    monkeypatch.setattr(tty, "stdout_is_tty", lambda: True, raising=True)
    assert tty.clipboard_allowed({}, no_clipboard_flag=False) is True
    assert tty.clipboard_allowed({}, no_clipboard_flag=True) is False
