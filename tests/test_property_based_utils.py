from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

try:  # import at module level; skip the whole module if unavailable
    from hypothesis import given
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover - tooling availability
    pytest.skip("hypothesis not available", allow_module_level=True)

from grobl.utils import probe_binary_details


@given(st.binary(min_size=0, max_size=4096))
def test_probe_binary_details_reports_exact_size(data: bytes) -> None:
    # write arbitrary byte content and ensure size matches
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "rand.bin"
        p.write_bytes(data)
        det = probe_binary_details(p)
        assert det["size_bytes"] == p.stat().st_size
