from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from grobl.config import load_default_config
from grobl.constants import ContentScope
from grobl.core import run_scan
from grobl.directory import DirectoryTreeBuilder
from grobl.renderers import (
    DirectoryRenderer,
    build_llm_payload,
    build_markdown_payload,
    build_markdown_snapshot,
    format_begin_file_header,
)
from tests.support import build_ignore_matcher

pytestmark = pytest.mark.small

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


def test_tree_and_markdown_views_fall_back_to_plain_tree_on_invariant_break(tmp_path: Path) -> None:
    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    d = tmp_path / "pkg"
    d.mkdir()
    f = tmp_path / "pkg" / "module.py"
    f.write_text("print('hi')\n", encoding="utf-8")

    builder.add_directory(d, "", is_last=False)
    builder.add_file_to_tree(f, "pkg", is_last=True)
    builder.add_file(
        f,
        f.relative_to(tmp_path),
        lines=1,
        chars=len("print('hi')\n"),
        content="print('hi')\n",
    )

    raw_tree = builder.tree_output()

    # Break the ordering invariant to simulate a partially collected tree.
    builder.tree._ordered.pop()  # type: ignore[attr-defined]

    renderer = DirectoryRenderer(builder)
    expected = [f"{tmp_path.name}/", *raw_tree]

    assert renderer.tree_lines(include_metadata=True) == expected
    assert renderer.tree_lines_for_markdown() == expected


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


def test_build_llm_payload_respects_scope(tmp_path: Path) -> None:
    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    subdir = tmp_path / "pkg"
    subdir.mkdir()
    builder.add_directory(subdir, "", is_last=False)
    file_path = tmp_path / "pkg" / "module.py"
    file_path.write_text("print('hi')\n", encoding="utf-8")
    builder.add_file_to_tree(file_path, "pkg", is_last=True)
    builder.add_file(
        file_path,
        file_path.relative_to(tmp_path),
        lines=1,
        chars=len("print('hi')\n"),
        content="print('hi')\n",
    )

    payload_all = build_llm_payload(
        builder=builder,
        common=tmp_path,
        scope=ContentScope.ALL,
        tree_tag="directory",
        file_tag="file",
    )
    assert "<directory" in payload_all
    assert "<file" in payload_all

    payload_tree = build_llm_payload(
        builder=builder,
        common=tmp_path,
        scope=ContentScope.TREE,
        tree_tag="directory",
        file_tag="file",
    )
    assert "<directory" in payload_tree
    assert "<file" not in payload_tree

    payload_files = build_llm_payload(
        builder=builder,
        common=tmp_path,
        scope=ContentScope.FILES,
        tree_tag="directory",
        file_tag="file",
    )
    assert "<directory" not in payload_files
    assert "<file" in payload_files


def _extract_tree_section(markdown: str) -> list[str]:
    start_marker = "```tree"
    end_marker = "```"

    start = markdown.index(start_marker) + len(start_marker)
    # skip the newline immediately after the ```tree fence
    if markdown[start : start + 1] == "\n":
        start += 1
    end = markdown.index(end_marker, start)
    body = markdown[start:end]
    return body.splitlines()


def _extract_begin_file_lines(markdown: str) -> list[str]:
    return [line for line in markdown.splitlines() if line.startswith("%%%% BEGIN_FILE ")]


