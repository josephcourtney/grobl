from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pathspec import PathSpec

from grobl.directory import DirectoryTreeBuilder
from grobl.file_handling import FileProcessingContext, ScanDependencies, TextFileHandler
from grobl.utils import TextDetectionResult

pytestmark = pytest.mark.small

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _deps(
    *,
    detector: Callable[[Path], TextDetectionResult],
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
    reader_calls: list[Path] = []

    def detector(path: Path) -> TextDetectionResult:
        return TextDetectionResult(is_text=True, content=path.read_text(encoding="utf-8"))

    def reader(path: Path) -> str:
        reader_calls.append(path)
        return path.read_text(encoding="utf-8")

    deps = _deps(detector=detector, reader=reader)
    ctx = FileProcessingContext(
        builder=builder,
        common=tmp_path,
        match_base=tmp_path,
        print_spec=spec,
        dependencies=deps,
    )

    handler = TextFileHandler()
    detection_inc = detector(inc)
    detection_skip = detector(skip)

    assert handler.supports(path=inc, is_text_file=detection_inc.is_text)
    handler.process(
        path=inc,
        context=ctx,
        is_text_file=detection_inc.is_text,
        detection=detection_inc,
    )
    handler.process(
        path=skip,
        context=ctx,
        is_text_file=detection_skip.is_text,
        detection=detection_skip,
    )

    m = dict(builder.metadata_items())
    assert m["inc.txt"] == (2, len("hello\nworld\n"), True)
    assert m["skip.txt"][2] is False
    # contents include only the included file
    payload = "\n".join(builder.file_contents())
    assert 'name="inc.txt"' in payload
    assert "skip.txt" not in payload
    assert reader_calls == []
