from __future__ import annotations

from typing import TYPE_CHECKING

from grobl.config import load_and_adjust_config

if TYPE_CHECKING:
    from pathlib import Path


def write_toml(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_config_precedence_explicit_overrides_env_and_local(tmp_path: Path, monkeypatch: object) -> None:
    base = tmp_path / "proj"
    base.mkdir()

    # XDG config (lowest among custom sources here)
    xdg = tmp_path / "xdg" / "grobl" / "config.toml"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg.parent.parent))
    write_toml(xdg, "exclude_tree=['from-xdg']\n")

    # Local project config
    write_toml(base / ".grobl.toml", "exclude_tree=['from-local']\n")

    # pyproject tool table also present
    write_toml(base / "pyproject.toml", "[tool.grobl]\nexclude_tree=['from-pyproject']\n")

    # Env override
    env_cfg = tmp_path / "env.toml"
    write_toml(env_cfg, "exclude_tree=['from-env']\n")
    monkeypatch.setenv("GROBL_CONFIG_PATH", str(env_cfg))

    # Explicit override
    explicit_cfg = tmp_path / "explicit.toml"
    write_toml(explicit_cfg, "exclude_tree=['from-explicit']\n")

    cfg = load_and_adjust_config(
        base_path=base,
        explicit_config=explicit_cfg,
        ignore_defaults=True,
        add_ignore=(),
        remove_ignore=(),
    )
    assert cfg.get("exclude_tree") == ["from-explicit"]


def test_runtime_ignore_files_and_no_ignore(tmp_path: Path) -> None:
    base = tmp_path
    ignore_file = tmp_path / "ignore.txt"
    ignore_file.write_text("# comment\nfoo\nbar\n\n", encoding="utf-8")

    cfg = load_and_adjust_config(
        base_path=base,
        explicit_config=None,
        ignore_defaults=True,
        add_ignore=("baz",),
        remove_ignore=(),
        add_ignore_files=(ignore_file,),
        no_ignore=False,
    )
    assert set(cfg.get("exclude_tree", [])) == {"foo", "bar", "baz"}

    # Now disable all ignores
    cfg2 = load_and_adjust_config(
        base_path=base,
        explicit_config=None,
        ignore_defaults=True,
        add_ignore=(),
        remove_ignore=(),
        add_ignore_files=(ignore_file,),
        no_ignore=True,
    )
    assert cfg2.get("exclude_tree") == []
