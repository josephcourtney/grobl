from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hypothesis import given
from hypothesis import strategies as st

import grobl_config
from grobl_config import apply_runtime_ignores, load_and_adjust_config

SEGMENT = st.text(
    min_size=1,
    max_size=5,
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_import():
    assert grobl_config


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

    cfg = load_and_adjust_config(
        base_path=base,
        explicit_config=None,
        ignore_defaults=True,
        add_ignore=(),
        remove_ignore=(),
    )
    assert cfg.get("exclude_tree") == ["from-base"]


@given(
    base=st.lists(SEGMENT, max_size=5),
    add=st.lists(SEGMENT, max_size=3),
    remove=st.lists(SEGMENT, max_size=3),
    no_ignore=st.booleans(),
)
def test_apply_runtime_ignores_matches_manual_logic(
    base: list[str], add: list[str], remove: list[str], *, no_ignore: bool
) -> None:
    cfg = {"exclude_tree": base.copy()}
    result = apply_runtime_ignores(
        cfg,
        add_ignore=tuple(add),
        remove_ignore=tuple(remove),
        add_ignore_files=(),
        no_ignore=no_ignore,
    )
    if no_ignore:
        assert result["exclude_tree"] == []
        return

    expected = base.copy()
    for pattern in add:
        if pattern not in expected:
            expected.append(pattern)
    for pattern in remove:
        if pattern in expected:
            expected.remove(pattern)
    assert result["exclude_tree"] == expected
