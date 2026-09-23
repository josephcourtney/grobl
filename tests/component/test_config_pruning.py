from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import tomlkit

from grobl.config_pruning import inspect_config_pruning

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.medium


def test_current_tree_prunes_exact_inherited_duplicate(tmp_path: Path) -> None:
    config = tmp_path / ".grobl.toml"
    config.write_text('tree_only = ["*.png"]\n', encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"png")

    result = inspect_config_pruning(
        config,
        current_tree=True,
        repo_root=tmp_path,
        default_cfg={"tree_only": ["*.png"]},
    )
    parsed = tomlkit.parse(result.text)

    assert result.changed is True
    assert "tree_only" not in parsed
    assert result.warnings


def test_current_tree_keeps_duplicate_that_reasserts_state(tmp_path: Path) -> None:
    config = tmp_path / ".grobl.toml"
    config.write_text('exclude = ["docs/"]\n', encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("guide", encoding="utf-8")

    result = inspect_config_pruning(
        config,
        current_tree=True,
        repo_root=tmp_path,
        default_cfg={
            "exclude": ["docs/"],
            "tree_only": ["docs/"],
        },
    )

    assert result.changed is False
    assert result.text == 'exclude = ["docs/"]\n'


def test_current_tree_does_not_remove_unique_dormant_rule(tmp_path: Path) -> None:
    config = tmp_path / ".grobl.toml"
    source = 'exclude = ["future/**"]\n'
    config.write_text(source, encoding="utf-8")

    result = inspect_config_pruning(
        config,
        current_tree=True,
        repo_root=tmp_path,
        default_cfg={},
    )

    assert result.changed is False
    assert result.text == source


def test_current_tree_walks_filesystem_once_for_multiple_duplicates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / ".grobl.toml"
    config.write_text('exclude = ["build", "dist"]\n', encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "dist").mkdir()

    path_type = type(tmp_path)
    original_iterdir = path_type.iterdir
    root_reads = 0

    def counted_iterdir(path: Path) -> Iterator[Path]:
        nonlocal root_reads
        if path == tmp_path:
            root_reads += 1
        return original_iterdir(path)

    monkeypatch.setattr(path_type, "iterdir", counted_iterdir)

    result = inspect_config_pruning(
        config,
        current_tree=True,
        repo_root=tmp_path,
        default_cfg={"exclude": ["build", "dist"]},
    )

    assert {rule.pattern for rule in result.removed} == {"build", "dist"}
    assert root_reads == 1


def test_current_tree_bisects_bulk_candidates_when_one_reassertion_is_required(tmp_path: Path) -> None:
    config = tmp_path / ".grobl.toml"
    config.write_text('exclude = ["docs/", "build"]\n', encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "build").mkdir()

    result = inspect_config_pruning(
        config,
        current_tree=True,
        repo_root=tmp_path,
        default_cfg={
            "exclude": ["docs/", "build"],
            "tree_only": ["docs/"],
        },
    )
    parsed = tomlkit.parse(result.text)

    assert list(parsed["exclude"]) == ["docs/"]
    assert {rule.pattern for rule in result.removed} == {"build"}


def test_current_tree_skips_omitted_subtree_with_unrelated_reinclusion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / ".grobl.toml"
    config.write_text('exclude = ["vendor"]\n', encoding="utf-8")
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "large").mkdir()
    source = tmp_path / "src"
    source.mkdir()
    (source / "keep.py").write_text("keep", encoding="utf-8")

    path_type = type(tmp_path)
    original_iterdir = path_type.iterdir

    def guarded_iterdir(path: Path) -> Iterator[Path]:
        if path == vendor:
            msg = "current-tree pruning descended into unrelated omitted subtree"
            raise AssertionError(msg)
        return original_iterdir(path)

    monkeypatch.setattr(path_type, "iterdir", guarded_iterdir)

    result = inspect_config_pruning(
        config,
        current_tree=True,
        repo_root=tmp_path,
        default_cfg={
            "exclude": ["vendor"],
            "include": ["src/keep.py"],
        },
    )

    assert {rule.pattern for rule in result.removed} == {"vendor"}


def test_prune_removes_empty_policy_key_and_inherited_setting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config = tmp_path / ".grobl.toml"
    config.write_text(
        """\
exclude = ["custom"]
include = []
include_tree_tags = "directory"
include_file_tags = "file"
""",
        encoding="utf-8",
    )

    result = inspect_config_pruning(
        config,
        repo_root=tmp_path,
        default_cfg={
            "include": [],
            "include_tree_tags": "directory",
            "include_file_tags": "files",
        },
    )
    parsed = tomlkit.parse(result.text)

    assert result.changed is True
    assert list(parsed["exclude"]) == ["custom"]
    assert "include" not in parsed
    assert "include_tree_tags" not in parsed
    assert parsed["include_file_tags"] == "file"
    assert result.removed_settings == ("include_tree_tags",)
    assert result.removed_empty_keys == ("include",)


def test_prune_keeps_setting_that_resets_xdg_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    xdg_home = tmp_path / "xdg"
    xdg_config = xdg_home / "grobl" / "config.toml"
    xdg_config.parent.mkdir(parents=True)
    xdg_config.write_text('include_tree_tags = "custom"\n', encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))

    project = tmp_path / "project"
    project.mkdir()
    config = project / ".grobl.toml"
    source = 'include_tree_tags = "directory"\n'
    config.write_text(source, encoding="utf-8")

    result = inspect_config_pruning(
        config,
        repo_root=project,
        default_cfg={"include_tree_tags": "directory"},
    )

    assert result.changed is False
    assert result.text == source


def test_prune_keeps_empty_policy_key_that_suppresses_extends(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    base = tmp_path / "base.toml"
    base.write_text('include = ["keep/**"]\n', encoding="utf-8")
    config = tmp_path / ".grobl.toml"
    source = 'extends = ["base.toml"]\ninclude = []\n'
    config.write_text(source, encoding="utf-8")

    result = inspect_config_pruning(
        config,
        repo_root=tmp_path,
        default_cfg={},
    )

    assert result.changed is False
    assert result.text == source


def test_current_tree_removes_orphaned_policy_sections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config = tmp_path / ".grobl.toml"
    config.write_text(
        """\
exclude = [
  "custom",

  # secrets
  ".env",

  # version control
  ".git",

  # project-specific
  "keep",
]
""",
        encoding="utf-8",
    )

    result = inspect_config_pruning(
        config,
        current_tree=True,
        repo_root=tmp_path,
        default_cfg={"exclude": [".env", ".git"]},
    )

    assert "# secrets" not in result.text
    assert "# version control" not in result.text
    assert "# project-specific" in result.text
    assert list(tomlkit.parse(result.text)["exclude"]) == ["custom", "keep"]


def test_current_tree_respects_disabled_default_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROBL_CONFIG_PATH", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-empty"))

    root = tmp_path / "repo"
    root.mkdir()
    (root / "dist").mkdir()
    path = root / ".grobl.toml"
    source = 'inherit_defaults = false\nexclude = ["dist"]\n'
    path.write_text(source, encoding="utf-8")

    result = inspect_config_pruning(
        path,
        current_tree=True,
        repo_root=root,
        default_cfg={"inherit_defaults": True, "exclude": ["dist"]},
    )

    assert not result.changed
    assert result.text == source
