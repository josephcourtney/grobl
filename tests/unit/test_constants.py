from __future__ import annotations

from grobl.constants import (
    CONFIG_EXCLUDE_PRINT,
    CONFIG_EXCLUDE_TREE,
    CONFIG_INCLUDE_FILE_TAGS,
    CONFIG_INCLUDE_TREE_TAGS,
    ContentScope,
    PayloadFormat,
    PayloadSink,
    SummaryFormat,
    TableStyle,
)


def test_enum_values_and_config_keys() -> None:
    assert {m.value for m in ContentScope} == {"all", "tree", "files"}
    assert {p.value for p in PayloadFormat} == {"llm", "json", "none"}
    assert {s.value for s in PayloadSink} == {"auto", "clipboard", "stdout", "file"}
    assert {t.value for t in TableStyle} == {"auto", "full", "compact", "none"}
    assert {f.value for f in SummaryFormat} == {"human", "json", "none"}
    # config keys are the canonical strings used throughout the codebase
    assert CONFIG_EXCLUDE_TREE == "exclude_tree"
    assert CONFIG_EXCLUDE_PRINT == "exclude_print"
    assert CONFIG_INCLUDE_TREE_TAGS == "include_tree_tags"
    assert CONFIG_INCLUDE_FILE_TAGS == "include_file_tags"
