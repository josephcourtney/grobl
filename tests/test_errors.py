from __future__ import annotations

from pathlib import Path

from grobl.errors import ScanInterrupted


def test_scan_interrupted_carries_state() -> None:
    b = object()
    c = Path("/tmp")  # noqa: S108 - path literal acceptable in test
    err = ScanInterrupted(b, c)
    assert err.builder is b
    assert err.common is c
