import sys
from unittest.mock import patch

import pytest

from grobl.cli import main, process_paths
from grobl.tokens import TokenizerNotAvailableError


def test_cli_tokens_summary(monkeypatch, tmp_path):
    (tmp_path / "file.txt").write_text("hello world", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "grobl.cli.load_tokenizer",
        lambda name: (lambda text: len(text.split())),
    )
    captured: dict[str, object] = {}

    def fake_summary(
        lines, total_lines, total_chars, *, total_tokens, tokenizer, budget
    ):
        captured["lines"] = lines
        captured["total_tokens"] = total_tokens
        captured["tokenizer"] = tokenizer

    monkeypatch.setattr("grobl.cli.human_summary", fake_summary)
    monkeypatch.setattr(sys, "argv", ["grobl", "--no-clipboard", "--tokens"])
    main()
    header = captured["lines"][0]
    assert "tokens" in header
    assert captured["total_tokens"] == 2
    assert captured["tokenizer"] == "cl100k_base"


def test_cli_tokens_error(monkeypatch, tmp_path, capsys):
    (tmp_path / "file.txt").write_text("hi", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "grobl.cli.load_tokenizer",
        lambda name: (_ for _ in ()).throw(
            TokenizerNotAvailableError(
                "Token counting requires 'tiktoken'. Install with 'pip install grobl[tokens]'"
            )
        ),
    )
    monkeypatch.setattr(sys, "argv", ["grobl", "--tokens"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert isinstance(exc.value, SystemExit)
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "tiktoken" in err


def test_skip_large_file_tokenization(monkeypatch, tmp_path, mock_clipboard):
    big = tmp_path / "big.txt"
    big.write_text("a" * 20, encoding="utf-8")
    monkeypatch.setattr(
        "grobl.cli.load_tokenizer", lambda name: (lambda text: len(text))
    )
    monkeypatch.setattr("grobl.tokens.TOKEN_LIMIT_BYTES", 10)
    with patch("grobl.cli.print"):
        builder = process_paths([tmp_path], {}, mock_clipboard, tokens=True)
    assert builder.total_tokens == 0
    cache_file = tmp_path / ".grobl.tokens.json"
    if cache_file.exists():
        cache_file.unlink()
    with patch("grobl.cli.print"):
        builder = process_paths(
            [tmp_path], {}, mock_clipboard, tokens=True, force_tokens=True
        )
    assert builder.total_tokens == 20
