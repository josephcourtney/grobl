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
        lines,
        total_lines,
        total_chars,
        *,
        total_tokens,
        tokenizer,
        budget,
        table,
    ):
        captured["lines"] = lines
        captured["total_tokens"] = total_tokens
        captured["tokenizer"] = tokenizer
        captured["budget"] = budget

    monkeypatch.setattr("grobl.cli.human_summary", fake_summary)
    monkeypatch.setattr(
        sys, "argv", ["grobl", "--no-clipboard", "--tokens", "--budget", "100"]
    )
    main()
    header = captured["lines"][0]
    assert "tokens" in header and "included" in header
    assert header.split() == ["lines", "chars", "tokens", "included"]
    assert captured["budget"] == 100
    assert captured["total_tokens"] == 2
    assert captured["tokenizer"] == "o200k_base"


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


def test_list_token_models(monkeypatch, capsys):
    class Fake:
        @staticmethod
        def list_encoding_names():
            return ["a", "b"]

        class model:  # noqa: D401 - simple container
            MODEL_TO_ENCODING = {"m1": "a", "m2": "a", "m3": "b"}

    monkeypatch.setitem(sys.modules, "tiktoken", Fake)
    monkeypatch.setattr(sys, "argv", ["grobl", "models"])
    main()
    out = capsys.readouterr().out
    assert "a: m1, m2" in out
    assert "b: m3" in out


def test_invalid_tokenizer_model(monkeypatch, tmp_path, capsys):
    (tmp_path / "file.txt").write_text("hi", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    class Fake:
        @staticmethod
        def get_encoding(name):  # noqa: ARG002
            raise KeyError("bad")

        @staticmethod
        def list_encoding_names():
            return ["foo"]

    monkeypatch.setitem(sys.modules, "tiktoken", Fake)
    monkeypatch.setattr(
        "grobl.cli.PyperclipClipboard",
        lambda fallback=None: type("MC", (), {"copy": lambda self, c: None})(),
    )
    monkeypatch.setattr("grobl.cli.human_summary", lambda *_a, **_k: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["grobl", "--tokens", "--tokenizer", "bad"],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert isinstance(exc.value, SystemExit)
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "Available models: foo" in err


def test_verbose_tokens_prints_info(monkeypatch, tmp_path, mock_clipboard):
    (tmp_path / "file.txt").write_text("hi", encoding="utf-8")
    monkeypatch.setattr(
        "grobl.cli.load_tokenizer", lambda name: (lambda text: len(text.split()))
    )
    fake_tok = type("T", (), {"__version__": "1.0"})
    monkeypatch.setitem(sys.modules, "tiktoken", fake_tok)
    with patch("grobl.cli.print") as mock_print:
        process_paths([tmp_path], {}, mock_clipboard, tokens=True, verbose=True)
    mock_print.assert_any_call("Tokenizer: o200k_base (tiktoken 1.0)")


def test_model_option_sets_tokenizer_and_budget(monkeypatch, tmp_path):
    (tmp_path / "file.txt").write_text("hello world", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        "grobl.cli.load_tokenizer", lambda name: (lambda text: len(text.split()))
    )
    monkeypatch.setattr(
        "grobl.cli.MODEL_SPECS",
        {"gpt-test": {"tokenizer": "fake-enc", "budget": {"default": 32000}}},
    )
    captured: dict[str, object] = {}

    def fake_summary(
        lines,
        total_lines,
        total_chars,
        *,
        total_tokens,
        tokenizer,
        budget,
        table,
    ):
        captured["tokenizer"] = tokenizer
        captured["budget"] = budget
        captured["total_tokens"] = total_tokens

    monkeypatch.setattr("grobl.cli.human_summary", fake_summary)
    monkeypatch.setattr(sys, "argv", ["grobl", "--no-clipboard", "--model", "gpt-test"])
    main()
    assert captured["tokenizer"] == "fake-enc"
    assert captured["budget"] == 32000
    assert captured["total_tokens"] == 2
