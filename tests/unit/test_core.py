from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from grobl.config_runtime import apply_runtime_ignore_edits
from grobl.core import run_scan
from grobl.errors import PathNotFoundError
from grobl.file_handling import (
    BaseFileHandler,
    FileAnalysis,
    FileHandlerRegistry,
    FileProcessingContext,
    ScanDependencies,
)
from grobl.resource_limits import ResourceLimits
from grobl.token_counting import count_tokens
from grobl.utils import TextDetectionResult
from tests.support import build_ignore_matcher

pytestmark = pytest.mark.medium

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def _make_ignores(paths: Sequence[Path], *, repo_root: Path, cfg: dict[str, object] | None = None):
    tree_patterns = tuple(cast("Sequence[str]", cfg.get("exclude_tree", ()))) if cfg else ()
    print_patterns = tuple(cast("Sequence[str]", cfg.get("exclude_print", ()))) if cfg else ()
    return build_ignore_matcher(
        repo_root=repo_root,
        scan_paths=list(paths),
        tree_patterns=tree_patterns,
        print_patterns=print_patterns,
    )


def test_file_collection_and_metadata(tmp_path: Path) -> None:
    # text file included; another text file excluded by exclude_print; one binary
    (tmp_path / "inc.txt").write_text("hello\nworld\n", encoding="utf-8")
    (tmp_path / "skip.txt").write_text("skip\n", encoding="utf-8")
    (tmp_path / "bin.dat").write_bytes(b"\x00\x01\x02\x03")

    cfg: dict[str, object] = {"exclude_tree": [], "exclude_print": ["skip.txt"]}
    ignores = _make_ignores([tmp_path], repo_root=tmp_path, cfg=cfg)
    res = run_scan(paths=[tmp_path], cfg=cfg, ignores=ignores)
    b = res.builder
    meta = dict(b.metadata_items())

    inc_summary = meta["inc.txt"]
    assert inc_summary.lines == 2
    assert inc_summary.tokens == count_tokens("hello\nworld\n")
    assert inc_summary.included is True
    skip_summary = meta["skip.txt"]
    assert skip_summary.included is False
    bin_summary = meta["bin.dat"]
    assert bin_summary.lines == 0
    assert bin_summary.chars == 4
    assert bin_summary.content_reason is not None
    assert bin_summary.content_reason["pattern"] == "<non-text>"


def test_exclude_print_with_gitignore_semantics(tmp_path: Path) -> None:
    # ensure **/*.md prevents content from being included
    (tmp_path / "notes").mkdir()
    md = tmp_path / "notes" / "readme.md"
    md.write_text("# hi\n", encoding="utf-8")
    txt = tmp_path / "notes" / "keep.txt"
    txt.write_text("ok\n", encoding="utf-8")

    from grobl.core import run_scan

    cfg: dict[str, object] = {"exclude_tree": [], "exclude_print": ["**/*.md"]}
    ignores = _make_ignores([tmp_path], repo_root=tmp_path, cfg=cfg)
    res = run_scan(paths=[tmp_path], cfg=cfg, ignores=ignores)
    # The .md file should have included=False in metadata
    meta = dict(res.builder.metadata_items())
    assert meta["notes/readme.md"].included is False
    assert meta["notes/keep.txt"].included is True


def test_run_scan_handles_single_file_path(tmp_path: Path) -> None:
    target = tmp_path / "solo.txt"
    target.write_text("line1\nline2\n", encoding="utf-8")

    ignores = _make_ignores([target], repo_root=tmp_path)
    res = run_scan(paths=[target], cfg={}, ignores=ignores)

    assert res.common == tmp_path
    tree = res.builder.tree_output()
    assert any("solo.txt" in line for line in tree)
    meta = dict(res.builder.metadata_items())
    assert "solo.txt" in meta
    solo_summary = meta["solo.txt"]
    assert solo_summary.lines == 2
    assert solo_summary.tokens == count_tokens("line1\nline2\n")
    assert solo_summary.included is True


def test_run_scan_uses_match_base_for_gitignore_anchors(tmp_path: Path) -> None:
    (tmp_path / "root_only.txt").write_text("root\n", encoding="utf-8")
    (tmp_path / "foo" / "a").mkdir(parents=True)
    (tmp_path / "foo" / "a" / "bar.txt").write_text("blocked\n", encoding="utf-8")
    (tmp_path / "foo" / "root_only.txt").write_text("keep\n", encoding="utf-8")
    (tmp_path / "foo" / "keep.txt").write_text("ok\n", encoding="utf-8")

    cfg: dict[str, object] = {"exclude_tree": ["/root_only.txt", "foo/**/bar.txt"], "exclude_print": []}
    path_list = [tmp_path / "foo"]
    ignores = _make_ignores(path_list, repo_root=tmp_path, cfg=cfg)
    res = run_scan(paths=path_list, cfg=cfg, match_base=tmp_path, ignores=ignores)
    tree = "\n".join(res.builder.tree_output())

    assert "bar.txt" not in tree
    assert "keep.txt" in tree
    assert "root_only.txt" in tree


