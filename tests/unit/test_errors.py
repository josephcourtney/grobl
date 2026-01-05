from __future__ import annotations

from pathlib import Path

import pytest

from grobl.directory import DirectoryTreeBuilder
from grobl.errors import ScanInterrupted

pytestmark = pytest.mark.small


def test_scan_interrupted_carries_state() -> None:
    c = Path("/tmp")  # noqa: S108 - path literal acceptable in test
    builder = DirectoryTreeBuilder(base_path=c, exclude_patterns=[])
    err = ScanInterrupted(builder, c)
    assert err.builder is builder
    assert err.common is c
