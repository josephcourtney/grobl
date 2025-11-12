from __future__ import annotations

from typing import TYPE_CHECKING

from grobl.constants import OutputMode, TableStyle
from grobl.directory import DirectoryTreeBuilder
from grobl.summary import SummaryContext, build_summary

if TYPE_CHECKING:
    from pathlib import Path


def test_build_summary_includes_binary_details_and_totals(tmp_path: Path) -> None:
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
    b.record_binary_details(relb, {"size_bytes": 3, "format": "dat"})

    ctx = SummaryContext(builder=b, common=tmp_path, mode=OutputMode.SUMMARY, table=TableStyle.COMPACT)
    js = build_summary(ctx)

    assert js["root"] == str(tmp_path)
    assert js["mode"] == "summary"
    assert js["table"] == "compact"
    totals = js["totals"]
    assert totals["total_lines"] == 2
    assert totals["total_characters"] == 3
    files = {f["path"]: f for f in js["files"]}
    assert files["t.txt"]["included"] is True
    assert files["bin.dat"]["binary"] is True
    assert files["bin.dat"]["binary_details"]["size_bytes"] == 3
