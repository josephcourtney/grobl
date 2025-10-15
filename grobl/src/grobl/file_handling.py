"""File processing strategies used by :mod:`grobl.core`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .utils import is_text, read_text

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from pathspec import PathSpec

    from .directory import DirectoryTreeBuilder


@dataclass(frozen=True, slots=True)
class ScanDependencies:
    """Gateway used by the scanner to perform I/O."""

    text_detector: Callable[[Path], bool]
    text_reader: Callable[[Path], str]

    @classmethod
    def default(cls) -> ScanDependencies:
        return cls(
            text_detector=is_text,
            text_reader=read_text,
        )


@dataclass(frozen=True, slots=True)
class FileProcessingContext:
    """Immutable context shared across file handlers."""

    builder: DirectoryTreeBuilder
    common: Path
    print_spec: PathSpec
    dependencies: ScanDependencies


@dataclass(frozen=True, slots=True)
class FileAnalysis:
    """Intermediate result produced by file handlers."""

    lines: int
    chars: int
    include_content: bool
    content: str | None = None
    binary_details: dict[str, object] | None = None


class BaseFileHandler:
    """Template method workflow for handling files."""

    def supports(self, *, path: Path, is_text_file: bool) -> bool:
        raise NotImplementedError

    def process(self, *, path: Path, context: FileProcessingContext, is_text_file: bool) -> None:
        rel = path.relative_to(context.common)
        analysis = self._analyse(path=path, context=context, is_text_file=is_text_file)
        builder = context.builder
        builder.record_metadata(rel, analysis.lines, analysis.chars)
        if analysis.include_content and analysis.content is not None:
            builder.add_file(path, rel, analysis.lines, analysis.chars, analysis.content)
        if analysis.binary_details:
            builder.record_binary_details(rel, analysis.binary_details)

    def _analyse(
        self,
        *,
        path: Path,
        context: FileProcessingContext,
        is_text_file: bool,
    ) -> FileAnalysis:
        raise NotImplementedError


class TextFileHandler(BaseFileHandler):
    """Handle text files by capturing metadata and, optionally, contents."""

    @staticmethod
    def supports(*, path: Path, is_text_file: bool) -> bool:  # noqa: ARG004 - `path` unused
        return is_text_file

    @staticmethod
    def _analyse(
        *,
        path: Path,
        context: FileProcessingContext,
        is_text_file: bool,  # noqa: ARG004 - template signature
    ) -> FileAnalysis:
        deps = context.dependencies
        content = deps.text_reader(path)
        line_count = len(content.splitlines())
        char_count = len(content)
        rel = path.relative_to(context.common)
        include = not context.print_spec.match_file(rel.as_posix())
        return FileAnalysis(
            lines=line_count,
            chars=char_count,
            include_content=include,
            content=content,
        )


class BinaryFileHandler(BaseFileHandler):
    """Handle binary files by storing metadata and derived details."""

    @staticmethod
    def supports(*, path: Path, is_text_file: bool) -> bool:  # noqa: ARG004 - `path` unused
        return not is_text_file

    @staticmethod
    def _analyse(
        *,
        path: Path,
        context: FileProcessingContext,
        is_text_file: bool,  # noqa: ARG004 - template signature
    ) -> FileAnalysis:
        size = int(details.get("size_bytes", 0))
        return FileAnalysis(
            lines=0,
            chars=size,
            include_content=False,
        )


@dataclass(slots=True)
class FileHandlerRegistry:
    """Strategy registry that keeps :func:`run_scan` open for extension."""

    handlers: tuple[BaseFileHandler, ...]

    @classmethod
    def default(cls) -> FileHandlerRegistry:
        return cls(handlers=(TextFileHandler(), BinaryFileHandler()))

    def handle(self, *, path: Path, context: FileProcessingContext) -> None:
        deps = context.dependencies
        is_text_file = deps.text_detector(path)
        for handler in self.handlers:
            if handler.supports(path=path, is_text_file=is_text_file):
                handler.process(path=path, context=context, is_text_file=is_text_file)
                return
        msg = f"no handler registered for {path}"
        raise ValueError(msg)

    def extend(self, extra_handlers: Iterable[BaseFileHandler]) -> FileHandlerRegistry:
        return FileHandlerRegistry(handlers=tuple(extra_handlers) + self.handlers)
