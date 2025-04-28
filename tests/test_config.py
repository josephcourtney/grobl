import importlib.resources
import json
import sys

import pytest

from grobl import main
from grobl.config import (
    DOTIGNORE_CONFIG,
    JSON_CONFIG,
    TOML_CONFIG,
    build_merged_config,
    collect_old_configs,
    load_default_config,
    load_json_config,
    load_toml_config,
    merge_gitignore,
    migrate_config,
    prompt_delete,
    read_config,
    read_groblignore,
)
from grobl.errors import ConfigLoadError


def test_load_default_config_oserror(monkeypatch):
    class FakePath:
        def joinpath(self, filename):  # noqa: ARG002
            return self

        def open(self, *args, **kwargs):  # noqa: ARG002, PLR6301
            msg = "boom"
            raise OSError(msg)

    # 🛠 Correct: patch the *object*, not a string
    monkeypatch.setattr(importlib.resources, "files", lambda *_: FakePath())

    with pytest.raises(ConfigLoadError, match="Error loading default configuration"):
        load_default_config()


def test_migrate_config_toml_already_exists(tmp_path, capsys):
    (tmp_path / TOML_CONFIG).write_text("content")
    migrate_config(tmp_path)
    out = capsys.readouterr().out
    assert f"{TOML_CONFIG} already exists." in out


def test_migrate_config_no_old_files(tmp_path, capsys):
    migrate_config(tmp_path)
    out = capsys.readouterr().out
    assert f"No {JSON_CONFIG} or {DOTIGNORE_CONFIG} to migrate." in out


def test_main_migrate_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["grobl", "migrate-config"])

    with pytest.raises(SystemExit) as e:
        main.main()
    assert e.value.code == 0


def test_load_json_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    cfg = load_json_config(path)
    assert cfg["foo"] == "bar"


def test_load_toml_config(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('foo = "bar"\n', encoding="utf-8")
    cfg = load_toml_config(path)
    assert cfg["foo"] == "bar"


def test_read_groblignore_lines(tmp_path):
    file = tmp_path / ".groblignore"
    file.write_text("# comment\n\n*.pyc\n__pycache__/\n", encoding="utf-8")
    patterns = read_groblignore(tmp_path)
    assert patterns == ["*.pyc", "__pycache__/"]


def test_merge_gitignore_adds_patterns(tmp_path):
    base_cfg = {}
    (tmp_path / ".groblignore").write_text("*.tmp\n", encoding="utf-8")
    merge_gitignore(base_cfg, tmp_path)
    assert "*.tmp" in base_cfg["exclude_tree"]


def test_load_toml_config_error(tmp_path):
    bad_toml = tmp_path / "bad.toml"
    bad_toml.write_text("not: toml:", encoding="utf-8")
    with pytest.raises(ConfigLoadError):
        load_toml_config(bad_toml)


def test_load_json_config_error(tmp_path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{ bad json }", encoding="utf-8")
    with pytest.raises(ConfigLoadError):
        load_json_config(bad_json)


def test_read_config_toml_error(monkeypatch, tmp_path):
    toml = tmp_path / ".grobl.config.toml"
    toml.write_text("invalid = ", encoding="utf-8")

    # Patch sys.exit to catch it instead of exiting
    monkeypatch.setattr(sys, "exit", lambda code=0: (_ for _ in ()).throw(SystemExit(code)))

    with pytest.raises(ConfigLoadError):
        read_config(tmp_path)


def test_collect_old_configs(tmp_path):
    (tmp_path / ".grobl.config.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".groblignore").write_text("", encoding="utf-8")
    old_files = collect_old_configs(tmp_path)
    names = [f.name for f in old_files]
    assert ".grobl.config.json" in names
    assert ".groblignore" in names


def test_build_merged_config(tmp_path):
    (tmp_path / ".grobl.config.json").write_text('{"exclude_tree": ["*.bak"]}', encoding="utf-8")
    (tmp_path / ".groblignore").write_text("*.tmp\n", encoding="utf-8")
    cfg = build_merged_config(tmp_path)
    assert "*.bak" in cfg["exclude_tree"]
    assert "*.tmp" in cfg["exclude_tree"]


def test_prompt_delete_yes_no(tmp_path, monkeypatch, capsys):
    file = tmp_path / "old.json"
    file.write_text("data", encoding="utf-8")

    monkeypatch.setattr("builtins.input", lambda _: "y")
    prompt_delete([file])
    out = capsys.readouterr().out
    assert "Deleted old.json" in out
    assert not file.exists()

    file = tmp_path / "old2.json"
    file.write_text("data", encoding="utf-8")

    monkeypatch.setattr("builtins.input", lambda _: "n")
    prompt_delete([file])
    out = capsys.readouterr().out
    assert "Kept old2.json" in out
    assert file.exists()


def test_migrate_config_success(monkeypatch, tmp_path):
    (tmp_path / ".grobl.config.json").write_text('{"exclude_tree": ["*.bak"]}', encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _: "n")  # Always say "keep"
    migrate_config(tmp_path)
    assert (tmp_path / ".grobl.config.toml").exists()


def test_read_config_json_fallback(tmp_path):
    (tmp_path / ".grobl.config.json").write_text('{"exclude_tree": ["*.tmp"]}', encoding="utf-8")
    cfg = read_config(tmp_path)
    assert "*.tmp" in cfg["exclude_tree"]


def test_main_configloaderror(monkeypatch):
    # Patch inside grobl.main
    monkeypatch.setattr("grobl.main.sys.argv", ["grobl"])
    monkeypatch.setattr("grobl.main.sys.exit", lambda code=0: (_ for _ in ()).throw(SystemExit(code)))

    # Patch main's internal dependencies
    monkeypatch.setattr(
        "grobl.main.read_config", lambda *_args, **_kwargs: (_ for _ in ()).throw(ConfigLoadError("fail"))
    )
    monkeypatch.setattr(
        "grobl.main.PyperclipClipboard", type("MockClipboard", (), {"copy": lambda _self, _content: None})
    )
    monkeypatch.setattr("grobl.main.human_summary", lambda *_a, **_k: None)

    # Now run it, expecting SystemExit
    with pytest.raises(SystemExit) as e:
        main.main()
    assert e.value.code == 1


def test_read_config_handles_invalid_toml(monkeypatch, tmp_path):
    (tmp_path / ".grobl.config.toml").write_text("invalid = ", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("grobl.main.PyperclipClipboard", lambda: None)
    monkeypatch.setattr("grobl.main.human_summary", lambda *_: None)

    monkeypatch.setattr(sys, "argv", ["grobl"])
    with pytest.raises(SystemExit) as exc_info:
        main.main()

    assert exc_info.value.code == 1
