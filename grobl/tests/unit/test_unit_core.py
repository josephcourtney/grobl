from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from grobl.core import run_scan
from grobl.file_handling import ScanDependencies

import grobl

if TYPE_CHECKING:
    from pathlib import Path


def test_package_importable() -> None:
    assert grobl is not None


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
    assert meta["bin.dat"][1] == -1


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


def test_run_scan_rejects_missing_paths(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(ValueError, match="scan paths do not exist"):
        run_scan(paths=[missing], cfg={})
