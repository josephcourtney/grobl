from __future__ import annotations

from typing import TYPE_CHECKING

from pathspec import PathSpec

from grobl.directory import DirectoryTreeBuilder
from grobl.file_handling import (
    BinaryFileHandler,
    FileProcessingContext,
    ScanDependencies,
    TextFileHandler,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _deps(
    *,
    detector: Callable[[Path], bool],
    reader: Callable[[Path], str],
    probe: Callable[[Path], dict[str, object]],
) -> ScanDependencies:
    return ScanDependencies(text_detector=detector, text_reader=reader, binary_probe=probe)


def test_text_handler_respects_exclude_print_and_records_contents(tmp_path: Path) -> None:
    inc = tmp_path / "inc.txt"
    inc.write_text("hello\nworld\n", encoding="utf-8")
    skip = tmp_path / "skip.txt"
    skip.write_text("skip\n", encoding="utf-8")

    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    spec = PathSpec.from_lines("gitwildmatch", ["skip.txt"])
    deps = _deps(detector=lambda _p: True, reader=lambda p: p.read_text("utf-8"), probe=lambda _p: {})
    ctx = FileProcessingContext(builder=builder, common=tmp_path, print_spec=spec, dependencies=deps)

    handler = TextFileHandler()
    assert handler.supports(path=inc, is_text_file=True)
    handler.process(path=inc, context=ctx, is_text_file=True)
    handler.process(path=skip, context=ctx, is_text_file=True)

    m = dict(builder.metadata_items())
    assert m["inc.txt"] == (2, len("hello\nworld\n"), True)
    assert m["skip.txt"][2] is False
    # contents include only the included file
    payload = "\n".join(builder.file_contents())
    assert 'name="inc.txt"' in payload
    assert "skip.txt" not in payload


def test_binary_handler_records_size_and_details(tmp_path: Path) -> None:
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"\x01\x02\x03\x04")

    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    spec = PathSpec.from_lines("gitwildmatch", [])
    details = {"size_bytes": 99, "format": "bin"}
    deps = _deps(detector=lambda _p: False, reader=lambda _p: "", probe=lambda _p: details)
    ctx = FileProcessingContext(builder=builder, common=tmp_path, print_spec=spec, dependencies=deps)

    handler = BinaryFileHandler()
    assert handler.supports(path=blob, is_text_file=False)
    handler.process(path=blob, context=ctx, is_text_file=False)

    m = dict(builder.metadata_items())
    assert m["blob.bin"] == (0, 99, False)
    assert builder.get_binary_details("blob.bin") == details
