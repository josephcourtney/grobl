from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from grobl.directory import DirectoryTreeBuilder, TreeCallback, traverse_dir

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

    traverse_dir(base, ([base], [], base), cb)
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
    traverse_dir(tmp_path, ([tmp_path], [], tmp_path), callback)

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

    traverse_dir(tmp_path, ([tmp_path], builder.exclude_patterns, tmp_path), cb)
    tree = builder.tree_output()
    # a.txt should come before b.txt; ignore.me excluded
    joined = "\n".join(tree)
    assert "a.txt" in joined
    assert "b.txt" in joined
    assert "ignore.me" not in joined
    assert joined.index("a.txt") < joined.index("b.txt")


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

    traverse_dir(tmp_path, ([tmp_path], builder.exclude_patterns, tmp_path), cb)
    out = "\n".join(builder.tree_output())
    assert "ignore.me" not in out
    assert "keep.txt" in out
