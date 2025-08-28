from __future__ import annotations

from pathlib import Path

from grobl.core import run_scan
from grobl.directory import DirectoryTreeBuilder, traverse_dir
from grobl.utils import find_common_ancestor


def test_common_ancestor_config_base(tmp_path: Path) -> None:
    base = tmp_path / "proj"
    (base / "a").mkdir(parents=True)
    (base / "b").mkdir(parents=True)
    p1 = base / "a" / "x.txt"
    p2 = base / "b" / "y.txt"
    p1.write_text("one", encoding="utf-8")
    p2.write_text("two", encoding="utf-8")

    common = find_common_ancestor([p1, p2])
    assert common == base


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
    assert "a.txt" in joined and "b.txt" in joined
    assert "ignore.me" not in joined
    assert joined.index("a.txt") < joined.index("b.txt")


def test_file_collection_and_metadata(tmp_path: Path) -> None:
    # text file included; another text file excluded by exclude_print; one binary
    (tmp_path / "inc.txt").write_text("hello\nworld\n", encoding="utf-8")
    (tmp_path / "skip.txt").write_text("skip\n", encoding="utf-8")
    (tmp_path / "bin.dat").write_bytes(b"\x00\x01\x02\x03")

    cfg = {"exclude_tree": [], "exclude_print": ["skip.txt"]}
    res = run_scan(paths=[tmp_path], cfg=cfg)
    b = res.builder
    meta = dict(b.metadata_items())

    assert meta["inc.txt"][0] == 2 and meta["inc.txt"][2] is True
    assert meta["skip.txt"][2] is False
    assert meta["bin.dat"][0] == 0 and meta["bin.dat"][1] == 4

