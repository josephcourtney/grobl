from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from pathspec import PathSpec

from grobl.directory import (
    DirectoryTreeBuilder,
    TraverseConfig,
    TreeCallback,
    traverse_dir,
)

pytestmark = pytest.mark.small

if TYPE_CHECKING:
    from pathlib import Path


def test_symlink_directories_are_not_followed(tmp_path: Path) -> None:
    base = tmp_path
    (base / "real").mkdir()
    (base / "real" / "child").mkdir()
    (base / "real" / "child" / "file.txt").write_text("hello", encoding="utf-8")

    # Create a symlink to the real directory
    (base / "link").symlink_to(base / "real", target_is_directory=True)

    builder = DirectoryTreeBuilder(base_path=base, exclude_patterns=[])

    def cb(item: Path, prefix: str, *, is_last: bool) -> None:
        if item.is_dir():
            builder.add_directory(item, prefix, is_last=is_last)
        else:
            builder.add_file_to_tree(item, prefix, is_last=is_last)

    config = TraverseConfig(paths=[base], patterns=[], base=base)
    traverse_dir(base, config, cb)
    # Expect both directories listed, but no recursion into the symlink
    names = "\n".join(builder.tree_output())
    assert "real" in names
    assert "link" in names
    # The nested child/file appear only under the real dir path
    # and should not be duplicated under the symlink
    assert names.count("child") == 1


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
    config = TraverseConfig(paths=[tmp_path], patterns=[], base=tmp_path)
    traverse_dir(tmp_path, config, callback)

    lines = builder.tree_output()
    directory_suffixes = {rel.name + "/" for kind, rel in builder.ordered_entries() if kind == "dir"}
    for suffix in directory_suffixes:
        assert any(line.endswith(suffix) for line in lines), f"missing trailing slash for {suffix}"


def test_traversal_order_and_exclude_patterns(tmp_path: Path) -> None:
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "dir" / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "dir" / "ignore.me").write_text("x", encoding="utf-8")

    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=["dir/ignore.*"])

    def cb(item: Path, prefix: str, *, is_last: bool) -> None:  # pragma: no cover - tiny callback
        if item.is_dir():
            builder.add_directory(item, prefix, is_last=is_last)
        else:
            builder.add_file_to_tree(item, prefix, is_last=is_last)

    config = TraverseConfig(paths=[tmp_path], patterns=builder.exclude_patterns, base=tmp_path)
    traverse_dir(tmp_path, config, cb)
    tree = builder.tree_output()
    # a.txt should come before b.txt; ignore.me excluded
    joined = "\n".join(tree)
    assert "a.txt" in joined
    assert "b.txt" in joined
    assert "ignore.me" not in joined
    assert joined.index("a.txt") < joined.index("b.txt")


def test_summary_totals_exposes_inclusion_and_totals(tmp_path: Path) -> None:
    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])

    include = tmp_path / "include.txt"
    include.write_text("a\nb\n", encoding="utf-8")

    skip = tmp_path / "skip.bin"
    skip.write_bytes(b"\x00\x01")

    rel_include = include.relative_to(tmp_path)
    rel_skip = skip.relative_to(tmp_path)

    builder.record_metadata(rel_include, lines=2, chars=4)
    builder.add_file(include, rel_include, lines=2, chars=4, content="a\nb\n")

    builder.record_metadata(rel_skip, lines=0, chars=2)

    snapshot = builder.summary_totals()
    assert snapshot.total_lines == 2
    assert snapshot.total_characters == 4
    assert snapshot.all_total_lines == 2
    assert snapshot.all_total_characters == 6

    include_stats = snapshot.for_path(rel_include)
    skip_stats = snapshot.for_path(rel_skip)
    assert include_stats is not None
    assert include_stats.included is True
    assert skip_stats is not None
    assert skip_stats.included is False
    assert snapshot.is_included(rel_include) is True
    assert snapshot.is_included(rel_skip) is False

    totals_dict = snapshot.to_dict()
    assert totals_dict == {
        "total_lines": 2,
        "total_characters": 4,
        "all_total_lines": 2,
        "all_total_characters": 6,
    }


def test_double_star_excludes_any_depth(tmp_path: Path) -> None:
    # a/b/ignore.me and c/ignore.me should be excluded by **/ignore.*
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "ignore.me").write_text("x", encoding="utf-8")
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / "ignore.me").write_text("y", encoding="utf-8")
    (tmp_path / "keep.txt").write_text("k", encoding="utf-8")

    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=["**/ignore.*"])

    def cb(item: Path, prefix: str, *, is_last: bool) -> None:  # pragma: no cover - small callback
        if item.is_dir():
            builder.add_directory(item, prefix, is_last=is_last)
        else:
            builder.add_file_to_tree(item, prefix, is_last=is_last)

    config = TraverseConfig(paths=[tmp_path], patterns=builder.exclude_patterns, base=tmp_path)
    traverse_dir(tmp_path, config, cb)
    out = "\n".join(builder.tree_output())
    assert "ignore.me" not in out
    assert "keep.txt" in out


def test_traverse_dir_accepts_precompiled_spec(tmp_path: Path) -> None:
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "keep.md").write_text("keep", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("nope", encoding="utf-8")

    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])

    def cb(item: Path, prefix: str, *, is_last: bool) -> None:  # pragma: no cover - simple callback
        if item.is_dir():
            builder.add_directory(item, prefix, is_last=is_last)
        else:
            builder.add_file_to_tree(item, prefix, is_last=is_last)

    spec = PathSpec.from_lines("gitwildmatch", ["ignored.txt"])
    config = TraverseConfig(paths=[tmp_path], patterns=[], base=tmp_path, spec=spec)
    traverse_dir(tmp_path, config, cb)
    out = "\n".join(builder.tree_output())
    assert "ignored.txt" not in out
    assert "keep.md" in out
