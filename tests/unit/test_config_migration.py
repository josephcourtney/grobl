from __future__ import annotations

import pytest
import tomlkit

from grobl.config_migration import ConfigMigrationError, migrate_config_text

pytestmark = pytest.mark.small


def test_migrate_legacy_policy_removes_redundant_content_patterns() -> None:
    source = """\
# keep this comment
exclude_tree = ["dist/", "build/"]
exclude_print = ["dist/", "build/", "LICENSE*"]
include_tree_tags = "directory"
"""

    result = migrate_config_text(source)
    parsed = tomlkit.parse(result.text)

    assert result.changed is True
    assert list(parsed["exclude"]) == ["dist/", "build/"]
    assert list(parsed["tree_only"]) == ["LICENSE*"]
    assert "exclude_tree" not in parsed
    assert "exclude_print" not in parsed
    assert parsed["include_tree_tags"] == "directory"
    assert "# keep this comment" in result.text
    assert result.warnings


def test_migrate_respects_last_exact_tree_negation() -> None:
    source = """\
exclude_tree = ["foo", "!foo"]
exclude_print = ["foo"]
"""
    result = migrate_config_text(source)
    parsed = tomlkit.parse(result.text)

    assert list(parsed["exclude"]) == ["foo", "!foo"]
    assert list(parsed["tree_only"]) == ["foo"]


def test_migrate_exclude_content_matches_legacy_alias_precedence() -> None:
    source = """\
exclude_print = ["old"]
exclude_content = ["new"]
"""
    result = migrate_config_text(source)
    parsed = tomlkit.parse(result.text)

    assert list(parsed["tree_only"]) == ["new"]
    assert any("takes precedence" in warning for warning in result.warnings)


def test_migrate_rejects_mixed_canonical_and_legacy_keys() -> None:
    source = """\
exclude = ["new"]
exclude_tree = ["old"]
"""
    with pytest.raises(ConfigMigrationError, match="mixes canonical and legacy"):
        migrate_config_text(source)


def test_migrate_leaves_canonical_config_unchanged() -> None:
    source = """\
exclude = ["dist/"]
tree_only = ["LICENSE*"]
include = []
"""
    result = migrate_config_text(source)

    assert result.changed is False
    assert result.text == source


def test_migrate_rejects_invalid_legacy_policy_value() -> None:
    with pytest.raises(ConfigMigrationError, match="exclude_tree"):
        migrate_config_text("exclude_tree = 42\n")
