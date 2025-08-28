"""Renderers for directory tree and file payloads.

"Why": Separate presentation (formatting) from collection (DirectoryTreeBuilder).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .constants import OutputMode

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .directory import DirectoryTreeBuilder


@dataclass(slots=True)
class DirectoryRenderer:
    """Responsible for turning collected data into strings/lists for output."""

    builder: DirectoryTreeBuilder

    def tree_lines(
        self,
        *,
        include_metadata: bool = False,
    ) -> list[str]:
        """Return the tree lines, optionally including metadata columns."""
        b = self.builder
        raw_tree = b.tree_output()

        if not include_metadata:
            return [b.base_path.name, *raw_tree]

        if not raw_tree:
            return [b.base_path.name]

        def _column_widths() -> tuple[int, int, int, int]:
            name_w = max(len(line) for line in raw_tree)
            meta_values = list(b.metadata_items())
            max_line_digits = max((len(str(v[0])) for _, v in meta_values), default=1)
            max_char_digits = max((len(str(v[1])) for _, v in meta_values), default=1)
            line_w = max(max_line_digits, len("lines"))
            char_w = max(max_char_digits, len("chars"))
            marker_w = max(len("included"), 8)
            return name_w, line_w, char_w, marker_w

        widths = _column_widths()
        name_w, line_w, char_w, mark_w = widths
        header = f"{'':{name_w}} {'lines':>{line_w}} {'chars':>{char_w}} {'included':>{mark_w}}"
        output = [header, b.base_path.name]

        entry_map = dict(b.file_tree_entries())
        for idx, text in enumerate(raw_tree):
            rel = entry_map.get(idx)
            if rel is None:
                output.append(text)
                continue
            ln, ch, included = b.get_metadata(str(rel)) or (0, 0, False)
            marker = " " if included else "*"
            output.append(f"{text:<{name_w}} {ln:>{line_w}} {ch:>{char_w}} {marker:>{mark_w}}")

        return output

    def files_payload(self) -> str:
        """Return the combined <file:content> payload already collected by builder."""
        return "\n".join(self.builder.file_contents())


# -------------------- LLM payload assembly moved here --------------------


def _build_tree_payload(builder: DirectoryTreeBuilder, common: Path, *, ttag: str) -> str:
    renderer = DirectoryRenderer(builder)
    tree_xml = "\n".join(renderer.tree_lines(include_metadata=False))
    return f'<{ttag} name="{common.name}" path="{common}">\n{tree_xml}\n</{ttag}>'


def _build_files_payload(builder: DirectoryTreeBuilder, common: Path, *, ftag: str) -> str:
    renderer = DirectoryRenderer(builder)
    files_xml = renderer.files_payload()
    return f'<{ftag} root="{common.name}">\n{files_xml}\n</{ftag}>'


MODE_HANDLERS: dict[OutputMode, Callable[[DirectoryTreeBuilder, Path, str, str], list[str]]] = {
    OutputMode.ALL: lambda b, c, ttag, ftag: [
        _build_tree_payload(b, c, ttag=ttag),
        _build_files_payload(b, c, ftag=ftag),
    ],
    OutputMode.TREE: lambda b, c, ttag, ftag: [_build_tree_payload(b, c, ttag=ttag)],  # noqa: ARG005
    OutputMode.FILES: lambda b, c, ttag, ftag: [_build_files_payload(b, c, ftag=ftag)],  # noqa: ARG005
    OutputMode.SUMMARY: lambda b, c, ttag, ftag: [],  # summary-only: no LLM payload  # noqa: ARG005
}


def build_llm_payload(
    *,
    builder: DirectoryTreeBuilder,
    common: Path,
    mode: OutputMode,
    tree_tag: str,
    file_tag: str,
) -> str:
    """Assemble the final LLM payload based on mode and tag names."""
    handler = MODE_HANDLERS.get(mode, MODE_HANDLERS[OutputMode.ALL])
    parts = handler(builder, common, tree_tag, file_tag)
    return "\n".join(parts)
