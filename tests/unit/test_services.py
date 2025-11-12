from __future__ import annotations

import json
from typing import TYPE_CHECKING

from grobl.constants import OutputMode, SummaryFormat, TableStyle
from grobl.services import ScanExecutor, ScanOptions

if TYPE_CHECKING:
    from pathlib import Path


def _write_noop(_: str) -> None:  # pragma: no cover - trivial
    pass


def _fake_png_bytes(width: int, height: int) -> bytes:
    # Minimal PNG signature + IHDR prefix sufficient for our parser
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_len = (13).to_bytes(4, "big")
    ihdr = b"IHDR"
    w = width.to_bytes(4, "big")
    h = height.to_bytes(4, "big")
    bit_depth = (8).to_bytes(1, "big")
    color_type = (6).to_bytes(1, "big")  # RGBA
    rest = b"\x00\x00\x00"  # compression, filter, interlace
    # CRC placeholder (ignored by parser)
    crc = b"\x00\x00\x00\x00"
    return sig + ihdr_len + ihdr + w + h + bit_depth + color_type + rest + crc


def test_binary_summary_includes_image_details(tmp_path: Path) -> None:
    img = tmp_path / "tiny.png"
    img.write_bytes(_fake_png_bytes(2, 3))

    cfg = {"exclude_tree": [], "exclude_print": []}
    executor = ScanExecutor(sink=_write_noop)
    _, js = executor.execute(
        paths=[tmp_path],
        cfg=cfg,
        options=ScanOptions(mode=OutputMode.SUMMARY, table=TableStyle.NONE),
    )

    files = {f["path"]: f for f in js["files"]}
    entry = files.get("tiny.png")
    assert entry is not None
    assert entry.get("binary") is True
    details = entry.get("binary_details")
    assert isinstance(details, dict)
    assert details.get("format") == "png"
    assert details.get("width") == 2
    assert details.get("height") == 3
    # size should be present
    assert isinstance(details.get("size_bytes"), int)


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