def test_markdown_tree_includes_inclusion_annotations(tmp_path: Path) -> None:  # noqa: PLR0914
    root = tmp_path / "proj"
    root.mkdir()

    (root / "1.txt").write_text("one\n", encoding="utf-8")

    a = root / "a"
    a.mkdir()
    (a / "2.txt").write_text("two\n", encoding="utf-8")

    d = a / "d"
    d.mkdir()
    (d / "3.txt").write_text("three\n", encoding="utf-8")

    b = root / "b"
    b.mkdir()
    (b / "skip.txt").write_text("skip\n", encoding="utf-8")

    c = root / "c"
    c.mkdir()
    (c / "4.txt").write_text("four\n", encoding="utf-8")

    cfg = load_default_config()
    # Ensure that files under 'b/' are present in the tree but have no contents
    # captured in the payload.
    exclude_print = list(cfg.get("exclude_print", []))
    exclude_print.append("b/**")
    cfg["exclude_print"] = exclude_print

    ignores = build_ignore_matcher(
        repo_root=root,
        scan_paths=[root],
        tree_patterns=cfg.get("exclude_tree", []),
        print_patterns=cfg.get("exclude_print", []),
    )
    result = run_scan(paths=[root], cfg=cfg, ignores=ignores)
    markdown = build_markdown_payload(builder=result.builder, common=result.common, scope=ContentScope.ALL)

    tree_lines = _extract_tree_section(markdown)

    # Root line
    assert tree_lines[0] == "proj/"

    line_1 = next(line for line in tree_lines if "1.txt" in line)
    line_2 = next(line for line in tree_lines if "2.txt" in line)
    line_3 = next(line for line in tree_lines if "3.txt" in line)
    line_4 = next(line for line in tree_lines if "4.txt" in line)
    line_b_dir = next(line for line in tree_lines if "b/" in line)
    line_b_file = next(line for line in tree_lines if "skip.txt" in line)

    assert "[INCLUDED:FULL]" in line_1
    assert "[INCLUDED:FULL]" in line_2
    assert "[INCLUDED:FULL]" in line_3
    assert "[INCLUDED:FULL]" in line_4

    # Files and the directory whose subtree is entirely excluded from printing
    # should be marked as not included.
    assert "[NOT_INCLUDED]" in line_b_dir
    assert "[NOT_INCLUDED]" in line_b_file


def test_markdown_snapshot_schema_separates_tree_and_files(tmp_path: Path) -> None:
    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    subdir = tmp_path / "pkg"
    subdir.mkdir()
    builder.add_directory(subdir, "", is_last=False)

    file_path = tmp_path / "pkg" / "module.py"
    file_path.write_text("print('hi')\n", encoding="utf-8")
    rel = file_path.relative_to(tmp_path)
    builder.add_file_to_tree(file_path, "pkg", is_last=True)
    builder.add_file(file_path, rel, lines=1, chars=len("print('hi')\n"), content="print('hi')\n")

    snapshot = build_markdown_snapshot(builder=builder, scope=ContentScope.ALL)

    assert snapshot.tree_lines == DirectoryRenderer(builder).tree_lines_for_markdown()
    assert len(snapshot.files) == 1
    entry = snapshot.files[0]
    assert entry.path == "pkg/module.py"
    assert entry.language == "python"
    assert entry.start_line == 1
    assert entry.end_line == 1
    assert entry.chars == len("print('hi')\n")
    assert entry.content == "print('hi')\n"


def test_markdown_payload_uses_formatted_header_once(tmp_path: Path) -> None:
    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    file_path = tmp_path / "app.py"
    file_path.write_text("print('ok')\n", encoding="utf-8")
    rel = file_path.relative_to(tmp_path)
    builder.add_file_to_tree(file_path, "", is_last=True)
    builder.add_file(file_path, rel, lines=1, chars=len("print('ok')\n"), content="print('ok')\n")

    snapshot = build_markdown_snapshot(builder=builder, scope=ContentScope.FILES)
    expected_header = format_begin_file_header(snapshot.files[0])

    markdown = build_markdown_payload(builder=builder, common=tmp_path, scope=ContentScope.FILES)
    lines = markdown.splitlines()

    headers = [line for line in lines if line.startswith("%%%% BEGIN_FILE ")]
    assert headers == [expected_header]

    files_headers = [line for line in lines if line == "## Files"]
    assert files_headers == ["## Files"]


