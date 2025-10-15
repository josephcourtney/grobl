from __future__ import annotations

import os
from pathlib import Path

import pytest

from grobl.errors import PathNotFoundError
from grobl.utils import find_common_ancestor


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
