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
def generate_sample_paths(tmp_path):
    """
    Generate a complex directory structure based on predefined patterns.
    The structure will include cases to test overlapping exclusions.
    """
    base = tmp_path / "folder_1"
    base.mkdir()

    # Patterns:
    # *.abc -> Reject all .abc files
    # folder_1/folder_2/folder_3 -> Reject everything in this subfolder
    # folder_1/*/*.py -> Reject python files in subdirectories of folder_1

    # Create files that match the "*.abc" pattern
    (base / "file1.abc").touch()
    (base / "file2.txt").touch()  # Not to be excluded

    # Create nested folder structure
    folder_2 = base / "folder_2"
    folder_2.mkdir()

    folder_3 = folder_2 / "folder_3"
    folder_3.mkdir()

    # Create files in folder_3 (should be excluded by folder_1/folder_2/folder_3)
    (folder_3 / "file_in_folder3.txt").touch()

    # Create subfolder inside folder_1 (for folder_1/*/*.py exclusion pattern)
    subfolder = base / "subfolder"
    subfolder.mkdir()

    (subfolder / "script.py").touch()  # Should be excluded
    (subfolder / "readme.md").touch()  # Should NOT be excluded

    # Create python file at top level of folder_1 (should NOT be excluded)
    (base / "main.py").touch()

    # Add a second-level folder inside folder_2 to test overlapping patterns
    subfolder_in_folder2 = folder_2 / "subfolder_in_folder2"
    subfolder_in_folder2.mkdir()

    (subfolder_in_folder2 / "module.py").touch()  # Should be excluded by folder_1/*/*.py

    # Return the base path and pattern list
    return base


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


def test_read_file_contents(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!\n")
    contents = read_file_contents(file_path)
    assert contents == "Hello, World!\n"

    # Test with a non-existent file
    non_existent_file = tmp_path / "non_existent.txt"
    contents = read_file_contents(non_existent_file)
    assert not contents  # Updated to use `not contents`


def test_traverse_and_print_files(sample_paths):
    exclude_patterns = ["*.log", "node_modules/*"]
    clipboard_output, terminal_output, total_lines = traverse_and_print_files(
        [sample_paths[0]], exclude_patterns
    )

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


def test_match_exclude_patterns(generate_sample_paths):
    base_path = generate_sample_paths
    ignore_patterns = ["*.abc", "folder_2/folder_3/**", "**/*.py"]

    assert match_exclude_patterns(base_path / "file1.abc", ignore_patterns, base_path) is True
    assert match_exclude_patterns(base_path / "file2.txt", ignore_patterns, base_path) is False

    # Test folder exclusion
    assert match_exclude_patterns(
        base_path / "folder_2/folder_3/file_in_folder3.txt",
        ignore_patterns,
        base_path,
    ) is True

    # Test exclusion of Python files in any subdirectory
    assert match_exclude_patterns(base_path / "subfolder/script.py", ignore_patterns, base_path) is True
    assert match_exclude_patterns(base_path / "subfolder/readme.md", ignore_patterns, base_path) is False

    # Ensure Python file inside nested subfolder is excluded
    assert match_exclude_patterns(
        base_path / "folder_2/subfolder_in_folder2/module.py",
        ignore_patterns,
        base_path,
    ) is True

    # Ensure Python file in base path is not excluded
    assert match_exclude_patterns(base_path / "main.py", ignore_patterns, base_path) is False


def test_enumerate_file_tree_with_groblignore(generate_sample_paths, tmp_path):
    base_path = generate_sample_paths
    groblignore_path = tmp_path / ".groblignore"
    groblignore_content = """
    *.abc
    folder_2/folder_3
    **/*.py
    """
    groblignore_path.write_text(groblignore_content.strip())
    ignore_patterns = read_groblignore(groblignore_path)

    file_tree = list(enumerate_file_tree([base_path], ignore_patterns))
    file_tree_string = "\n".join(file_tree)

    # Files excluded by *.abc
    assert "file1.abc" not in file_tree_string

    # Exclude everything in folder_2/folder_3
    assert "folder_3" not in file_tree_string
    assert "file_in_folder3.txt" not in file_tree_string

    # Exclude Python files in any subdirectories
    assert "script.py" not in file_tree_string
    assert "module.py" not in file_tree_string

    # Ensure files not matching the patterns are present
    assert "file2.txt" in file_tree_string
    assert "readme.md" in file_tree_string
    assert "main.py" in file_tree_string  # Since main.py is at the base level
