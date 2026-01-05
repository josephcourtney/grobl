from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grobl.config import apply_runtime_ignores, read_config, resolve_config_base
from grobl.errors import ConfigLoadError
from grobl.utils import find_common_ancestor

pytestmark = pytest.mark.small

if TYPE_CHECKING:
    from pathlib import Path


def write_toml(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_config_precedence_explicit_overrides_env_and_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    cfg = read_config(
        base_path=base,
        explicit_config=explicit_cfg,
        ignore_defaults=True,
        add_ignore=(),
        remove_ignore=(),
        unignore=(),
    )
    assert cfg.get("exclude_tree") == ["from-explicit"]


def test_runtime_ignore_files_and_no_ignore(tmp_path: Path) -> None:
    base = tmp_path
    ignore_file = tmp_path / "ignore.txt"
    ignore_file.write_text("# comment\nfoo\nbar\n\n", encoding="utf-8")

    cfg = read_config(
        base_path=base,
        explicit_config=None,
        ignore_defaults=True,
        add_ignore=("baz",),
        remove_ignore=(),
        add_ignore_files=(ignore_file,),
        unignore=(),
        no_ignore=False,
    )
    assert set(cfg.get("exclude_tree", [])) == {"foo", "bar", "baz"}

    # Now disable all ignores
    cfg2 = read_config(
        base_path=base,
        explicit_config=None,
        ignore_defaults=True,
        add_ignore=(),
        remove_ignore=(),
        add_ignore_files=(ignore_file,),
        unignore=(),
        no_ignore=True,
    )
    assert cfg2.get("exclude_tree") == []


def test_runtime_remove_ignore_warns_when_missing(capsys: pytest.CaptureFixture[str]) -> None:
    cfg = {"exclude_tree": ["a"]}
    apply_runtime_ignores(
        cfg,
        add_ignore=(),
        remove_ignore=("missing",),
        add_ignore_files=(),
        unignore=(),
        no_ignore=False,
    )
    captured = capsys.readouterr()
    assert "warning: ignore pattern not found: missing" in captured.err


def test_config_is_read_from_common_ancestor(tmp_path: Path) -> None:
    # project layout: base/.grobl.toml and two subpaths are scanned
    base = tmp_path / "proj"
    (base / "a").mkdir(parents=True)
    (base / "b").mkdir(parents=True)
    (base / ".grobl.toml").write_text("exclude_tree=['from-base']\n", encoding="utf-8")

    p1 = base / "a" / "one.txt"
    p2 = base / "b" / "two.txt"
    p1.write_text("1", encoding="utf-8")
    p2.write_text("2", encoding="utf-8")

    common = find_common_ancestor([p1, p2])
    cfg = read_config(
        base_path=common,
        explicit_config=None,
        ignore_defaults=True,
        add_ignore=(),
        remove_ignore=(),
        unignore=(),
    )
    assert cfg.get("exclude_tree") == ["from-base"]


def test_legacy_config_file_is_loaded(tmp_path: Path) -> None:
    base = tmp_path / "proj"
    base.mkdir()
    legacy = base / ".grobl.config.toml"
    legacy.write_text("exclude_tree=['from-legacy']\n", encoding="utf-8")

    cfg = read_config(
        base_path=base,
        explicit_config=None,
        ignore_defaults=True,
        add_ignore=(),
        remove_ignore=(),
        unignore=(),
    )

    assert cfg.get("exclude_tree") == ["from-legacy"]


def test_missing_explicit_config_raises(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.toml"

    with pytest.raises(ConfigLoadError):
        read_config(
            base_path=tmp_path,
            explicit_config=missing,
            ignore_defaults=True,
            add_ignore=(),
            remove_ignore=(),
            unignore=(),
        )


def test_missing_env_config_is_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "env-missing.toml"
    monkeypatch.setenv("GROBL_CONFIG_PATH", str(missing))

    cfg = read_config(
        base_path=tmp_path,
        explicit_config=None,
        ignore_defaults=True,
        add_ignore=(),
        remove_ignore=(),
        unignore=(),
    )

    assert isinstance(cfg, dict)


def test_resolve_config_base_prefers_explicit_path(tmp_path: Path) -> None:
    base = tmp_path / "proj"
    base.mkdir()
    explicit = tmp_path / "cfg" / "grobl.toml"
    explicit.parent.mkdir()
    explicit.write_text("exclude_tree=['x']\n", encoding="utf-8")

    resolved = resolve_config_base(base_path=base, explicit_config=explicit)
    assert resolved == explicit.parent.resolve()


def test_resolve_config_base_walks_up_to_config_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    nested = root / "a" / "b"
    nested.mkdir(parents=True)
    (root / ".grobl.toml").write_text("exclude_tree=['x']\n", encoding="utf-8")

    resolved = resolve_config_base(base_path=nested, explicit_config=None)
    assert resolved == root.resolve()
