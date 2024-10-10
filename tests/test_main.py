import logging
from pathlib import Path

import pytest

from grobl.main import (
    enumerate_file_tree,
    find_common_ancestor,
    is_text_file,
    match_exclude_patterns,
    read_file_contents,
    read_groblignore,
    traverse_and_print_files,
    tree_structure_to_string,
)


@pytest.fixture
def sample_paths(tmp_path):
    python_project = tmp_path / "python_project"
    python_project.mkdir()
    (python_project / "requirements.txt").touch()
    (python_project / "main.py").write_text("print('Hello, World!')\n")

    js_project = tmp_path / "js_project"
    js_project.mkdir()
    (js_project / "package.json").touch()
    (js_project / "index.js").write_text("console.log('Hello, World!');\n")

    ts_project = tmp_path / "ts_project"
    ts_project.mkdir()
    (ts_project / "tsconfig.json").touch()
    (ts_project / "index.ts").write_text("console.log('Hello, World!');\n")

    rust_project = tmp_path / "rust_project"
    rust_project.mkdir()
    (rust_project / "Cargo.toml").touch()
    (rust_project / "main.rs").write_text('fn main() { println!("Hello, World!"); }\n')

    wasm_project = tmp_path / "wasm_project"
    wasm_project.mkdir()
    (wasm_project / "wasm").mkdir()
    (wasm_project / "index.wasm").touch()

    return [python_project, js_project, ts_project, rust_project, wasm_project]


def test_find_common_ancestor(sample_paths):
    common_ancestor = find_common_ancestor(sample_paths)
    assert common_ancestor.name == sample_paths[0].parent.name


def test_match_exclude_patterns():
    patterns = ["*.pyc", "node_modules/*"]
    assert match_exclude_patterns(Path("test.pyc"), patterns) is True
    assert match_exclude_patterns(Path("node_modules/test.js"), patterns) is True
    assert match_exclude_patterns(Path("test.py"), patterns) is False


def test_enumerate_file_tree(sample_paths):
    exclude_patterns = ["*.log", "node_modules/*"]
    file_tree = list(enumerate_file_tree([sample_paths[0]], exclude_patterns))
    assert "python_project" in file_tree[0]
    assert "main.py" in file_tree[1]


def test_tree_structure_to_string(sample_paths):
    exclude_patterns = ["*.log", "node_modules/*"]
    tree_string = tree_structure_to_string([sample_paths[0]], exclude_patterns)
    assert "python_project" in tree_string
    assert "main.py" in tree_string


def test_is_text_file():
    assert is_text_file(Path("test.py")) is True
    assert is_text_file(Path("test.pyc")) is False


def test_read_file_contents(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!\n")
    contents = read_file_contents(file_path)
    assert contents == "Hello, World!\n"

    # Test with a non-existent file
    non_existent_file = tmp_path / "non_existent.txt"
    contents = read_file_contents(non_existent_file)
    assert not contents  # Updated to use `not contents`

    # Test with a binary file (should be ignored gracefully)
    binary_file = tmp_path / "binary.bin"
    binary_file.write_bytes(b"\x00\x01\x02\x03")
    contents = read_file_contents(binary_file)
    assert not contents  # Updated to use `not contents`


def test_traverse_and_print_files(sample_paths):
    exclude_patterns = ["*.log", "node_modules/*"]
    clipboard_output, terminal_output, total_lines = traverse_and_print_files([sample_paths[0]], exclude_patterns)

    # Validate clipboard output
    assert "main.py" in clipboard_output
    assert "```" in clipboard_output  # Check for code block

    # Validate terminal output
    assert "main.py: (1 lines)" in terminal_output  # Check for line count
    assert total_lines == 1  # Check total lines


def test_read_groblignore(tmp_path):
    groblignore_path = tmp_path / ".groblignore"
    groblignore_content = """
    *.log
    *.tmp
    node_modules/
    """
    groblignore_path.write_text(groblignore_content.strip())
    ignore_patterns = read_groblignore(groblignore_path)
    assert "*.log" in ignore_patterns
    assert "*.tmp" in ignore_patterns
    assert "node_modules/" in ignore_patterns

    # Test empty or nonexistent .groblignore file
    empty_ignore = read_groblignore(tmp_path / "empty.groblignore")
    assert empty_ignore == []
