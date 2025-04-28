from pathlib import Path

import pytest

from grobl.errors import (
    ERROR_MSG_EMPTY_PATHS,
    ERROR_MSG_NO_COMMON_ANCESTOR,
    PathNotFoundError,
)
from grobl.utils import (
    find_common_ancestor,
    is_text,
    read_text,
)


def test_find_common_ancestor_empty_list():
    with pytest.raises(ValueError, match=ERROR_MSG_EMPTY_PATHS):
        find_common_ancestor([])


def test_find_common_ancestor_no_common():
    paths = [Path("/a/b"), Path("/c/d")]
    with pytest.raises(PathNotFoundError, match=ERROR_MSG_NO_COMMON_ANCESTOR):
        find_common_ancestor(paths)


def test_is_text_and_read_text(temp_directory):
    text_file = temp_directory / "src" / "main.py"
    assert is_text(text_file) is True
    content = read_text(text_file)
    assert "def main():" in content

    # Nonexistent file should return False for is_text
    assert is_text(temp_directory / "no_such_file.txt") is False
