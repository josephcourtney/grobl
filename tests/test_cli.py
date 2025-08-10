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


def _silence_summary(monkeypatch):
    # Avoid noisy tree/summary printing; we only care about the LLM-tagged output.
    monkeypatch.setattr("grobl.cli.human_summary", lambda *_a, **_k: None)


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


def test_cli_accepts_single_positional_path(monkeypatch, tmp_path, capsys):
    """
    Running `grobl tests` should treat 'tests' as a directory path (not a subcommand)
    and include only files from that directory in the emitted <directory> block.
    """
    _silence_summary(monkeypatch)
    # Arrange: cwd with a 'tests' dir and an unrelated file next to it
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "inside.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("nope", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    # Act
    monkeypatch.setattr(sys, "argv", ["grobl", "--no-clipboard", "tests"])
    main()
    out = capsys.readouterr().out

    # Assert: output contains only the target path contents
    assert '<directory name="tests"' in out
    assert "inside.py" in out
    assert "outside.txt" not in out  # should not scan siblings


def test_cli_accepts_multiple_positional_paths_and_sets_common_ancestor(
    monkeypatch, tmp_path, capsys
):
    """
    When given multiple paths, the directory tag should reflect their deepest common
    ancestor, and files from each path should be included.
    """
    _silence_summary(monkeypatch)
    (tmp_path / "pkg_a").mkdir()
    (tmp_path / "pkg_b").mkdir()
    (tmp_path / "pkg_a" / "a.py").write_text("a=1", encoding="utf-8")
    (tmp_path / "pkg_b" / "b.py").write_text("b=2", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        sys,
        "argv",
        ["grobl", "--no-clipboard", "pkg_a", "pkg_b"],
    )
    main()
    out = capsys.readouterr().out

    # The <directory> tag should name the common ancestor (tmp_path's basename)
    assert f'<directory name="{tmp_path.name}" path="{tmp_path}"' in out
    assert "a.py" in out and "b.py" in out


def test_cli_path_named_tests_is_not_misparsed_as_command(
    monkeypatch, tmp_path, capsys
):
    """
    Historical bug: passing 'tests' was treated like a bad subcommand.
    This asserts it's correctly handled as a directory.
    """
    _silence_summary(monkeypatch)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.py").write_text("x=1", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(sys, "argv", ["grobl", "--no-clipboard", "tests"])
    main()
    out = capsys.readouterr().out

    assert '<directory name="tests"' in out
    assert "t.py" in out


def test_config_sets_default_cli_options(monkeypatch, tmp_path):
    (tmp_path / "file.txt").write_text("hello world", encoding="utf-8")
    cfg_text = (
        "no_clipboard = true\n"
        "tokens = true\n"
        'model = "gpt-test"\n'
        "budget = 5000\n"
        "force_tokens = true\n"
        "verbose = true\n"
    )
    (tmp_path / ".grobl.config.toml").write_text(cfg_text, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "grobl.cli.load_tokenizer", lambda name: (lambda text: len(text.split()))
    )
    monkeypatch.setattr(
        "grobl.cli.MODEL_SPECS",
        {"gpt-test": {"tokenizer": "fake-enc", "budget": {"default": 32000}}},
    )
    captured: dict[str, object] = {}

    class DummyStdoutClipboard:
        def __init__(self, output_path: Path | None = None):  # noqa: D401, ARG002
            captured["clipboard"] = "stdout"

        def copy(self, content: str) -> None:  # noqa: D401, ARG002
            pass

    monkeypatch.setattr("grobl.cli.StdoutClipboard", DummyStdoutClipboard)
    monkeypatch.setattr(
        "grobl.cli.PyperclipClipboard",
        lambda fallback=None: (_ for _ in ()).throw(RuntimeError("clipboard used")),
    )

    def fake_process(
        paths,
        cfg,
        clipboard,
        builder,
        *,
        tokens,
        tokenizer_name,
        tokens_for,
        budget,
        force_tokens,
        verbose,
    ):
        captured["tokens"] = tokens
        captured["tokenizer_name"] = tokenizer_name
        captured["budget"] = budget
        captured["force_tokens"] = force_tokens
        captured["verbose"] = verbose

    monkeypatch.setattr("grobl.cli.process_paths", fake_process)
    monkeypatch.setattr("grobl.cli.human_summary", lambda *_a, **_k: None)
    monkeypatch.setattr(sys, "argv", ["grobl"])
    main()
    assert captured["clipboard"] == "stdout"
    assert captured["tokens"] is True
    assert captured["tokenizer_name"] == "fake-enc"
    assert captured["budget"] == 5000
    assert captured["force_tokens"] is True
    assert captured["verbose"] is True


def test_init_config_writes_default(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["grobl", "init-config"])
    with pytest.raises(SystemExit):
        main()
    assert (tmp_path / ".grobl.config.toml").exists()


def test_init_config_project_root(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    sub = tmp_path / "pkg"
    sub.mkdir()
    monkeypatch.chdir(sub)
    monkeypatch.setattr(sys, "argv", ["grobl", "init-config"])
    monkeypatch.setattr("builtins.input", lambda _=None: "y")
    with pytest.raises(SystemExit):
        main()
    assert (tmp_path / ".grobl.config.toml").exists()


def test_model_alias_and_tier_budget(monkeypatch, tmp_path):
    (tmp_path / "file.txt").write_text("hello world", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "grobl.cli.load_tokenizer", lambda name: (lambda text: len(text.split()))
    )
    monkeypatch.setattr(
        "grobl.cli.MODEL_SPECS",
        {
            "gpt-4.1": {"tokenizer": "fake", "budget": {"plus": 64000}},
            "gpt-5": {"tokenizer": "fake", "budget": {"plus": 64000}},
        },
    )
    captured: dict[str, object] = {}

    def fake_summary(
        lines, total_lines, total_chars, *, total_tokens, tokenizer, budget
    ):
        captured["tokenizer"] = tokenizer
        captured["budget"] = budget

    monkeypatch.setattr("grobl.cli.human_summary", fake_summary)
    monkeypatch.setattr(
        sys, "argv", ["grobl", "--no-clipboard", "--model", "gpt-5:plus"]
    )
    main()
    assert captured["tokenizer"] == "fake"
    assert captured["budget"] == 64000
