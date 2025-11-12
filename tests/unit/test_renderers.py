from __future__ import annotations

from typing import TYPE_CHECKING

from grobl.directory import DirectoryTreeBuilder
from grobl.renderers import DirectoryRenderer

if TYPE_CHECKING:
    from pathlib import Path


def test_tree_lines_with_metadata_shows_columns_and_markers(tmp_path: Path) -> None:
    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    d = tmp_path / "sub"
    d.mkdir()
    f = tmp_path / "file.txt"
    f.write_text("hello\n", encoding="utf-8")

    # Build a small tree and metadata: one dir, one file (included)
    builder.add_directory(d, "", is_last=False)
    builder.add_file_to_tree(f, "", is_last=True)
    rel = f.relative_to(tmp_path)
    builder.add_file(f, rel, lines=1, chars=len("hello\n"), content="hello\n")

    renderer = DirectoryRenderer(builder)
    lines = renderer.tree_lines(include_metadata=True)
    # Header row present
    assert lines[0].strip().startswith("lines")
    # Base directory name on second row
    assert lines[1].endswith("/")
    # A file row with metadata columns and included marker (" " for included)
    text = "\n".join(lines)
    assert "file.txt" in text
    assert " 1 " in text  # line count column rendered


def test_files_payload_contains_file_content_block(tmp_path: Path) -> None:
    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    f = tmp_path / "doc.md"
    f.write_text("```code```", encoding="utf-8")
    rel = f.relative_to(tmp_path)
    # add_file applies Markdown fence escaping
    builder.add_file(f, rel, lines=1, chars=9, content=f.read_text("utf-8"))
    payload = DirectoryRenderer(builder).files_payload()
    assert '<file:content name="doc.md"' in payload
    assert r"\`\`\`" in payload  # escaped backticks
