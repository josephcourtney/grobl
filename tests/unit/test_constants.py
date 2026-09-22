from __future__ import annotations

import pytest

import grobl.constants as const_mod
from grobl.constants import (
    CONFIG_EXCLUDE,
    CONFIG_EXCLUDE_PRINT,
    CONFIG_EXCLUDE_TREE,
    CONFIG_INCLUDE,
    CONFIG_INCLUDE_FILE_TAGS,
    CONFIG_INHERIT_DEFAULTS,
    CONFIG_INCLUDE_TREE_TAGS,
    CONFIG_TREE_ONLY,
    ContentScope,
    InclusionLevel,
    PayloadFormat,
    SummaryFormat,
    TableStyle,
)

pytestmark = pytest.mark.small


def test_enum_values_and_config_keys() -> None:
    assert {m.value for m in ContentScope} == {"all", "tree", "files"}
    assert {p.value for p in PayloadFormat} == {"llm", "markdown", "json", "ndjson", "none"}
    assert {t.value for t in TableStyle} == {"auto", "full", "compact"}
    assert {f.value for f in SummaryFormat} == {"auto", "table", "json", "none"}
    assert {level.value for level in InclusionLevel} == {"omit", "tree_only", "full"}
    # Canonical policy keys.
    assert CONFIG_EXCLUDE == "exclude"
    assert CONFIG_TREE_ONLY == "tree_only"
    assert CONFIG_INCLUDE == "include"
    # Legacy keys remain accepted as compatibility inputs.
    assert CONFIG_EXCLUDE_TREE == "exclude_tree"
    assert CONFIG_EXCLUDE_PRINT == "exclude_print"
    assert CONFIG_INCLUDE_TREE_TAGS == "include_tree_tags"
    assert CONFIG_INCLUDE_FILE_TAGS == "include_file_tags"
    assert CONFIG_INHERIT_DEFAULTS == "inherit_defaults"


def test_output_mode_not_exposed() -> None:
    assert not hasattr(const_mod, "OutputMode")
