from __future__ import annotations

import json

from grobl.constants import OutputMode, SummaryFormat, TableStyle
from grobl.services import ScanExecutor, ScanOptions


def _write_noop(_: str) -> None:  # pragma: no cover - trivial
    pass


def test_scan_executor_emits_json_payload_when_requested(tmp_path):
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
            mode=OutputMode.ALL,
            table=TableStyle.NONE,
            fmt=SummaryFormat.JSON,
        ),
    )

    assert not human
    assert summary["mode"] == OutputMode.ALL.value
    assert summary["table"] == TableStyle.NONE.value
    assert writes, "expected JSON payload to be written"

    payload = json.loads(writes[0])
    assert payload["mode"] == OutputMode.ALL.value
    assert payload["summary"]["totals"] == summary["totals"]
    files = payload["summary"]["files"]
    assert any(entry["path"].endswith("example.txt") for entry in files)
