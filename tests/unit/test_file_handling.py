from __future__ import annotations

from typing import TYPE_CHECKING

from pathspec import PathSpec

from grobl.directory import DirectoryTreeBuilder
from grobl.file_handling import (
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
) -> ScanDependencies:
    return ScanDependencies(text_detector=detector, text_reader=reader)


def test_text_handler_respects_exclude_print_and_records_contents(tmp_path: Path) -> None:
    inc = tmp_path / "inc.txt"
    inc.write_text("hello\nworld\n", encoding="utf-8")
    skip = tmp_path / "skip.txt"
    skip.write_text("skip\n", encoding="utf-8")

    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    spec = PathSpec.from_lines("gitwildmatch", ["skip.txt"])
    deps = _deps(detector=lambda _p: True, reader=lambda p: p.read_text("utf-8"))
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
