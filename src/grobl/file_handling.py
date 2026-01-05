"""File processing strategies used by :mod:`grobl.core`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .utils import TextDetectionResult, detect_text, read_text

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from pathspec import PathSpec

    from .directory import DirectoryTreeBuilder


@dataclass(frozen=True, slots=True)
class ScanDependencies:
    """Gateway used by the scanner to perform I/O."""

    text_detector: Callable[[Path], TextDetectionResult]
    text_reader: Callable[[Path], str]

    @classmethod
    def default(cls) -> ScanDependencies:
        return cls(
            text_detector=detect_text,
            text_reader=read_text,
        )


@dataclass(frozen=True, slots=True)
class FileProcessingContext:
    """Immutable context shared across file handlers."""

    builder: DirectoryTreeBuilder
    common: Path
    match_base: Path
    print_spec: PathSpec
    dependencies: ScanDependencies


@dataclass(frozen=True, slots=True)
class FileAnalysis:
    """Intermediate result produced by file handlers."""

    lines: int
    chars: int
    include_content: bool
    content: str | None = None


class BaseFileHandler:
    """Template method workflow for handling files."""

    def supports(self, *, path: Path, is_text_file: bool) -> bool:
        raise NotImplementedError

    def process(
        self,
        *,
        path: Path,
        context: FileProcessingContext,
        is_text_file: bool,
        detection: TextDetectionResult,
    ) -> None:
        rel = path.relative_to(context.common)
        analysis = self._analyze(
            path=path,
            context=context,
            is_text_file=is_text_file,
            detection=detection,
        )
        builder = context.builder
        builder.record_metadata(rel, analysis.lines, analysis.chars)
        if analysis.include_content and analysis.content is not None:
            builder.add_file(path, rel, analysis.lines, analysis.chars, analysis.content)

    def _analyze(
        self,
        *,
        path: Path,
        context: FileProcessingContext,
        is_text_file: bool,
        detection: TextDetectionResult,
    ) -> FileAnalysis:
        raise NotImplementedError


class TextFileHandler(BaseFileHandler):
    """Handle text files by capturing metadata and, optionally, contents."""

    def supports(self, *, path: Path, is_text_file: bool) -> bool:
        _ = self
        _ = path
        return is_text_file

    def _analyze(
        self,
        *,
        path: Path,
        context: FileProcessingContext,
        is_text_file: bool,
        detection: TextDetectionResult,
    ) -> FileAnalysis:
        _ = self
        del is_text_file
        deps = context.dependencies
        content = deps.text_reader(path) if detection.content is None else detection.content
        line_count = len(content.splitlines())
        char_count = len(content)
        rel_match = path.relative_to(context.match_base)
        include = not context.print_spec.match_file(rel_match.as_posix())
        return FileAnalysis(
            lines=line_count,
            chars=char_count,
            include_content=include,
            content=content,
        )


# --------------------------------------------------------------------------- #
# NEW: simple handler for binary files                                        #
# --------------------------------------------------------------------------- #


class BinaryFileHandler(BaseFileHandler):
    """Record metadata for binary files (size only, no contents)."""

    def supports(self, *, path: Path, is_text_file: bool) -> bool:
        _ = self
        _ = path
        return not is_text_file

    def _analyze(
        self,
        *,
        path: Path,
        context: FileProcessingContext,
        is_text_file: bool,
        detection: TextDetectionResult,
    ) -> FileAnalysis:
        _ = self
        del context, is_text_file, detection
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        # For binary blobs we expose character-count as byte size, 0 lines.
        return FileAnalysis(lines=0, chars=size, include_content=False)


@dataclass(slots=True)
class FileHandlerRegistry:
    """Strategy registry that keeps :func:`run_scan` open for extension."""

    handlers: tuple[BaseFileHandler, ...]

    @classmethod
    def default(cls) -> FileHandlerRegistry:
        return cls(handlers=(TextFileHandler(), BinaryFileHandler()))

    def handle(self, *, path: Path, context: FileProcessingContext) -> None:
        deps = context.dependencies
        detection = deps.text_detector(path)
        is_text_file = detection.is_text
        for handler in self.handlers:
            if handler.supports(path=path, is_text_file=is_text_file):
                handler.process(
                    path=path,
                    context=context,
                    is_text_file=is_text_file,
                    detection=detection,
                )
                return
        msg = f"no handler registered for {path}"
        raise ValueError(msg)

    def extend(self, extra_handlers: Iterable[BaseFileHandler]) -> FileHandlerRegistry:
        return FileHandlerRegistry(handlers=tuple(extra_handlers) + self.handlers)
