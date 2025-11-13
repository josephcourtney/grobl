"""Renderers for directory tree and file payloads.

"Why": Separate presentation (formatting) from collection (DirectoryTreeBuilder).
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape as _html_escape
from pathlib import Path
from typing import TYPE_CHECKING

from .constants import ContentScope

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from .directory import DirectoryTreeBuilder


def _escape_xml_attr(value: str) -> str:
    """Escape XML/HTML attribute characters."""
    return _html_escape(value, quote=True)


def _escape_xml_text(value: str) -> str:
    """Escape XML/HTML text content without quoting apostrophes."""
    return _html_escape(value, quote=False)


def _escape_markdown_meta(value: str) -> str:
    """Escape metadata values embedded in Markdown headers."""
    escaped = _escape_xml_attr(value)
    escaped = escaped.replace("%", "%25")
    return escaped.replace("\n", "&#10;")


@dataclass(slots=True)
class DirectoryRenderer:
    """Responsible for turning collected data into strings/lists for output."""

    builder: DirectoryTreeBuilder

    def _annotated_tree(
        self,
        formatter: Callable[[int, str, str, Path | None, tuple[int, int, bool] | None], str],
        *,
        raw_lines: Sequence[str] | None = None,
        ordered_entries: Sequence[tuple[str, Path]] | None = None,
    ) -> tuple[list[str], bool]:
        """Return formatted tree lines plus a flag indicating annotation success."""
        b = self.builder
        raw = list(raw_lines if raw_lines is not None else b.tree_output())
        base_line = f"{b.base_path.name}/"
        if not raw:
            return [base_line], False

        ordered = list(ordered_entries if ordered_entries is not None else b.ordered_entries())
        if len(ordered) != len(raw):
            return [base_line, *raw], False

        lines: list[str] = []
        for idx, (text, (kind, rel)) in enumerate(zip(raw, ordered, strict=True)):
            metadata = None
            rel_path: Path | None = rel
            if kind == "file" and rel_path is not None:
                metadata = b.get_metadata(str(rel_path))
            lines.append(formatter(idx, text, kind, rel_path, metadata))

        return [base_line, *lines], True

    def tree_lines(
        self,
        *,
        include_metadata: bool = False,
    ) -> list[str]:
        """Return the tree lines, optionally including metadata columns."""
        b = self.builder
        raw_tree = b.tree_output()

        if not include_metadata:
            body, _ = self._annotated_tree(
                lambda _i, text, _k, _r, _m: text,
                raw_lines=raw_tree,
            )
            return body

        if not raw_tree:
            return [f"{b.base_path.name}/"]

        name_w = max(len(line) for line in raw_tree)
        meta_values = list(b.metadata_items())
        max_line_digits = max((len(str(v[0])) for _, v in meta_values), default=1)
        max_char_digits = max((len(str(v[1])) for _, v in meta_values), default=1)
        line_w = max(max_line_digits, len("lines"))
        char_w = max(max_char_digits, len("chars"))
        marker_w = max(len("included"), 8)
        header = f"{'':{name_w}} {'lines':>{line_w}} {'chars':>{char_w}} {'included':>{marker_w}}"

        def _format(
            _idx: int,
            text: str,
            kind: str,
            _rel: Path | None,
            metadata: tuple[int, int, bool] | None,
        ) -> str:
            if kind != "file":
                return text
            ln, ch, included = metadata or (0, 0, False)
            marker = " " if included else "*"
            return f"{text:<{name_w}} {ln:>{line_w}} {ch:>{char_w}} {marker:>{marker_w}}"

        body, annotated = self._annotated_tree(_format, raw_lines=raw_tree)
        if not annotated:
            return body
        return [header, *body]

    def tree_lines_for_markdown(self) -> list[str]:  # noqa: C901, PLR0912
        """Return tree lines annotated with inclusion markers for markdown payloads."""
        b = self.builder
        raw_tree = b.tree_output()
        if not raw_tree:
            return [f"{b.base_path.name}/"]

        ordered = b.ordered_entries()
        if len(ordered) != len(raw_tree):
            return [f"{b.base_path.name}/", *raw_tree]

        meta_included: dict[Path, bool] = {}
        for key, (_, _, included) in b.metadata_items():
            meta_included[Path(key)] = included

        dir_any: dict[Path, bool] = {}
        dir_included: dict[Path, bool] = {}
        root = Path()
        for path, included in meta_included.items():
            parent = path.parent
            while parent != root:
                dir_any[parent] = True
                if included:
                    dir_included[parent] = True
                parent = parent.parent

        labels: dict[int, str] = {}
        name_width = 0
        for idx, (text, (kind, rel)) in enumerate(zip(raw_tree, ordered, strict=True)):
            label: str | None = None
            if kind == "file":
                included = meta_included.get(rel, False)
                label = "[INCLUDED:FULL]" if included else "[NOT_INCLUDED]"
            elif kind == "dir":
                if dir_any.get(rel) and not dir_included.get(rel):
                    label = "[NOT_INCLUDED]"
            if label is not None:
                labels[idx] = label
                name_width = max(name_width, len(text))

        if not labels:
            return [f"{b.base_path.name}/", *raw_tree]

        def _format(
            idx: int,
            text: str,
            _kind: str,
            _rel: Path | None,
            _metadata: tuple[int, int, bool] | None,
        ) -> str:
            label = labels.get(idx)
            if label is None:
                return text
            return f"{text:<{name_width}} {label}"

        body, annotated = self._annotated_tree(
            _format,
            raw_lines=raw_tree,
            ordered_entries=ordered,
        )
        if not annotated:
            return body
        return body

    def files_payload(self) -> str:
        """Return the combined <file:content> payload already collected by builder."""
        parts: list[str] = []
        for file_info in self.builder.files_json():
            name = str(file_info.get("name", ""))
            lines = int(file_info.get("lines", 0))
            chars = int(file_info.get("chars", 0))
            content = str(file_info.get("content", ""))
            parts.append(f'<file:content name="{_escape_xml_attr(name)}" lines="{lines}" chars="{chars}">')
            if content:
                parts.append(_escape_xml_text(content))
            else:
                parts.append("")
            parts.append("</file:content>")
        return "\n".join(parts)


# -------------------- LLM payload assembly moved here --------------------


@dataclass(slots=True)
class MarkdownFileSchema:
    """Schema representation for an individual file block in the markdown snapshot."""

    path: str
    language: str | None
    start_line: int
    end_line: int
    chars: int
    content: str


@dataclass(slots=True)
class MarkdownSnapshotSchema:
    """Schema containing the directory tree lines and file blocks for markdown output."""

    tree_lines: list[str] | None
    files: list[MarkdownFileSchema]


def _build_tree_payload(builder: DirectoryTreeBuilder, common: Path, *, ttag: str) -> str:
    renderer = DirectoryRenderer(builder)
    tree_xml = "\n".join(renderer.tree_lines(include_metadata=False))
    return (
        f'<{ttag} name="{_escape_xml_attr(common.name)}" '
        f'path="{_escape_xml_attr(str(common))}">\n{tree_xml}\n</{ttag}>'
    )


def _build_files_payload(builder: DirectoryTreeBuilder, common: Path, *, ftag: str) -> str:
    renderer = DirectoryRenderer(builder)
    files_xml = renderer.files_payload()
    return f'<{ftag} root="{_escape_xml_attr(common.name)}">\n{files_xml}\n</{ftag}>'


MODE_HANDLERS: dict[ContentScope, Callable[[DirectoryTreeBuilder, Path, str, str], list[str]]] = {
    ContentScope.ALL: lambda b, c, ttag, ftag: [
        _build_tree_payload(b, c, ttag=ttag),
        _build_files_payload(b, c, ftag=ftag),
    ],
    ContentScope.TREE: lambda b, c, ttag, ftag: [_build_tree_payload(b, c, ttag=ttag)],  # noqa: ARG005
    ContentScope.FILES: lambda b, c, ttag, ftag: [_build_files_payload(b, c, ftag=ftag)],  # noqa: ARG005
}


def build_llm_payload(
    *,
    builder: DirectoryTreeBuilder,
    common: Path,
    scope: ContentScope,
    tree_tag: str,
    file_tag: str,
) -> str:
    """Assemble the final LLM payload based on scope and tag names."""
    handler = MODE_HANDLERS.get(scope, MODE_HANDLERS[ContentScope.ALL])
    parts = handler(builder, common, tree_tag, file_tag)
    return "\n".join(parts)


def _guess_language(path: str) -> str:
    """Best-effort mapping from filename to code fence language label."""
    lower = path.lower()
    ext = lower.rsplit(".", 1)[-1] if "." in lower else ""
    mapping = {
        "py": "python",
        "md": "markdown",
        "markdown": "markdown",
        "toml": "toml",
        "json": "json",
        "yml": "yaml",
        "yaml": "yaml",
        "sh": "bash",
        "bash": "bash",
        "zsh": "bash",
        "fish": "fish",
        "txt": "",
    }
    return mapping.get(ext, "")


def build_markdown_snapshot(*, builder: DirectoryTreeBuilder, scope: ContentScope) -> MarkdownSnapshotSchema:
    """Build a schema object describing the markdown snapshot for a scan result."""
    renderer = DirectoryRenderer(builder)
    tree_lines: list[str] | None = None
    if scope in {ContentScope.ALL, ContentScope.TREE}:
        tree_lines = renderer.tree_lines_for_markdown()

    files: list[MarkdownFileSchema] = []
    if scope in {ContentScope.ALL, ContentScope.FILES}:
        for file_info in builder.files_json():
            name = str(file_info.get("name", ""))
            line_count = int(file_info.get("lines", 0))
            chars = int(file_info.get("chars", 0))
            content = str(file_info.get("content", ""))
            language = _guess_language(name) or None

            if line_count > 0:
                start_line = 1
                end_line = line_count
            else:
                start_line = 0
                end_line = 0

            files.append(
                MarkdownFileSchema(
                    path=name,
                    language=language,
                    start_line=start_line,
                    end_line=end_line,
                    chars=chars,
                    content=content,
                )
            )

    return MarkdownSnapshotSchema(tree_lines=tree_lines, files=files)


def format_begin_file_header(entry: MarkdownFileSchema) -> str:
    """Return the formatted BEGIN_FILE header for a markdown file block."""
    meta_parts: list[str] = [f'path="{_escape_markdown_meta(entry.path)}"']
    if entry.language:
        meta_parts.append(f'language="{_escape_markdown_meta(entry.language)}"')
    line_range = f"{entry.start_line}-{entry.end_line}"
    meta_parts.extend((f'lines="{line_range}"', f'chars="{entry.chars}"'))
    return f"%%%% BEGIN_FILE {' '.join(meta_parts)} %%%%"


def build_markdown_payload(
    *,
    builder: DirectoryTreeBuilder,
    common: Path,
    scope: ContentScope,
) -> str:
    """Assemble a Markdown payload containing a directory tree and file blocks."""
    del common
    snapshot = build_markdown_snapshot(builder=builder, scope=scope)
    parts: list[str] = ["# Project Snapshot"]

    if snapshot.tree_lines is not None:
        tree_body = "\n".join(snapshot.tree_lines)
        parts.extend((
            "",
            "## Directory",
            "",
            "```tree",
            tree_body,
            "```",
        ))

    if snapshot.files:
        parts.extend(("", "## Files"))
        for entry in snapshot.files:
            parts.extend(("", format_begin_file_header(entry)))

            fence = "```" + (entry.language or "")
            parts.append(fence)
            if entry.content:
                # Avoid spurious blank lines caused by trailing newlines in file
                # contents when rendering fenced code blocks.
                trimmed = entry.content.rstrip("\n")
                if trimmed:
                    parts.append(trimmed)
            parts.extend(("```", "%%%% END_FILE %%%%"))

    return "\n".join(parts).rstrip() + "\n"
