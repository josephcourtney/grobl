"""Tree rendering regression tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from grobl.directory import DirectoryTreeBuilder, TreeCallback, traverse_dir

if TYPE_CHECKING:
    from pathlib import Path


def test_directory_lines_include_trailing_slash(tmp_path: Path) -> None:
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "beta").mkdir()
    (tmp_path / "alpha" / "beta" / "leaf.txt").write_text("hello", encoding="utf-8")

    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])

    def collect(node: Path, prefix: str, *, is_last: bool) -> None:
        if node.is_dir():
            builder.add_directory(node, prefix, is_last=is_last)
        else:
            builder.add_file_to_tree(node, prefix, is_last=is_last)

    callback = cast("TreeCallback", collect)
    traverse_dir(tmp_path, ([tmp_path], [], tmp_path), callback)

    lines = builder.tree_output()
    directory_suffixes = {rel.name + "/" for kind, rel in builder.ordered_entries() if kind == "dir"}
    for suffix in directory_suffixes:
        assert any(line.endswith(suffix) for line in lines), f"missing trailing slash for {suffix}"
