import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import pyperclip

from grobl.directory import (
    DirectoryTreeBuilder,
    filter_items,
)
from grobl.cli import main, process_paths


def test_directory_tree_builder_adds_entries_and_files():
    builder = DirectoryTreeBuilder(Path("/test"), [])
    builder.add_directory(Path("/test/dir"), "", is_last=True)
    assert builder.tree_output == ["└── dir"]

    # Test adding a file and metadata
    builder = DirectoryTreeBuilder(Path("/test"), [])
    builder.add_file_to_tree(Path("/test/file.txt"), "", is_last=True)
    builder.record_metadata(Path("file.txt"), 5, 42, 0)
    builder.add_file(Path("/test/file.txt"), Path("file.txt"), 5, 42, 0, "content")
    assert (
        '<file:content name="file.txt" lines="5" chars="42">' in builder.file_contents
    )
    assert builder.total_lines == 5
    assert builder.total_characters == 42


def test_filter_items_skips_excluded(temp_directory):
    base = temp_directory
    paths = [base / "src"]
    patterns = ["*.pyc", "__pycache__"]

    (base / "src" / "skip.pyc").write_text("should be skipped", encoding="utf-8")
    (base / "src" / "main.py").write_text("should be included", encoding="utf-8")

    items = list((base / "src").iterdir())
    filtered = filter_items(items, paths, patterns, base)

    assert (base / "src" / "skip.pyc") not in filtered
    assert (base / "src" / "main.py") in filtered


def test_process_paths_includes_files(temp_directory, mock_clipboard):
    with patch("grobl.cli.print"):
        process_paths([temp_directory / "src"], {}, mock_clipboard)
    out = mock_clipboard.copied_content
    assert "main.py" in out
    assert "utils.py" in out


def test_full_directory_scan(temp_directory, mock_clipboard):
    with patch("grobl.cli.print"):
        process_paths([temp_directory], {}, mock_clipboard)
    out = mock_clipboard.copied_content
    assert "├── src" in out
    assert "└── tests" in out


def test_exclude_patterns_work(temp_directory, mock_clipboard):
    # add excluded file
    (temp_directory / "src" / "skip.pyc").write_text("x", encoding="utf-8")
    with patch("grobl.cli.print"):
        process_paths([temp_directory], {"exclude_tree": ["*.pyc"]}, mock_clipboard)
    out = mock_clipboard.copied_content
    assert "skip.pyc" not in out


def test_unicode_handling(temp_directory, mock_clipboard):
    ufile = temp_directory / "src" / "uni.py"
    ufile.write_text("Hello 世界", encoding="utf-8")
    with patch("grobl.cli.print"):
        process_paths([temp_directory], {}, mock_clipboard)
    out = mock_clipboard.copied_content
    assert "uni.py" in out
    assert "世界" in out


def test_cli_basic_run(monkeypatch, tmp_path):
    # Create a fake cwd with minimal files
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    # Mock clipboard + process paths
    monkeypatch.setattr(
        "grobl.cli.PyperclipClipboard",
        lambda fallback=None: type(
            "MockClipboard", (), {"copy": lambda _self, _content: None}
        )(),
    )
    monkeypatch.setattr("grobl.cli.human_summary", lambda *_a, **_k: None)

    # Fake sys.argv
    monkeypatch.setattr(sys, "argv", ["grobl"])

    # Run!
    main()


def test_cli_migrate_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["grobl", "migrate-config"])
    monkeypatch.setattr("grobl.cli.migrate_config", lambda *_a, **_k: None)

    with pytest.raises(SystemExit) as e:
        main()
    exc = e.value
    assert isinstance(exc, SystemExit)
    assert exc.code == 0


def test_binary_file_in_tree_without_content(tmp_path, mock_clipboard):
    # Write a little “binary” blob with a null byte
    binf = tmp_path / "foo.bin"
    binf.write_bytes(b"THIS\x00IS\x01BINARY")

    # Run
    with patch("grobl.cli.print"):
        process_paths([tmp_path], {}, mock_clipboard)
    out = mock_clipboard.copied_content

    # It should appear in the <directory>…</directory> section…
    assert "foo.bin" in out.split("</directory>")[0]
    # …but we should never open it as a <file:content>
    assert '<file:content name="foo.bin"' not in out


def test_no_clipboard_prints_output(monkeypatch, tmp_path, capsys):
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("grobl.cli.human_summary", lambda *_a, **_k: None)
    monkeypatch.setattr(sys, "argv", ["grobl", "--no-clipboard"])
    main()
    out = capsys.readouterr().out
    assert "file.txt" in out


def test_output_flag_writes_file(monkeypatch, tmp_path):
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    out_file = tmp_path / "out.md"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("grobl.cli.human_summary", lambda *_a, **_k: None)
    monkeypatch.setattr(sys, "argv", ["grobl", "--output", str(out_file)])
    main()
    assert out_file.exists()
    assert "file.txt" in out_file.read_text(encoding="utf-8")


def test_add_and_remove_ignore(monkeypatch, tmp_path, capsys):
    (tmp_path / "keep.txt").write_text("k", encoding="utf-8")
    (tmp_path / "skip.log").write_text("s", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("grobl.cli.human_summary", lambda *_a, **_k: None)
    # Add ignore for *.log
    monkeypatch.setattr(
        sys, "argv", ["grobl", "--no-clipboard", "--add-ignore", "*.log"]
    )
    main()
    out = capsys.readouterr().out
    assert "skip.log" not in out
    # Remove ignore for *.log
    monkeypatch.setattr(
        sys, "argv", ["grobl", "--no-clipboard", "--remove-ignore", "*.log"]
    )
    main()
    out = capsys.readouterr().out
    assert "skip.log" in out


def test_clipboard_fallback(monkeypatch, tmp_path, capsys):
    (tmp_path / "file.txt").write_text("hi", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("grobl.cli.human_summary", lambda *_a, **_k: None)
    monkeypatch.setattr(
        pyperclip,
        "copy",
        lambda _c: (_ for _ in ()).throw(pyperclip.PyperclipException("fail")),
    )
    monkeypatch.setattr(sys, "argv", ["grobl"])
    main()
    out = capsys.readouterr().out
    assert "file.txt" in out
