from __future__ import annotations

import sys

import tomllib

from grobl.cli import main
from grobl.editor import interactive_edit_config


def test_interactive_edit_config_saves(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    inputs = iter(["1", "2"])
    monkeypatch.setattr("builtins.input", lambda _=None: next(inputs))
    cfg: dict = {}
    interactive_edit_config([tmp_path], cfg, save=True)
    data = tomllib.loads((tmp_path / ".grobl.config.toml").read_text(encoding="utf-8"))
    assert "a.txt" in data["exclude_tree"]
    assert "b.txt" in data["exclude_print"]


def test_cli_interactive_run_excludes(tmp_path, monkeypatch, capsys):
    (tmp_path / "keep.txt").write_text("k", encoding="utf-8")
    (tmp_path / "skip.txt").write_text("s", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    inputs = iter(["2", ""])
    monkeypatch.setattr("builtins.input", lambda _=None: next(inputs))
    monkeypatch.setattr("grobl.cli.human_summary", lambda *_a, **_k: None)
    monkeypatch.setattr(sys, "argv", ["grobl", "--no-clipboard", "--interactive"])
    main()
    out = capsys.readouterr().out
    tree_section = out.split("<tree root=")[-1]
    assert "keep.txt" in tree_section
    assert "skip.txt" not in tree_section
    assert not (tmp_path / ".grobl.config.toml").exists()
