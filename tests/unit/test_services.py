from __future__ import annotations

import json

from grobl.constants import (
    ContentScope,
    PayloadFormat,
    SummaryFormat,
    TableStyle,
)
from grobl.services import ScanExecutor, ScanOptions


def _write_noop(_: str) -> None:  # pragma: no cover - trivial
    pass


def test_execute_emits_json_payload_and_summary(tmp_path):
    sample = tmp_path / "example.txt"
    sample.write_text("hello\n", encoding="utf-8")

    writes: list[str] = []

    def _sink(content: str) -> None:
        writes.append(content)

    executor = ScanExecutor(sink=_sink)
    cfg = {"exclude_tree": [], "exclude_print": []}

    human, summary = executor.execute(
        paths=[tmp_path],
        cfg=cfg,
        options=ScanOptions(
            scope=ContentScope.ALL,
            payload_format=PayloadFormat.JSON,
            summary_format=SummaryFormat.JSON,
            summary_style=TableStyle.NONE,
        ),
    )

    assert not human
    assert summary["scope"] == ContentScope.ALL.value
    assert summary["style"] == TableStyle.NONE.value
    assert writes, "expected JSON payload to be written"

    payload = json.loads(writes[0])
    assert payload["scope"] == ContentScope.ALL.value
    assert payload["summary"]["totals"] == summary["totals"]
    assert payload["summary"]["style"] == summary["style"]
    files = payload["summary"]["files"]
    assert any(entry["path"].endswith("example.txt") for entry in files)


def test_execute_skips_payload_when_disabled(tmp_path):
    sample = tmp_path / "solo.txt"
    sample.write_text("hello\n", encoding="utf-8")

    writes: list[str] = []

    executor = ScanExecutor(sink=writes.append)
    cfg = {"exclude_tree": [], "exclude_print": []}

    human, summary = executor.execute(
        paths=[tmp_path],
        cfg=cfg,
        options=ScanOptions(
            scope=ContentScope.ALL,
            payload_format=PayloadFormat.NONE,
            summary_format=SummaryFormat.HUMAN,
            summary_style=TableStyle.COMPACT,
        ),
    )

    assert writes == []
    assert human
    assert summary["scope"] == ContentScope.ALL.value
    assert summary["style"] == TableStyle.COMPACT.value


def test_execute_summary_none_returns_minimal_structure(tmp_path):
    sample = tmp_path / "none.txt"
    sample.write_text("hello\n", encoding="utf-8")

    writes: list[str] = []

    executor = ScanExecutor(sink=writes.append)
    cfg = {"exclude_tree": [], "exclude_print": []}

    human, summary = executor.execute(
        paths=[tmp_path],
        cfg=cfg,
        options=ScanOptions(
            scope=ContentScope.ALL,
            payload_format=PayloadFormat.NONE,
            summary_format=SummaryFormat.NONE,
            summary_style=TableStyle.AUTO,
        ),
    )

    assert writes == []
    assert not human
    assert summary["root"] == str(tmp_path)
    assert summary["scope"] == ContentScope.ALL.value
    assert summary["style"] == TableStyle.AUTO.value
    assert summary["files"] == []
    totals = summary["totals"]
    assert totals["total_lines"] == 1
    assert totals["total_characters"] == len("hello\n")
