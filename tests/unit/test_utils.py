from __future__ import annotations

import os
from pathlib import Path

import pytest

from grobl.errors import PathNotFoundError
from grobl.utils import detect_text, find_common_ancestor, is_text

try:  # import at module level; skip the whole module if unavailable
    from hypothesis import given
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover - tooling availability
    pytest.skip("hypothesis not available", allow_module_level=True)

from grobl.config import apply_runtime_ignores


def test_find_common_ancestor_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        find_common_ancestor([])


def test_find_common_ancestor_single_path(tmp_path: Path) -> None:
    got = find_common_ancestor([tmp_path])
    assert got == tmp_path


@pytest.mark.skipif(os.name != "posix", reason="POSIX-only path assumptions")
def test_find_common_ancestor_root_rejected() -> None:
    with pytest.raises(PathNotFoundError):
        find_common_ancestor([Path("/"), Path("/tmp")])  # noqa: S108 - controlled use in test


def test_is_text_missing_file_returns_false(tmp_path: Path) -> None:
    missing = tmp_path / "nope.txt"
    assert is_text(missing) is False
    detection = detect_text(missing)
    assert detection.is_text is False
    assert detection.content is None


def test_detect_text_prefetches_content(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("héllo\nworld", encoding="utf-8")

    detection = detect_text(sample)

    assert detection.is_text is True
    assert detection.content == sample.read_text(encoding="utf-8", errors="ignore")


def test_detect_text_binary_payload(tmp_path: Path) -> None:
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"\x00\xff\x01\x02")

    detection = detect_text(blob)

    assert detection.is_text is False
    assert detection.content is None


@pytest.mark.parametrize(
    ("components", "expected_rel"),
    [
        (("a",), "a"),
        (("a", "a/b"), "a"),
        (("x/y/z", "x/y/w"), "x/y"),
    ],
)
def test_common_ancestor_param(tmp_path: Path, components: tuple[str, ...], expected_rel: str) -> None:
    paths = [tmp_path / c for c in components]
    got = find_common_ancestor(paths)
    expected = tmp_path / expected_rel
    assert got == expected


@pytest.mark.skipif(os.name != "posix", reason="POSIX-only path assumptions")
def test_common_ancestor_disjoint_drives_like(tmp_path: Path) -> None:
    # Mix an absolute path outside /private/var with tmp_path so only root is shared -> rejected
    with pytest.raises(PathNotFoundError):
        find_common_ancestor([Path("/usr"), tmp_path / "q"])


SEGMENT = st.text(
    min_size=1,
    max_size=5,
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
)


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


def test_common_ancestor_config_base(tmp_path: Path) -> None:
    base = tmp_path / "proj"
    (base / "a").mkdir(parents=True)
    (base / "b").mkdir(parents=True)
    p1 = base / "a" / "x.txt"
    p2 = base / "b" / "y.txt"
    p1.write_text("one", encoding="utf-8")
    p2.write_text("two", encoding="utf-8")

    common = find_common_ancestor([p1, p2])
    assert common == base
