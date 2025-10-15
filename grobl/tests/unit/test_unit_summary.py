from __future__ import annotations

from pathlib import Path

from grobl.constants import OutputMode, TableStyle
from grobl.core import run_scan
from grobl.summary import SummaryContext, build_summary


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
    data = _fake_png_bytes(2, 3)
    img.write_bytes(data)

    cfg = {"exclude_tree": [], "exclude_print": []}
    result = run_scan(paths=[tmp_path], cfg=cfg)
    builder = result.builder
    rel_path = Path("tiny.png")
    builder.record_metadata(rel_path, 0, len(data))
    builder.record_binary_details(
        rel_path,
        {"format": "png", "width": 2, "height": 3, "size_bytes": len(data)},
    )
    context = SummaryContext(
        builder=builder,
        common=result.common,
        mode=OutputMode.SUMMARY,
        table=TableStyle.NONE,
    )
    js = build_summary(context)

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
