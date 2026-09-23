"""File processing strategies used by :mod:`grobl.core`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .constants import InclusionLevel
from .provenance import format_content_reason, inclusion_reason_to_dict
from .resource_limits import UNLIMITED_RESOURCE_LIMITS, ResourceBudget
from .token_counting import count_tokens
from .utils import TextDetectionResult, detect_text, read_text

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from .directory import DirectoryTreeBuilder
    from .ignore import LayeredIgnoreMatcher
    from .timing import TimingRecorder


@dataclass(frozen=True, slots=True)
class ScanDependencies:
    """Gateway used by the scanner to perform I/O."""

    text_detector: Callable[[Path], TextDetectionResult]
    text_reader: Callable[[Path], str]

    @classmethod
    def default(cls) -> ScanDependencies:
        return cls(text_detector=detect_text, text_reader=read_text)


@dataclass(frozen=True, slots=True)
class FileProcessingContext:
    """Immutable context shared across file handlers."""

    builder: DirectoryTreeBuilder
    common: Path
    ignores: LayeredIgnoreMatcher
    dependencies: ScanDependencies
    budget: ResourceBudget = field(default_factory=lambda: ResourceBudget(UNLIMITED_RESOURCE_LIMITS))
    timing: TimingRecorder | None = None


@dataclass(frozen=True, slots=True)
class FileAnalysis:
    """Intermediate result produced by file handlers."""

    lines: int
    chars: int
    tokens: int
    include_content: bool
    content: str | None = None
    content_reason: dict[str, object] | None = None


def _read_text_content(
    path: Path,
    context: FileProcessingContext,
    detection: TextDetectionResult,
) -> str:
    if detection.content is not None:
        return detection.content
    reader = context.dependencies.text_reader
    if context.timing is None:
        return reader(path)
    with context.timing.measure("file reading", depth=1):
        return reader(path)


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
        builder.record_metadata(
            rel,
            analysis.lines,
            analysis.chars,
            analysis.tokens,
            content_reason=analysis.content_reason,
        )
        if analysis.include_content and analysis.content is not None:
            builder.add_file(
                path,
                rel,
                analysis.lines,
                analysis.chars,
                analysis.tokens,
                analysis.content,
            )

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
    """Handle text files by capturing metadata and contents."""

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
        try:
            content = _read_text_content(path, context, detection)
        except OSError as err:
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            return FileAnalysis(
                lines=0,
                chars=size,
                tokens=0,
                include_content=False,
                content_reason=format_content_reason(
                    detection_detail=f"read error: {err}",
                    subject=path,
                ),
            )
        line_count = len(content.splitlines())
        char_count = len(content)
        if context.timing is None:
            token_count = count_tokens(content)
            decision = context.ignores.explain_inclusion(path, is_dir=False)
        else:
            with context.timing.measure("token counting", depth=1):
                token_count = count_tokens(content)
            with context.timing.measure("policy matching", depth=1):
                decision = context.ignores.explain_inclusion(path, is_dir=False)
        include_content = decision.level is InclusionLevel.FULL
        reason = (
            inclusion_reason_to_dict(decision.reason)
            if not include_content and decision.reason is not None
            else None
        )
        if include_content:
            try:
                file_bytes = path.stat().st_size
            except OSError:
                file_bytes = len(content.encode("utf-8"))
            budget_reason = context.budget.accept(
                path,
                file_bytes=file_bytes,
                tokens=token_count,
            )
            if budget_reason is not None:
                include_content = False
                reason = budget_reason

        return FileAnalysis(
            lines=line_count,
            chars=char_count,
            tokens=token_count,
            include_content=include_content,
            content=content,
            content_reason=reason,
        )


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
        del context, is_text_file
        reason_dict = format_content_reason(
            detection_detail=detection.detail,
            subject=path,
        )
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        return FileAnalysis(
            lines=0,
            chars=size,
            tokens=0,
            include_content=False,
            content_reason=reason_dict,
        )


@dataclass(slots=True)
class FileHandlerRegistry:
    """Strategy registry that keeps :func:`run_scan` open for extension."""

    handlers: tuple[BaseFileHandler, ...]

    @classmethod
    def default(cls) -> FileHandlerRegistry:
        return cls(handlers=(TextFileHandler(), BinaryFileHandler()))

    def handle(self, *, path: Path, context: FileProcessingContext) -> None:
        if context.timing is None:
            decision = context.ignores.explain_inclusion(path, is_dir=False)
        else:
            with context.timing.measure("policy matching", depth=1):
                decision = context.ignores.explain_inclusion(path, is_dir=False)
        if decision.level is InclusionLevel.TREE_ONLY:
            # TREE_ONLY is intentionally cheap: do not read or text-detect the
            # file merely to report metadata for content that will not be sent.
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            reason = inclusion_reason_to_dict(decision.reason) if decision.reason is not None else None
            context.builder.record_metadata(
                path.relative_to(context.common),
                0,
                size,
                0,
                content_reason=reason,
            )
            return

        try:
            file_bytes = path.stat().st_size
        except OSError:
            file_bytes = None
        if file_bytes is not None:
            budget_reason = context.budget.preflight(path, file_bytes=file_bytes)
            if budget_reason is not None:
                context.builder.record_metadata(
                    path.relative_to(context.common),
                    0,
                    0,
                    0,
                    content_reason=budget_reason,
                )
                return

        deps = context.dependencies
        if context.timing is None:
            detection = deps.text_detector(path)
        else:
            with context.timing.measure("text detection", depth=1):
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
