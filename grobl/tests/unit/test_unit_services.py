"""Tests for grobl.services application orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grobl.constants import OutputMode, TableStyle
from grobl.services import ScanExecutor, ScanOptions

if TYPE_CHECKING:
    from pathlib import Path


def test_executor_produces_summary_and_payload(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    payloads: list[str] = []

    def collect(text: str) -> None:
        payloads.append(text)

    executor = ScanExecutor(sink=collect)
    human, summary = executor.execute(
        paths=[tmp_path],
        cfg={},
        options=ScanOptions(mode=OutputMode.ALL, table=TableStyle.FULL),
    )

    assert human
    assert summary["totals"]["total_lines"] >= 1
    assert payloads, "expected payload sink to receive data for non-summary mode"


def test_executor_skips_payload_for_summary_mode(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("world", encoding="utf-8")
    payloads: list[str] = []

    executor = ScanExecutor(sink=payloads.append)
    human, summary = executor.execute(
        paths=[tmp_path],
        cfg={},
        options=ScanOptions(mode=OutputMode.SUMMARY, table=TableStyle.COMPACT),
    )

    assert human  # summary mode still returns human-readable output
    assert summary["mode"] == OutputMode.SUMMARY.value
    assert payloads == []
