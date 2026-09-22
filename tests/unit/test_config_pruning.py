from __future__ import annotations

import pytest
import tomlkit

from grobl.config_pruning import ConfigPruneError, prune_config_text

pytestmark = pytest.mark.small


def test_prune_text_removes_rule_shadowed_by_later_identical_matcher() -> None:
    source = """\
exclude = ["foo", "bar"]
tree_only = ["foo"]
include = []
"""

    result = prune_config_text(source)
    parsed = tomlkit.parse(result.text)

    assert result.changed is True
    assert list(parsed["exclude"]) == ["bar"]
    assert list(parsed["tree_only"]) == ["foo"]
    assert result.removed[0].pattern == "foo"


def test_prune_text_preserves_comments_around_removed_array_item() -> None:
    source = """\
exclude = [
  # generated
  "build",
  "build",
]
"""

    result = prune_config_text(source)

    assert "# generated" in result.text
    assert list(tomlkit.parse(result.text)["exclude"]) == ["build"]


def test_prune_text_leaves_irredundant_config_unchanged() -> None:
    source = 'exclude = ["build"]\ntree_only = ["*.png"]\n'

    result = prune_config_text(source)

    assert result.changed is False
    assert result.text == source
    assert result.removed == ()


def test_prune_text_requires_canonical_policy() -> None:
    with pytest.raises(ConfigPruneError, match="config migrate"):
        prune_config_text('exclude_tree = ["build"]\n')
