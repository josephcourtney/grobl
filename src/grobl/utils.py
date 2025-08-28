"""Generic utility helpers."""

import contextlib
from os.path import commonpath  # <-- needed by find_common_ancestor
from pathlib import Path
from typing import Any

from grobl.errors import (
    ERROR_MSG_EMPTY_PATHS,
    ERROR_MSG_NO_COMMON_ANCESTOR,
    PathNotFoundError,
)

# ---- Binary parsing constants to avoid magic numbers in code ----
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_IHDR_MIN_TOTAL = 33  # signature(8) + length(4) + type(4) + IHDR(13) + (crc ignored)
GIF_MIN_HEADER = 10
BMP_MIN_HEADER = 26
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


def find_common_ancestor(paths: list[Path]) -> Path:
    """Return the deepest common ancestor of the given paths."""
    if not paths:
        msg = ERROR_MSG_EMPTY_PATHS
        raise ValueError(msg)
    try:
        # Using os.path.commonpath for cross-drive safety.
        root = Path(commonpath([str(p.resolve()) for p in paths]))
    except ValueError as e:
        # Different drives or otherwise disjoint paths.
        msg = ERROR_MSG_NO_COMMON_ANCESTOR
        raise PathNotFoundError(msg) from e
    # Treat “only the filesystem root” as no real common ancestor.
    if root == Path(root.anchor):
        msg = ERROR_MSG_NO_COMMON_ANCESTOR
        raise PathNotFoundError(msg)
    return root


def is_text(file_path: Path) -> bool:
    """
    Determine if file is a text file.

    Heuristic: check early binary markers, then try partial UTF-8 decode.
    Avoids reading entire file.
    """
    try:
        with file_path.open("rb") as f:
            chunk = f.read(4096)
            if b"\x00" in chunk:
                return False
            try:
                chunk.decode("utf-8")
            except UnicodeDecodeError:
                return False
    except OSError:
        return False
    return True


def read_text(file_path: Path) -> str:
    """Read text from ``file_path`` using UTF-8 with ignore errors."""
    return file_path.read_text(encoding="utf-8", errors="ignore")


def _read_prefix(path: Path, size: int = 65536) -> bytes:
    try:
        with path.open("rb") as f:
            return f.read(size)
    except OSError:
        return b""


def _parse_png_dims(data: bytes) -> tuple[int | None, int | None, str | None]:
    # PNG signature and IHDR parsing
    if not data.startswith(PNG_SIGNATURE):
        return None, None, None
    # IHDR is the first chunk after signature: length(4) type(4) data(13) crc(4)
    if len(data) < PNG_IHDR_MIN_TOTAL:
        return None, None, None
    # bytes 8..12 = length, 12..16 = type 'IHDR'
    if data[12:16] != b"IHDR":
        return None, None, None
    w = int.from_bytes(data[16:20], "big")
    h = int.from_bytes(data[20:24], "big")
    color_type = data[IHDR_COLOR_TYPE_OFFSET] if len(data) > IHDR_COLOR_TYPE_OFFSET else None
    color_map = {0: "grayscale", 2: "truecolor", 3: "indexed", 4: "grayscale-alpha", 6: "rgba"}
    cstr = color_map.get(color_type) if color_type is not None else None
    return w, h, cstr


def _parse_gif_dims(data: bytes) -> tuple[int | None, int | None]:
    if not (data.startswith((b"GIF87a", b"GIF89a"))):
        return None, None
    if len(data) < GIF_MIN_HEADER:
        return None, None
    w = int.from_bytes(data[6:8], "little")
    h = int.from_bytes(data[8:10], "little")
    return w, h


def _parse_bmp_dims(data: bytes) -> tuple[int | None, int | None]:
    if not data.startswith(b"BM"):
        return None, None
    if len(data) < BMP_MIN_HEADER:
        return None, None
    # DIB header starts at offset 14, width/height at 18/22 (little-endian)
    w = int.from_bytes(data[18:22], "little")
    h = int.from_bytes(data[22:26], "little")
    return w, h


def _is_jpeg_sof_marker(marker: int) -> bool:
    return marker in JPEG_SOF_MARKERS


def _parse_jpeg_dims(data: bytes) -> tuple[int | None, int | None]:  # noqa: C901 - small, contained scanner
    # Minimal JPEG SOF scanner
    if not data.startswith(JPEG_SOI):
        return None, None
    i = 2
    data_len = len(data)
    while i + 9 < data_len:
        if data[i] != JPEG_MARKER_PREFIX:
            i += 1
            continue
        # skip pad FFs
        while i < data_len and data[i] == JPEG_MARKER_PREFIX:
            i += 1
        if i >= data_len:
            break
        marker = data[i]
        i += 1
        # markers without length
        if marker in {0xD8, 0xD9}:
            continue
        if i + 1 >= data_len:
            break
        seg_len = int.from_bytes(data[i : i + 2], "big")
        if seg_len < JPEG_MIN_SEG_LEN:
            break
        if _is_jpeg_sof_marker(marker):
            if i + 7 < data_len:
                # segment layout: len(2) precision(1) height(2) width(2) ...
                height = int.from_bytes(data[i + 3 : i + 5], "big")
                width = int.from_bytes(data[i + 5 : i + 7], "big")
                return width, height
            break
        i += seg_len
    return None, None


def probe_binary_details(path: Path) -> dict[str, Any]:
    """Return best-effort binary file details for summaries.

    - Always includes size in bytes
    - Detects common image formats (png, jpeg, gif, bmp) and extracts dimensions
    - Returns deterministic keys; omits unknowns rather than guessing
    """
    size = 0
    with contextlib.suppress(OSError):
        size = path.stat().st_size
    data = _read_prefix(path)
    details: dict[str, Any] = {"size_bytes": size}

    # PNG
    w, h, c = _parse_png_dims(data)
    if w is not None and h is not None:
        details |= {"format": "png", "width": w, "height": h}
        if c is not None:
            details["color_type"] = c
        return details
    # JPEG
    wj, hj = _parse_jpeg_dims(data)
    if wj is not None and hj is not None:
        details |= {"format": "jpeg", "width": wj, "height": hj}
        return details
    # GIF
    wg, hg = _parse_gif_dims(data)
    if wg is not None and hg is not None:
        details |= {"format": "gif", "width": wg, "height": hg}
        return details
    # BMP
    wb, hb = _parse_bmp_dims(data)
    if wb is not None and hb is not None:
        details |= {"format": "bmp", "width": wb, "height": hb}
        return details

    # Fallback: include extension as a hint if present
    ext = path.suffix.lower().lstrip(".")
    if ext:
        details["format"] = ext
    return details
