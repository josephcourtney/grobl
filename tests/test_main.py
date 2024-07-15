import json
import pytest
from pathlib import Path
from grobl.main import (
    find_common_ancestor,
    match_exclude_patterns,
    enumerate_file_tree,
    tree_structure_to_string,
    is_text_file,
    read_file_contents,
    traverse_and_print_files,
    parse_pyproject_toml,
    gather_configs,
    detect_project_types,
    read_config_file
)

@pytest.fixture
def config():
    config_path = Path(__file__).parent / 'test_config.json'
    return read_config_file(config_path)

@pytest.fixture
def sample_paths(tmp_path):
    python_project = tmp_path / "python_project"
    python_project.mkdir()
    (python_project / "requirements.txt").touch()
    (python_project / "main.py").write_text("print('Hello, World!')")

    js_project = tmp_path / "js_project"
    js_project.mkdir()
    (js_project / "package.json").touch()
    (js_project / "index.js").write_text("console.log('Hello, World!');")

    ts_project = tmp_path / "ts_project"
    ts_project.mkdir()
    (ts_project / "tsconfig.json").touch()
    (ts_project / "index.ts").write_text("console.log('Hello, World!');")

    rust_project = tmp_path / "rust_project"
    rust_project.mkdir()
    (rust_project / "Cargo.toml").touch()
    (rust_project / "main.rs").write_text('fn main() { println!("Hello, World!"); }')

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

def test_enumerate_file_tree(sample_paths, config):
    exclude_patterns = config["ignore_patterns"]["python"]["exclude_tree"]
    file_tree = list(enumerate_file_tree([sample_paths[0]], exclude_patterns))
    assert "python_project" in file_tree[0]
    assert "main.py" in file_tree[1]

def test_tree_structure_to_string(sample_paths, config):
    exclude_patterns = config["ignore_patterns"]["python"]["exclude_tree"]
    tree_string = tree_structure_to_string([sample_paths[0]], exclude_patterns)
    assert "python_project" in tree_string
    assert "main.py" in tree_string

def test_is_text_file():
    assert is_text_file(Path("test.py")) is True
    assert is_text_file(Path("test.pyc")) is False

def test_read_file_contents(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!")
    contents = read_file_contents(file_path)
    assert contents == "Hello, World!"

    # Test with a non-existent file
    non_existent_file = tmp_path / "non_existent.txt"
    contents = read_file_contents(non_existent_file)
    assert contents == ""

    # Test with a binary file (should be ignored gracefully)
    binary_file = tmp_path / "binary.bin"
    binary_file.write_bytes(b'\x00\x01\x02\x03')
    contents = read_file_contents(binary_file)
    assert contents == ""

def test_traverse_and_print_files(sample_paths, config):
    exclude_patterns = config["ignore_patterns"]["python"]["exclude_tree"]
    exclude_print = config["ignore_patterns"]["python"]["exclude_print"]
    files_output = traverse_and_print_files([sample_paths[0]], exclude_patterns, exclude_print)
    assert "main.py" in files_output

def test_parse_pyproject_toml(tmp_path):
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text("""
    [tool.grobl]
    exclude_tree = ["*.log"]
    exclude_print = ["*.tmp"]
    """)
    config = parse_pyproject_toml(pyproject_toml)
    assert "*.log" in config["exclude_tree"]
    assert "*.tmp" in config["exclude_print"]

def test_gather_configs(tmp_path):
    project_path = tmp_path / "project"
    project_path.mkdir()
    (project_path / "pyproject.toml").write_text("""
    [tool.grobl]
    exclude_tree = ["*.log"]
    exclude_print = ["*.tmp"]
    """)
    paths = [project_path]
    configs = gather_configs(paths)
    assert "*.log" in configs["exclude_tree"]
    assert "*.tmp" in configs["exclude_print"]

def test_detect_project_types(sample_paths, config):
    project_types = detect_project_types([sample_paths[0]], config["project_types"])
    assert "python" in project_types
    project_types = detect_project_types([sample_paths[1]], config["project_types"])
    assert "javascript" in project_types

def test_read_config_file():
    config_path = Path(__file__).parent / 'test_config.json'
    config = read_config_file(config_path)
    assert "python" in config["project_types"]
    assert "*.pyc" in config["ignore_patterns"]["python"]["exclude_tree"]
