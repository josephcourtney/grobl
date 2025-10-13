from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grobl.core import run_scan
from grobl.directory import DirectoryTreeBuilder, traverse_dir
from grobl.file_handling import (
    BinaryFileHandler,
    FileAnalysis,
    FileHandlerRegistry,
    FileProcessingContext,
    ScanDependencies,
)
from grobl.utils import find_common_ancestor

if TYPE_CHECKING:
    from pathlib import Path


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
    assert "a.txt" in joined
    assert "b.txt" in joined
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

    assert meta["inc.txt"][0] == 2
    assert meta["inc.txt"][2] is True
    assert meta["skip.txt"][2] is False
    assert meta["bin.dat"][0] == 0
    assert meta["bin.dat"][1] == 4


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


def test_exclude_print_with_gitignore_semantics(tmp_path: Path) -> None:
    # ensure **/*.md prevents content from being included
    (tmp_path / "notes").mkdir()
    md = tmp_path / "notes" / "readme.md"
    md.write_text("# hi\n", encoding="utf-8")
    txt = tmp_path / "notes" / "keep.txt"
    txt.write_text("ok\n", encoding="utf-8")

    from grobl.core import run_scan

    cfg = {"exclude_tree": [], "exclude_print": ["**/*.md"]}
    res = run_scan(paths=[tmp_path], cfg=cfg)
    # The .md file should have included=False in metadata
    meta = dict(res.builder.metadata_items())
    assert meta["notes/readme.md"][2] is False
    assert meta["notes/keep.txt"][2] is True


def test_run_scan_accepts_injected_dependencies(tmp_path: Path) -> None:
    sample = tmp_path / "note.txt"
    sample.write_text("ignored", encoding="utf-8")

    reads: list[Path] = []

    def fake_read(path: Path) -> str:
        reads.append(path)
        return "hello"

    deps = ScanDependencies(
        text_detector=lambda _path: True,
        text_reader=fake_read,
        binary_probe=lambda _path: {"size_bytes": 0},
    )

    res = run_scan(paths=[tmp_path], cfg={}, dependencies=deps)
    assert reads == [sample]
    meta = dict(res.builder.metadata_items())
    assert meta["note.txt"][0] == 1


def test_run_scan_handles_single_file_path(tmp_path: Path) -> None:
    target = tmp_path / "solo.txt"
    target.write_text("line1\nline2\n", encoding="utf-8")

    res = run_scan(paths=[target], cfg={})

    assert res.common == tmp_path
    tree = res.builder.tree_output()
    assert any("solo.txt" in line for line in tree)
    meta = dict(res.builder.metadata_items())
    assert "solo.txt" in meta
    lines, _, included = meta["solo.txt"]
    assert lines == 2
    assert included is True


def test_run_scan_can_be_extended_with_custom_handler(tmp_path: Path) -> None:
    binary = tmp_path / "blob.bin"
    binary.write_bytes(b"abc")

    class ZeroHandler(BinaryFileHandler):
        def supports(self, *, path: Path, is_text_file: bool) -> bool:
            return path.suffix == ".bin"

        def _analyse(
            self,
            *,
            path: Path,
            context: FileProcessingContext,
            is_text_file: bool,
        ) -> FileAnalysis:
            return FileAnalysis(lines=0, chars=0, include_content=False, binary_details={"size_bytes": 0})

    handlers = FileHandlerRegistry.default().extend((ZeroHandler(),))
    res = run_scan(paths=[tmp_path], cfg={}, handlers=handlers)
    meta = dict(res.builder.metadata_items())
    assert meta["blob.bin"][1] == 0


def test_run_scan_rejects_missing_paths(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(ValueError, match="scan paths do not exist"):
        run_scan(paths=[missing], cfg={})
