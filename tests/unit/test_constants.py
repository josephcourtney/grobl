from __future__ import annotations

from grobl.constants import (
    CONFIG_EXCLUDE_PRINT,
    CONFIG_EXCLUDE_TREE,
    CONFIG_INCLUDE_FILE_TAGS,
    CONFIG_INCLUDE_TREE_TAGS,
    OutputMode,
    SummaryFormat,
    TableStyle,
)


def test_enum_values_and_config_keys() -> None:
    assert {m.value for m in OutputMode} == {"all", "tree", "files", "summary"}
    assert {t.value for t in TableStyle} == {"auto", "full", "compact", "none"}
    assert {f.value for f in SummaryFormat} == {"human", "json"}
    # config keys are the canonical strings used throughout the codebase
    assert CONFIG_EXCLUDE_TREE == "exclude_tree"
    assert CONFIG_EXCLUDE_PRINT == "exclude_print"
    assert CONFIG_INCLUDE_TREE_TAGS == "include_tree_tags"
    assert CONFIG_INCLUDE_FILE_TAGS == "include_file_tags"
