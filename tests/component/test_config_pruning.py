from __future__ import annotations

from pathlib import Path

import pytest
import tomlkit

from grobl.config_pruning import inspect_config_pruning

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

    assert result.changed is True
    assert list(tomlkit.parse(result.text)["tree_only"]) == []
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
