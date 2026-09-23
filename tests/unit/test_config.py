from __future__ import annotations

from pathlib import Path

import pytest

from grobl.config_loading import (
    discover_grobl_toml_files,
    load_config,
    load_toml_config,
    resolve_config_base,
)
from grobl.errors import ConfigLoadError
from grobl.utils import find_common_ancestor

pytestmark = pytest.mark.medium


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

    cfg = load_config(
        base_path=base,
        explicit_config=explicit_cfg,
        ignore_defaults=True,
    )
    assert cfg.get("exclude_tree") == ["from-explicit"]


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
    cfg = load_config(
        base_path=common,
        explicit_config=None,
        ignore_defaults=True,
    )
    assert cfg.get("exclude_tree") == ["from-base"]


def test_discovered_config_uses_logical_symlink_ancestors(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    links = repo / "links"
    target_dir = repo / "physical" / "nested"
    links.mkdir(parents=True)
    target_dir.mkdir(parents=True)

    root_config = repo / ".grobl.toml"
    logical_config = links / ".grobl.toml"
    physical_config = target_dir / ".grobl.toml"
    root_config.write_text("exclude = ['root']\n", encoding="utf-8")
    logical_config.write_text("exclude = ['logical']\n", encoding="utf-8")
    physical_config.write_text("exclude = ['physical']\n", encoding="utf-8")

    target = target_dir / "target.txt"
    target.write_text("contents\n", encoding="utf-8")
    link = links / "alias.txt"
    link.symlink_to(target)

    discovered = discover_grobl_toml_files(repo_root=repo, scan_paths=[link])

    assert discovered == [root_config.resolve(), logical_config.resolve()]
    assert physical_config.resolve() not in discovered


def test_legacy_config_file_is_loaded(tmp_path: Path) -> None:
    base = tmp_path / "proj"
    base.mkdir()
    legacy = base / ".grobl.config.toml"
    legacy.write_text("exclude_tree=['from-legacy']\n", encoding="utf-8")

    cfg = load_config(
        base_path=base,
        explicit_config=None,
        ignore_defaults=True,
    )

    assert cfg.get("exclude_tree") == ["from-legacy"]


def test_missing_explicit_config_raises(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.toml"

    with pytest.raises(ConfigLoadError):
        load_config(
            base_path=tmp_path,
            explicit_config=missing,
            ignore_defaults=True,
        )


def test_missing_env_config_is_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "env-missing.toml"
    monkeypatch.setenv("GROBL_CONFIG_PATH", str(missing))

    cfg = load_config(
        base_path=tmp_path,
        explicit_config=None,
        ignore_defaults=True,
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


def test_unreadable_config_is_normalized_as_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config.toml"
    config.write_text("scope = 'all'\n", encoding="utf-8")
    original_read_text = Path.read_text

    def read_text(
        path: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        if path == config:
            msg = "permission denied"
            raise OSError(msg)
        return original_read_text(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", read_text)

    with pytest.raises(ConfigLoadError, match="cannot read config"):
        load_toml_config(config)
