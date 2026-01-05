from __future__ import annotations

import pytest

from grobl.formatter import human_summary

pytestmark = pytest.mark.small


def test_human_summary_table_none_returns_empty() -> None:
    out = human_summary(["a"], 3, 5, table="none")
    assert not out


def test_human_summary_compact_contains_totals() -> None:
    out = human_summary(["a"], 10, 20, table="compact")
    assert "Total lines: 10" in out
    assert "Total characters: 20" in out


def test_human_summary_full_includes_title_and_tree() -> None:
    lines = ["file.txt", "subdir/"]
    out = human_summary(lines, 2, 10, table="full")
    assert " Project Summary " in out
    for ln in lines:
        assert ln in out
    # Ends with a newline when output is non-empty
    assert out.endswith("\n")


def test_human_summary_full_empty_tree_uses_title_width() -> None:
    # Ensure function behaves when tree_lines is empty
    out = human_summary([], 0, 0, table="full")
    assert " Project Summary " in out
    assert "Total lines: 0" in out
    assert "Total characters: 0" in out
