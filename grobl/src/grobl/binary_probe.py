"""Binary file probing utilities (format detection and dimensions).

Separated from generic utilities to keep responsibilities focused and ease testing.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

# ---- Binary parsing constants to avoid magic numbers in code ----
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_IHDR_MIN_TOTAL = 33  # signature(8) + length(4) + type(4) + IHDR(13) + (crc ignored)
JPEG_MARKER_PREFIX = 0xFF
JPEG_SOI = b"\xff\xd8"
JPEG_SOF_MARKERS = {
    0xC0,
    0xC1,
    0xC2,
    0xC3,
    0xC5,
    0xC6,
    0xC7,
    0xC9,
    0xCA,
    0xCB,
    0xCD,
    0xCE,
    0xCF,
}
JPEG_MIN_SEG_LEN = 2

IHDR_COLOR_TYPE_OFFSET = 25


@runtime_checkable
class BinaryParser(Protocol):
    """Strategy for parsing a specific binary format."""

    def parse(self, data: bytes) -> dict[str, Any] | None: ...


def _read_prefix(path: Path, size: int = 65536) -> bytes:
    try:
        with path.open("rb") as f:
            return f.read(size)
    except OSError:
        return b""


class PngParser:
    @staticmethod
    def parse(data: bytes) -> dict[str, Any] | None:
        if not data.startswith(PNG_SIGNATURE):
            return None
        if len(data) < PNG_IHDR_MIN_TOTAL:
            return None
        if data[12:16] != b"IHDR":
            return None
        w = int.from_bytes(data[16:20], "big")
        h = int.from_bytes(data[20:24], "big")
        color_type = data[IHDR_COLOR_TYPE_OFFSET] if len(data) > IHDR_COLOR_TYPE_OFFSET else None
        color_map = {0: "grayscale", 2: "truecolor", 3: "indexed", 4: "grayscale-alpha", 6: "rgba"}
        details: dict[str, Any] = {"format": "png", "width": w, "height": h}
        if color_type is not None and (cstr := color_map.get(color_type)):
            details["color_type"] = cstr
        return details


def _is_jpeg_sof_marker(marker: int) -> bool:
    return marker in JPEG_SOF_MARKERS


class JpegParser:
    @staticmethod
    def parse(data: bytes) -> dict[str, Any] | None:  # noqa: C901 - small, contained scanner
        if not data.startswith(JPEG_SOI):
            return None
        i = 2
        data_len = len(data)
        while i + 9 < data_len:
            if data[i] != JPEG_MARKER_PREFIX:
                i += 1
                continue
            while i < data_len and data[i] == JPEG_MARKER_PREFIX:
                i += 1
            if i >= data_len:
                break
            marker = data[i]
            i += 1
            if marker in {0xD8, 0xD9}:  # SOI/EOI w/o length
                continue
            if i + 1 >= data_len:
                break
            seg_len = int.from_bytes(data[i : i + 2], "big")
            if seg_len < JPEG_MIN_SEG_LEN:
                break
            if _is_jpeg_sof_marker(marker):
                if i + 7 < data_len:
                    height = int.from_bytes(data[i + 3 : i + 5], "big")
                    width = int.from_bytes(data[i + 5 : i + 7], "big")
                    return {"format": "jpeg", "width": width, "height": height}
                break
            i += seg_len
        return None


PARSERS = (PngParser(), JpegParser())


def probe_binary_details(path: Path) -> dict[str, Any]:
    """Return best-effort binary file details for summaries.

    - Always includes size in bytes
    - Detects PNG and JPEG image dimensions; other formats fall back to file extension only
    - Returns deterministic keys; omits unknowns rather than guessing
    """
    size = 0
    with contextlib.suppress(OSError):
        size = path.stat().st_size
    data = _read_prefix(path)
    details: dict[str, Any] = {"size_bytes": size}

    for parser in PARSERS:
        parsed = parser.parse(data)
        if parsed:
            details |= parsed
            return details

    # Fallback: include extension as a hint if present
    ext = path.suffix.lower().lstrip(".")
    if ext:
        details["format"] = ext
    return details
