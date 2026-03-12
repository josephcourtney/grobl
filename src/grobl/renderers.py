"""Renderers for directory tree and file payloads.

"Why": Separate presentation (formatting) from collection (DirectoryTreeBuilder).
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape as _html_escape
from typing import TYPE_CHECKING

from .constants import ContentScope
from .metadata_visibility import DEFAULT_METADATA_VISIBILITY, MetadataVisibility

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from .directory import DirectoryTreeBuilder, FileSummary, SummaryTotals


def _escape_markdown_meta(value: str) -> str:
    """Escape metadata values embedded in Markdown headers."""
    escaped = _html_escape(value, quote=True)
    escaped = escaped.replace("%", "%25")
    return escaped.replace("\n", "&#10;")


def _quote_llm_attr(value: str) -> str:
    """Wrap LLM attribute values using whichever quotes avoid escaping."""
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    return '"' + value.replace('"', '\\"') + '"'


@dataclass(slots=True)
class DirectoryRenderer:
    """Responsible for turning collected data into strings/lists for output."""

    builder: DirectoryTreeBuilder

    def _annotated_tree(
        self,
        formatter: Callable[[int, str, str, Path | None, FileSummary | None], str],
        *,
        raw_lines: Sequence[str] | None = None,
        ordered_entries: Sequence[tuple[str, Path]] | None = None,
        snapshot: SummaryTotals | None = None,
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
            rel_path: Path | None = rel
            file_summary = None
            if kind == "file" and rel_path is not None and snapshot is not None:
                file_summary = snapshot.for_path(rel_path)
            lines.append(formatter(idx, text, kind, rel_path, file_summary))

        return [base_line, *lines], True

    def tree_lines(
        self,
        *,
        include_metadata: bool = False,
        visibility: MetadataVisibility = DEFAULT_METADATA_VISIBILITY,
    ) -> list[str]:
        """Return the tree lines, optionally including metadata columns."""
        b = self.builder
        raw_tree = b.tree_output()

        if not include_metadata or not visibility.shows_any_tree_metadata():
            body, _ = self._annotated_tree(
                lambda _i, text, _k, _r, _m: text,
                raw_lines=raw_tree,
            )
            return body

        if not raw_tree:
            return [f"{b.base_path.name}/"]

        snapshot = b.summary_totals()
        name_w, column_widths = _tree_metadata_widths(raw_tree, snapshot, visibility=visibility)
        header = _tree_header(name_w=name_w, column_widths=column_widths, visibility=visibility)

        def _format(
            _idx: int,
            text: str,
            kind: str,
            _rel: Path | None,
            metadata: FileSummary | None,
        ) -> str:
            if kind != "file":
                return text
            return _format_tree_file_row(
                text=text,
                record=metadata,
                name_w=name_w,
                column_widths=column_widths,
                visibility=visibility,
            )

        body, annotated = self._annotated_tree(_format, raw_lines=raw_tree, snapshot=snapshot)
        if not annotated:
            return body
        return [header, *body]

    def tree_lines_for_markdown(
        self,
        *,
        visibility: MetadataVisibility = DEFAULT_METADATA_VISIBILITY,
    ) -> list[str]:
        """Return tree lines annotated with inclusion markers for markdown payloads."""
        b = self.builder
        raw_tree = b.tree_output()
        if not raw_tree:
            return [f"{b.base_path.name}/"]
        if not visibility.inclusion_status:
            return [f"{b.base_path.name}/", *raw_tree]

        ordered = b.ordered_entries()
        if len(ordered) != len(raw_tree):
            return [f"{b.base_path.name}/", *raw_tree]

        snapshot = b.summary_totals()
        labels, name_width = _markdown_labels(raw_tree=raw_tree, ordered=ordered, snapshot=snapshot)

        if not labels:
            return [f"{b.base_path.name}/", *raw_tree]

        def _format(
            idx: int,
            text: str,
            _kind: str,
            _rel: Path | None,
            _metadata: FileSummary | None,
        ) -> str:
            label = labels.get(idx)
            if label is None:
                return text
            return f"{text:<{name_width}} {label}"

        body, annotated = self._annotated_tree(
            _format,
            raw_lines=raw_tree,
            ordered_entries=ordered,
            snapshot=snapshot,
        )
        if not annotated:
            return body
        return body

    def files_payload(self, *, visibility: MetadataVisibility = DEFAULT_METADATA_VISIBILITY) -> str:
        """Return the combined <file:content> payload already collected by builder."""
        parts: list[str] = []
        for file_info in self.builder.files_json():
            name = str(file_info.get("name", ""))
            lines = int(file_info.get("lines", 0))
            chars = int(file_info.get("chars", 0))
            tokens = int(file_info.get("tokens", 0))
            content = str(file_info.get("content", ""))
            attrs = [f"name={_quote_llm_attr(name)}"]
            if visibility.lines:
                attrs.append(f'lines="{lines}"')
            if visibility.chars:
                attrs.append(f'chars="{chars}"')
            if visibility.tokens:
                attrs.append(f'tokens="{tokens}"')
            parts.append(f"<file:content {' '.join(attrs)}>")
            if content:
                parts.append(content)
            else:
                parts.append("")
            parts.append("</file:content>")
        return "\n".join(parts)


def _tree_metadata_widths(
    raw_tree: list[str],
    snapshot: SummaryTotals,
    *,
    visibility: MetadataVisibility,
) -> tuple[int, dict[str, int]]:
    meta_values = list(snapshot.iter_files())
    return (
        max(len(line) for line in raw_tree),
        {
            "lines": max(
                max((len(str(record.lines)) for _, record in meta_values), default=1),
                len("lines"),
            )
            if visibility.lines
            else 0,
            "chars": max(
                max((len(str(record.chars)) for _, record in meta_values), default=1),
                len("chars"),
            )
            if visibility.chars
            else 0,
            "tokens": max(
                max((len(str(record.tokens)) for _, record in meta_values), default=1),
                len("tokens"),
            )
            if visibility.tokens
            else 0,
            "included": max(len("included"), 8) if visibility.inclusion_status else 0,
        },
    )


def _markdown_labels(
    *,
    raw_tree: list[str],
    ordered: list[tuple[str, Path]],
    snapshot: SummaryTotals,
) -> tuple[dict[int, str], int]:
    labels: dict[int, str] = {}
    name_width = 0
    for idx, (text, (kind, rel)) in enumerate(zip(raw_tree, ordered, strict=True)):
        label: str | None = None
        if kind == "file":
            label = snapshot.marker_for_file(rel)
        elif kind == "dir":
            label = snapshot.marker_for_directory(rel)
        if label is not None:
            labels[idx] = label
            name_width = max(name_width, len(text))
    return labels, name_width


def _tree_header(
    *,
    name_w: int,
    column_widths: dict[str, int],
    visibility: MetadataVisibility,
) -> str:
    header_parts = [f"{'':{name_w}}"]
    if visibility.lines:
        header_parts.append(f"{'lines':>{column_widths['lines']}}")
    if visibility.chars:
        header_parts.append(f"{'chars':>{column_widths['chars']}}")
    if visibility.tokens:
        header_parts.append(f"{'tokens':>{column_widths['tokens']}}")
    if visibility.inclusion_status:
        header_parts.append(f"{'included':>{column_widths['included']}}")
    return " ".join(header_parts)


def _format_tree_file_row(
    *,
    text: str,
    record: FileSummary | None,
    name_w: int,
    column_widths: dict[str, int],
    visibility: MetadataVisibility,
) -> str:
    fields = [f"{text:<{name_w}}"]
    if visibility.lines:
        ln = record.lines if record is not None else 0
        fields.append(f"{ln:>{column_widths['lines']}}")
    if visibility.chars:
        ch = record.chars if record is not None else 0
        fields.append(f"{ch:>{column_widths['chars']}}")
    if visibility.tokens:
        tok = record.tokens if record is not None else 0
        fields.append(f"{tok:>{column_widths['tokens']}}")
    if visibility.inclusion_status:
        included = record.included if record is not None else False
        marker = " " if included else "*"
        fields.append(f"{marker:>{column_widths['included']}}")
    return " ".join(fields)


# -------------------- LLM payload assembly moved here --------------------


@dataclass(slots=True)
class MarkdownFileSchema:
    """Schema representation for an individual file block in the markdown snapshot."""

    path: str
    language: str | None
    start_line: int
    end_line: int
    chars: int
    tokens: int
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
        f"<{ttag} name={_quote_llm_attr(common.name)} "
        f"path={_quote_llm_attr(str(common))}>\n{tree_xml}\n</{ttag}>"
    )


def _build_files_payload(
    builder: DirectoryTreeBuilder,
    common: Path,
    *,
    visibility: MetadataVisibility,
    ftag: str,
) -> str:
    renderer = DirectoryRenderer(builder)
    files_xml = renderer.files_payload(visibility=visibility)
    return f"<{ftag} root={_quote_llm_attr(common.name)}>\n{files_xml}\n</{ftag}>"


def build_llm_payload(
    *,
    builder: DirectoryTreeBuilder,
    common: Path,
    scope: ContentScope,
    visibility: MetadataVisibility = DEFAULT_METADATA_VISIBILITY,
    tree_tag: str,
    file_tag: str,
) -> str:
    """Assemble the final LLM payload based on scope and tag names."""
    parts: list[str] = []
    if scope in {ContentScope.ALL, ContentScope.TREE}:
        parts.append(_build_tree_payload(builder, common, ttag=tree_tag))
    if scope in {ContentScope.ALL, ContentScope.FILES}:
        parts.append(_build_files_payload(builder, common, visibility=visibility, ftag=file_tag))
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


def build_markdown_snapshot(
    *,
    builder: DirectoryTreeBuilder,
    scope: ContentScope,
    visibility: MetadataVisibility = DEFAULT_METADATA_VISIBILITY,
) -> MarkdownSnapshotSchema:
    """Build a schema object describing the markdown snapshot for a scan result."""
    renderer = DirectoryRenderer(builder)
    tree_lines: list[str] | None = None
    if scope in {ContentScope.ALL, ContentScope.TREE}:
        tree_lines = renderer.tree_lines_for_markdown(visibility=visibility)

    files: list[MarkdownFileSchema] = []
    if scope in {ContentScope.ALL, ContentScope.FILES}:
        for file_info in builder.files_json():
            name = str(file_info.get("name", ""))
            line_count = int(file_info.get("lines", 0))
            chars = int(file_info.get("chars", 0))
            tokens = int(file_info.get("tokens", 0))
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
                    tokens=tokens,
                    content=content,
                )
            )

    return MarkdownSnapshotSchema(tree_lines=tree_lines, files=files)


def format_begin_file_header(
    entry: MarkdownFileSchema,
    *,
    visibility: MetadataVisibility = DEFAULT_METADATA_VISIBILITY,
) -> str:
    """Return the formatted BEGIN_FILE header for a markdown file block."""
    meta_parts: list[str] = [f'path="{_escape_markdown_meta(entry.path)}"']
    if entry.language:
        meta_parts.append(f'language="{_escape_markdown_meta(entry.language)}"')
    if visibility.lines:
        line_range = f"{entry.start_line}-{entry.end_line}"
        meta_parts.append(f'lines="{line_range}"')
    if visibility.chars:
        meta_parts.append(f'chars="{entry.chars}"')
    if visibility.tokens:
        meta_parts.append(f'tokens="{entry.tokens}"')
    return f"%%%% BEGIN_FILE {' '.join(meta_parts)} %%%%"


def build_markdown_payload(
    *,
    builder: DirectoryTreeBuilder,
    common: Path,
    scope: ContentScope,
    visibility: MetadataVisibility = DEFAULT_METADATA_VISIBILITY,
) -> str:
    """Assemble a Markdown payload containing a directory tree and file blocks."""
    del common
    snapshot = build_markdown_snapshot(builder=builder, scope=scope, visibility=visibility)
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
            parts.extend(("", format_begin_file_header(entry, visibility=visibility)))

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
