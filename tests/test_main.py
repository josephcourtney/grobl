from pathlib import Path
from unittest.mock import patch

import pytest

from grobl.main import (
    ERROR_MSG_EMPTY_PATHS,
    ERROR_MSG_NO_COMMON_ANCESTOR,
    ClipboardInterface,
    DirectoryTreeBuilder,
    PathNotFoundError,
    count_lines,
    escape_markdown,
    filter_items,
    find_common_ancestor,
    is_text_file,
    match_exclude_patterns,
    process_paths,
    read_file_contents,
    read_groblignore,
)


# Test Fixtures
@pytest.fixture
def mock_clipboard():
    class MockClipboard(ClipboardInterface):
        def __init__(self):
            self.copied_content = None

        def copy(self, content: str) -> None:
            self.copied_content = content

    return MockClipboard()


@pytest.fixture
def temp_directory(tmp_path):
    # Create a temporary directory structure for testing
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create some test files and directories
    (project_dir / "src").mkdir()
    (project_dir / "src" / "main.py").write_text("def main():\n    pass\n")
    (project_dir / "src" / "utils.py").write_text("def util():\n    return True")
    (project_dir / "tests").mkdir()
    (project_dir / "tests" / "test_main.py").write_text("def test_main():\n    assert True")
    (project_dir / ".groblignore").write_text("*.pyc\n__pycache__/")

    return project_dir


# Test Markdown Escaping
def test_escape_markdown():
    test_cases = [
        ("Hello *world*", r"Hello \*world\*"),
        ("_underscore_", r"\_underscore\_"),
        ("#header", r"\#header"),
        ("(parentheses)", r"\(parentheses\)"),
        ("normal text", "normal text"),
        ("multiple * _ # []", r"multiple \* \_ \# \[\]"),
    ]

    for input_text, expected in test_cases:
        assert escape_markdown(input_text) == expected


def test_find_common_ancestor_empty_list():
    with pytest.raises(ValueError, match=ERROR_MSG_EMPTY_PATHS):
        find_common_ancestor([])


def test_find_common_ancestor_no_common():
    paths = [Path("/home/user1"), Path("/home/user2"), Path("/var/log")]
    with pytest.raises(PathNotFoundError, match=ERROR_MSG_NO_COMMON_ANCESTOR):
        find_common_ancestor(paths)


# Test DirectoryTreeBuilder
def test_directory_tree_builder():
    builder = DirectoryTreeBuilder(Path("/test"), [])

    # Test directory addition
    builder.add_directory(Path("/test/dir"), "", is_last=True)
    assert builder.tree_output == ["└── dir"]

    # Test file addition
    builder.add_file(Path("/test/file.txt"), 10, 100, "content")
    assert "file.txt: (10 lines | 100 characters)" in builder.file_metadata
    assert builder.total_lines == 10
    assert builder.total_characters == 100


# Test File Operations
def test_is_text_file(temp_directory):
    text_file = temp_directory / "src" / "main.py"
    assert is_text_file(text_file) is True

    # Test non-existent file
    assert is_text_file(temp_directory / "nonexistent.txt") is False


def test_read_file_contents(temp_directory):
    file_path = temp_directory / "src" / "main.py"
    content = read_file_contents(file_path)
    assert "def main():" in content
    assert "pass" in content


def test_count_lines(temp_directory):
    file_path = temp_directory / "src" / "main.py"
    lines, chars = count_lines(file_path)
    assert lines == 2
    assert chars > 0


# Test File Filtering
def test_filter_items(temp_directory):
    base_path = temp_directory
    paths = [base_path / "src"]
    exclude_patterns = ["*.pyc", "__pycache__"]

    items = [
        base_path / "src" / "main.py",
        base_path / "src" / "test.pyc",
        base_path / "src" / "__pycache__",
    ]

    filtered = filter_items(items, paths, exclude_patterns, base_path)
    assert len(filtered) == 1
    assert filtered[0].name == "main.py"


def test_match_exclude_patterns(temp_directory):
    patterns = ["*.pyc", "__pycache__"]

    # Should match
    assert match_exclude_patterns(temp_directory / "test.pyc", patterns, temp_directory) is True

    # Should not match
    assert match_exclude_patterns(temp_directory / "test.py", patterns, temp_directory) is False


# Test Groblignore Reading
def test_read_groblignore(temp_directory):
    patterns = read_groblignore(temp_directory / ".groblignore")
    assert "*.pyc" in patterns
    assert "__pycache__/" in patterns
    assert ".git/" in patterns  # Default pattern


# Test Main Processing
def test_process_paths(temp_directory, mock_clipboard):
    paths = [temp_directory / "src"]
    exclude_patterns = ["*.pyc", "__pycache__"]

    with patch("grobl.main.print"):  # Suppress print output during test
        process_paths(paths, exclude_patterns, mock_clipboard)

    # Verify clipboard content
    assert mock_clipboard.copied_content is not None
    assert "main.py" in mock_clipboard.copied_content
    assert "utils.py" in mock_clipboard.copied_content
    assert "def main():" in mock_clipboard.copied_content


# Test Error Handling
def test_process_paths_nonexistent(mock_clipboard):
    with pytest.raises(FileNotFoundError):
        process_paths([Path("/nonexistent")], [], mock_clipboard)


# Integration Tests
def test_full_directory_scan(temp_directory, mock_clipboard):
    with patch("grobl.main.print"):  # Suppress print output during test
        process_paths([temp_directory], [], mock_clipboard)

    output = mock_clipboard.copied_content
    assert output is not None
    # Check for directory structure
    assert "├── src" in output
    assert "└── tests" in output
    # Check for file contents
    assert "main.py:" in output
    assert "test_main.py:" in output
    assert "def main():" in output
    assert "def test_main():" in output


def test_exclude_patterns_integration(temp_directory, mock_clipboard):
    # Create some files that should be excluded
    (temp_directory / "src" / "test.pyc").write_text("should be excluded")
    (temp_directory / "src" / "__pycache__").mkdir(exist_ok=True)

    with patch("grobl.main.print"):  # Suppress print output during test
        process_paths([temp_directory], ["*.pyc", "__pycache__"], mock_clipboard)

    output = mock_clipboard.copied_content
    assert output is not None
    assert "test.pyc" not in output
    assert "__pycache__" not in output


def test_unicode_handling(temp_directory, mock_clipboard):
    # Test handling of unicode characters in filenames and content
    unicode_content = "Hello 世界\nこんにちは"
    unicode_file = temp_directory / "src" / "unicode_test.py"
    unicode_file.write_text(unicode_content, encoding="utf-8")

    with patch("grobl.main.print"):  # Suppress print output during test
        process_paths([temp_directory], [], mock_clipboard)

    output = mock_clipboard.copied_content
    assert output is not None
    assert "unicode_test.py" in output
    assert "Hello 世界" in output
    assert "こんにちは" in output
