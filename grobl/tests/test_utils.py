from __future__ import annotations

import os
from pathlib import Path

import pytest

from grobl.errors import PathNotFoundError
from grobl.utils import find_common_ancestor, is_text


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
