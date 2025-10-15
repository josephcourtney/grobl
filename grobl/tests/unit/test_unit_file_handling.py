"""Tests for grobl.file_handling module behaviors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grobl.core import run_scan
from grobl.file_handling import (
    BinaryFileHandler,
    FileAnalysis,
    FileHandlerRegistry,
    FileProcessingContext,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_run_scan_can_be_extended_with_custom_handler(tmp_path: Path) -> None:
    binary = tmp_path / "blob.bin"
    binary.write_bytes(b"abc")

    class ZeroHandler(BinaryFileHandler):
        def supports(self, *, path: Path, is_text_file: bool) -> bool:
            return path.suffix == ".bin"

        def _analyse(
            self,
            *,
            path: Path,
            context: FileProcessingContext,
            is_text_file: bool,
        ) -> FileAnalysis:
            rel = path.relative_to(context.common)
            context.builder.record_binary_details(rel, {"size_bytes": 0})
            return FileAnalysis(
                lines=0,
                chars=0,
                include_content=False,
            )

    handlers = FileHandlerRegistry.default().extend((ZeroHandler(),))
    res = run_scan(paths=[tmp_path], cfg={}, handlers=handlers)
    meta = dict(res.builder.metadata_items())
    assert meta["blob.bin"][1] == 0


def test_default_registry_exposes_handlers() -> None:
    registry = FileHandlerRegistry.default()
    assert registry.handlers, "expected default registry to have handlers registered"
