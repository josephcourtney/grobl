from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

try:  # import at module level; skip the whole module if unavailable
    from hypothesis import given
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover - tooling availability
    pytest.skip("hypothesis not available", allow_module_level=True)

from grobl.binary_probe import probe_binary_details
from grobl.config import apply_runtime_ignores

SEGMENT = st.text(
    min_size=1,
    max_size=5,
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
)


@given(st.binary(min_size=0, max_size=4096))
def test_probe_binary_details_reports_exact_size(data: bytes) -> None:
    # write arbitrary byte content and ensure size matches
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "rand.bin"
        p.write_bytes(data)
        det = probe_binary_details(p)
        assert det["size_bytes"] == p.stat().st_size


@given(
    base=st.lists(SEGMENT, max_size=5),
    add=st.lists(SEGMENT, max_size=3),
    remove=st.lists(SEGMENT, max_size=3),
    no_ignore=st.booleans(),
)
def test_apply_runtime_ignores_matches_manual_logic(
    base: list[str], add: list[str], remove: list[str], *, no_ignore: bool
) -> None:
    cfg = {"exclude_tree": base.copy()}
    result = apply_runtime_ignores(
        cfg,
        add_ignore=tuple(add),
        remove_ignore=tuple(remove),
        add_ignore_files=(),
        no_ignore=no_ignore,
    )
    if no_ignore:
        assert result["exclude_tree"] == []
        return

    expected = base.copy()
    for pattern in add:
        if pattern not in expected:
            expected.append(pattern)
    for pattern in remove:
        if pattern in expected:
            expected.remove(pattern)
    assert result["exclude_tree"] == expected
