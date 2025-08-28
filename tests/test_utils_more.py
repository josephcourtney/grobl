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