def test_markdown_metadata_omits_obvious_fields(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()

    script = root / "script.py"
    script.write_text('print("hi")\n', encoding="utf-8")

    unknown = root / "data.custom"
    unknown.write_text("payload\n", encoding="utf-8")

    cfg = load_default_config()
    ignores = build_ignore_matcher(
        repo_root=root,
        scan_paths=[root],
        tree_patterns=cfg.get("exclude_tree", []),
        print_patterns=cfg.get("exclude_print", []),
    )
    result = run_scan(paths=[root], cfg=cfg, ignores=ignores)
    markdown = build_markdown_payload(builder=result.builder, common=result.common, scope=ContentScope.ALL)

    header_lines = _extract_begin_file_lines(markdown)

    script_header = next(line for line in header_lines if 'path="script.py"' in line)
    unknown_header = next(line for line in header_lines if 'path="data.custom"' in line)

    # path, language, lines, chars should all be present for recognised languages.
    assert 'path="script.py"' in script_header
    assert 'language="python"' in script_header
    assert 'lines="' in script_header
    assert 'chars="' in script_header
    # Default kind="full" should not be emitted.
    assert 'kind="full"' not in script_header

    # For unknown extensions, omit language altogether.
    assert 'path="data.custom"' in unknown_header
    assert "language=" not in unknown_header
    assert 'lines="' in unknown_header
    assert 'chars="' in unknown_header


def test_markdown_trims_trailing_newlines_in_code_blocks(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()

    script = root / "script.py"
    # Trailing newline is common in source files; it should not produce an extra
    # blank line before the closing fence.
    script.write_text('print("hi")\n', encoding="utf-8")

    cfg = load_default_config()
    ignores = build_ignore_matcher(
        repo_root=root,
        scan_paths=[root],
        tree_patterns=cfg.get("exclude_tree", []),
        print_patterns=cfg.get("exclude_print", []),
    )
    result = run_scan(paths=[root], cfg=cfg, ignores=ignores)
    markdown = build_markdown_payload(builder=result.builder, common=result.common, scope=ContentScope.ALL)

    lines = markdown.splitlines()
    fence_idx = next(i for i, line in enumerate(lines) if line.startswith("```python"))

    # Expect the pattern:
    # ```python
    # print("hi")
    # ```
    assert lines[fence_idx + 1] == 'print("hi")'
    assert lines[fence_idx + 2] == "```"


def test_llm_payload_keeps_raw_xml_like_content(tmp_path: Path) -> None:
    root = tmp_path / "proj&<>"
    root.mkdir()

    special = root / 'strange "name"&.txt'
    special.write_text("<file:content> & closing </file:content>", encoding="utf-8")

    builder = DirectoryTreeBuilder(base_path=root, exclude_patterns=[])
    builder.add_file_to_tree(special, "", is_last=True)
    builder.add_file(
        special,
        special.relative_to(root),
        lines=1,
        chars=len("<file:content> & closing </file:content>"),
        content=special.read_text(encoding="utf-8"),
    )

    payload = build_llm_payload(
        builder=builder,
        common=root,
        scope=ContentScope.ALL,
        tree_tag="tree",
        file_tag="files",
    )

    assert 'name="proj&<>"' in payload
    assert f'path="{root}"' in payload
    assert "<file:content name='strange \"name\"&.txt'" in payload
    assert "<file:content> & closing </file:content>" in payload


def test_markdown_headers_escape_metadata(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()

    special = root / 'unsafe "name"% &.py'
    special.write_text('print("hi")\n', encoding="utf-8")

    builder = DirectoryTreeBuilder(base_path=root, exclude_patterns=[])
    builder.add_file_to_tree(special, "", is_last=True)
    builder.add_file(
        special,
        special.relative_to(root),
        lines=1,
        chars=len('print("hi")\n'),
        content=special.read_text(encoding="utf-8"),
    )

    markdown = build_markdown_payload(builder=builder, common=root, scope=ContentScope.ALL)
    header = next(line for line in markdown.splitlines() if line.startswith("%%%% BEGIN_FILE "))

    assert 'path="unsafe &quot;name&quot;%25 &amp;.py"' in header
    assert 'language="python"' in header
    assert '%"' not in header
