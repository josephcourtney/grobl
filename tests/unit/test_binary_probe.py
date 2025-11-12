from __future__ import annotations

from typing import TYPE_CHECKING

from grobl.binary_probe import probe_binary_details

if TYPE_CHECKING:
    from pathlib import Path


def _fake_png_bytes(width: int, height: int) -> bytes:
    # signature + length(13) + "IHDR" + width + height + bit_depth + color_type + misc + crc
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_len = (13).to_bytes(4, "big")
    ihdr = b"IHDR"
    w = width.to_bytes(4, "big")
    h = height.to_bytes(4, "big")
    bit_depth = (8).to_bytes(1, "big")
    color_type = (6).to_bytes(1, "big")  # RGBA
    rest = b"\x00\x00\x00"  # compression, filter, interlace
    crc = b"\x00\x00\x00\x00"
    return sig + ihdr_len + ihdr + w + h + bit_depth + color_type + rest + crc


def _fake_gif_bytes(width: int, height: int) -> bytes:
    # Header (6) + Logical Screen Descriptor (4) is minimum for our parser
    return b"GIF89a" + width.to_bytes(2, "little") + height.to_bytes(2, "little")


def _fake_bmp_bytes(width: int, height: int) -> bytes:
    # Minimum 26 bytes; write BM header and width/height in expected offsets.
    b = bytearray(26)
    b[0:2] = b"BM"
    b[18:22] = width.to_bytes(4, "little")
    b[22:26] = height.to_bytes(4, "little")
    return bytes(b)


def _fake_jpeg_bytes(width: int, height: int) -> bytes:
    # SOI + SOF0 segment with width/height
    soi = b"\xff\xd8"
    # marker FF C0, length 0x0011, precision 8, H, W, and 3 components metadata (ignored by parser)
    sof = (
        b"\xff\xc0"
        b"\x00\x11"
        b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    )
    return soi + sof


def test_probe_png_detects_dimensions(tmp_path: Path) -> None:
    p = tmp_path / "img.png"
    p.write_bytes(_fake_png_bytes(2, 3))
    d = probe_binary_details(p)
    assert d["format"] == "png"
    assert d["width"] == 2
    assert d["height"] == 3
    assert d["size_bytes"] == p.stat().st_size


def test_probe_gif_detects_dimensions(tmp_path: Path) -> None:
    p = tmp_path / "anim.gif"
    p.write_bytes(_fake_gif_bytes(11, 7))
    d = probe_binary_details(p)
    assert d["format"] == "gif"
    assert d["width"] == 11
    assert d["height"] == 7


def test_probe_bmp_detects_dimensions(tmp_path: Path) -> None:
    p = tmp_path / "img.bmp"
    p.write_bytes(_fake_bmp_bytes(9, 5))
    d = probe_binary_details(p)
    assert d["format"] == "bmp"
    assert d["width"] == 9
    assert d["height"] == 5


def test_probe_jpeg_detects_dimensions(tmp_path: Path) -> None:
    p = tmp_path / "photo.jpg"
    p.write_bytes(_fake_jpeg_bytes(320, 200))
    d = probe_binary_details(p)
    assert d["format"] == "jpeg"
    assert d["width"] == 320
    assert d["height"] == 200


def test_probe_unknown_reports_size_and_extension(tmp_path: Path) -> None:
    p = tmp_path / "blob.xyz"
    p.write_bytes(b"\x01\x02\x03\x04\x05")
    d = probe_binary_details(p)
    assert d["size_bytes"] == 5
    # falls back to extension when format is unknown
    assert d.get("format") == "xyz"
