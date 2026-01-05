from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grobl.constants import ContentScope, TableStyle
from grobl.directory import DirectoryTreeBuilder
from grobl.summary import SummaryContext, build_sink_payload_json, build_summary

pytestmark = pytest.mark.small

if TYPE_CHECKING:
    from pathlib import Path


def test_build_summary_includes_binary_files_and_totals(tmp_path: Path) -> None:
    b = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    # Text file (included)
    tf = tmp_path / "t.txt"
    tf.write_text("a\nb\n", encoding="utf-8")
    b.add_file(tf, tf.relative_to(tmp_path), lines=2, chars=3, content="a\nb\n")
    # Binary file (excluded content)
    bf = tmp_path / "bin.dat"
    bf.write_bytes(b"\x00\x01\x02")
    relb = bf.relative_to(tmp_path)
    b.record_metadata(relb, lines=0, chars=3)

    ctx = SummaryContext(builder=b, common=tmp_path, scope=ContentScope.ALL, style=TableStyle.COMPACT)
    js = build_summary(ctx)

    assert js["root"] == str(tmp_path)
    assert js["scope"] == "all"
    assert js["style"] == "compact"
    totals = js["totals"]
    snapshot = b.summary_totals()
    assert totals["total_lines"] == snapshot.total_lines
    assert totals["total_characters"] == snapshot.total_characters
    assert totals["all_total_lines"] == snapshot.all_total_lines
    assert totals["all_total_characters"] == snapshot.all_total_characters
    files = {entry["path"]: entry for entry in js["files"]}
    assert files["t.txt"]["included"] is True
    assert files["t.txt"]["lines"] == 2
    assert files["t.txt"]["chars"] == 3
    assert files["bin.dat"]["included"] is False
    assert files["bin.dat"]["binary"] is True


def test_build_sink_payload_json_respects_scope(tmp_path: Path) -> None:
    b = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    file_a = tmp_path / "a.txt"
    file_a.write_text("hello\n", encoding="utf-8")
    b.add_file(file_a, file_a.relative_to(tmp_path), lines=1, chars=6, content="hello\n")
    file_b = tmp_path / "b.bin"
    file_b.write_bytes(b"\x00")
    b.record_metadata(file_b.relative_to(tmp_path), lines=0, chars=1)

    ctx_all = SummaryContext(builder=b, common=tmp_path, scope=ContentScope.ALL, style=TableStyle.AUTO)
    payload_all = build_sink_payload_json(ctx_all)
    assert payload_all["scope"] == "all"
    assert "tree" in payload_all
    assert "files" in payload_all
    assert payload_all["summary"] == build_summary(ctx_all)

    ctx_tree = SummaryContext(builder=b, common=tmp_path, scope=ContentScope.TREE, style=TableStyle.AUTO)
    payload_tree = build_sink_payload_json(ctx_tree)
    assert payload_tree["scope"] == "tree"
    assert "tree" in payload_tree
    assert "files" not in payload_tree

    ctx_files = SummaryContext(builder=b, common=tmp_path, scope=ContentScope.FILES, style=TableStyle.FULL)
    payload_files = build_sink_payload_json(ctx_files)
    assert payload_files["scope"] == "files"
    assert "tree" not in payload_files
    assert "files" in payload_files
    assert payload_files["summary"] == build_summary(ctx_files)