def test_run_scan_rejects_missing_paths(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(PathNotFoundError, match="scan path not found"):
        run_scan(
            paths=[missing],
            cfg={},
            ignores=_make_ignores([missing], repo_root=tmp_path),
        )


def test_unignore_allows_specific_paths(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("*\n", encoding="utf-8")
    (tmp_path / "tests" / "fixtures").mkdir(parents=True)
    nested = tmp_path / "tests" / "fixtures" / ".gitignore"
    nested.write_text("nested\n", encoding="utf-8")

    base_cfg: dict[str, object] = {"exclude_tree": [".gitignore"], "exclude_print": []}
    edits = apply_runtime_ignore_edits(
        base_tree=list(base_cfg["exclude_tree"]),
        base_print=list(base_cfg["exclude_print"]),
        add_ignore=(),
        remove_ignore=(),
        add_ignore_files=(),
        unignore=("tests/fixtures/**/.gitignore",),
        no_ignore=False,
    )
    cfg: dict[str, object] = {"exclude_tree": edits.tree_patterns, "exclude_print": edits.print_patterns}
    ignores = _make_ignores([tmp_path], repo_root=tmp_path, cfg=cfg)
    res = run_scan(paths=[tmp_path], cfg=cfg, match_base=tmp_path, ignores=ignores)
    tree = "\n".join(res.builder.tree_output())
    assert tree.count(".gitignore") == 1


def test_run_scan_accepts_injected_dependencies(tmp_path: Path) -> None:
    sample = tmp_path / "note.txt"
    sample.write_text("ignored", encoding="utf-8")

    reads: list[Path] = []

    def fake_read(path: Path) -> str:
        reads.append(path)
        return "hello"

    def fake_detect(path: Path) -> TextDetectionResult:
        return TextDetectionResult(is_text=True, content=fake_read(path))

    deps = ScanDependencies(
        text_detector=fake_detect,
        text_reader=fake_read,
    )

    ignores = _make_ignores([tmp_path], repo_root=tmp_path)
    res = run_scan(paths=[tmp_path], cfg={}, dependencies=deps, ignores=ignores)
    assert reads == [sample]
    meta = dict(res.builder.metadata_items())
    assert meta["note.txt"].lines == 1
    assert meta["note.txt"].tokens == count_tokens("hello")


def test_run_scan_can_be_extended_with_custom_handler(tmp_path: Path) -> None:
    binary = tmp_path / "blob.bin"
    binary.write_bytes(b"abc")

    class ZeroHandler(BaseFileHandler):
        def supports(self, *, path: Path, is_text_file: bool) -> bool:
            return path.suffix == ".bin"

        def _analyze(
            self,
            *,
            path: Path,
            context: FileProcessingContext,
            is_text_file: bool,
            detection: TextDetectionResult,
        ) -> FileAnalysis:
            return FileAnalysis(lines=0, chars=0, tokens=0, include_content=False)

    handlers = FileHandlerRegistry.default().extend((ZeroHandler(),))
    ignores = _make_ignores([tmp_path], repo_root=tmp_path)
    res = run_scan(paths=[tmp_path], cfg={}, handlers=handlers, ignores=ignores)
    meta = dict(res.builder.metadata_items())
    assert meta["blob.bin"].chars == 0


def test_max_file_bytes_omits_before_text_detection(tmp_path: Path) -> None:
    target = tmp_path / "large.txt"
    target.write_text("0123456789", encoding="utf-8")
    ignores = _make_ignores([tmp_path], repo_root=tmp_path)

    def detector(_path: Path) -> TextDetectionResult:
        raise AssertionError("oversized file should not be read")

    result = run_scan(
        paths=[tmp_path],
        cfg={},
        ignores=ignores,
        dependencies=ScanDependencies(
            text_detector=detector,
            text_reader=lambda _path: "",
        ),
        limits=ResourceLimits(max_file_bytes=5),
    )

    record = dict(result.builder.metadata_items())["large.txt"]
    assert record.included is False
    assert record.content_reason is not None
    assert record.content_reason["source"] == "resource-limit"
    assert "max_file_bytes exceeded" in str(record.content_reason["detail"])


def test_max_total_bytes_omits_later_files_deterministically(tmp_path: Path) -> None:
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    first.write_text("aaaa", encoding="utf-8")
    second.write_text("bbbb", encoding="utf-8")
    ignores = _make_ignores([tmp_path], repo_root=tmp_path)

    result = run_scan(
        paths=[tmp_path],
        cfg={},
        ignores=ignores,
        limits=ResourceLimits(max_total_bytes=4),
    )

    metadata = dict(result.builder.metadata_items())
    assert metadata["a.txt"].included is True
    assert metadata["b.txt"].included is False
    assert metadata["b.txt"].content_reason is not None
    assert metadata["b.txt"].content_reason["source"] == "resource-limit"
    assert "max_total_bytes exceeded" in str(metadata["b.txt"].content_reason["detail"])


def test_max_tokens_omits_file_that_would_exceed_remaining_budget(tmp_path: Path) -> None:
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    first.write_text("alpha\n", encoding="utf-8")
    second.write_text("beta\n", encoding="utf-8")
    ignores = _make_ignores([tmp_path], repo_root=tmp_path)

    result = run_scan(
        paths=[tmp_path],
        cfg={},
        ignores=ignores,
        limits=ResourceLimits(max_tokens=count_tokens("alpha\n")),
    )

    metadata = dict(result.builder.metadata_items())
    assert metadata["a.txt"].included is True
    assert metadata["b.txt"].included is False
    assert metadata["b.txt"].content_reason is not None
    assert metadata["b.txt"].content_reason["source"] == "resource-limit"
    assert "max_tokens exceeded" in str(metadata["b.txt"].content_reason["detail"])
