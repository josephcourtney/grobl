from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grobl.constants import InclusionLevel
from grobl.core import run_scan
from grobl.file_handling import ScanDependencies
from grobl.ignore import build_layered_ignores
from grobl.utils import TextDetectionResult

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.small


def _matcher(
    root: Path,
    *,
    exclude: tuple[str, ...] = (),
    tree_only: tuple[str, ...] = (),
    include: tuple[str, ...] = (),
):
    return build_layered_ignores(
        repo_root=root,
        scan_paths=[root],
        include_defaults=False,
        include_config=False,
        runtime_exclude=exclude,
        runtime_tree_only=tree_only,
        runtime_include=include,
        default_cfg={},
    )


def test_three_states_have_expected_tree_and_content_projection(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("sample", encoding="utf-8")

    cases = (
        (InclusionLevel.OMIT, _matcher(tmp_path, exclude=("sample.txt",))),
        (InclusionLevel.TREE_ONLY, _matcher(tmp_path, tree_only=("sample.txt",))),
        (InclusionLevel.FULL, _matcher(tmp_path, include=("sample.txt",))),
    )
    for expected, matcher in cases:
        decision = matcher.explain_inclusion(target, is_dir=False)
        assert decision.level is expected
        assert matcher.explain_tree(target, is_dir=False).excluded is (
            expected is InclusionLevel.OMIT
        )
        assert matcher.explain_content(target, is_dir=False).excluded is (
            expected is not InclusionLevel.FULL
        )


def test_tree_only_scan_does_not_read_or_detect_file(tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    target.write_text("do not read me", encoding="utf-8")

    def fail_detect(_path: Path) -> TextDetectionResult:
        raise AssertionError("TREE_ONLY file was text-detected")

    def fail_read(_path: Path) -> str:
        raise AssertionError("TREE_ONLY file was read")

    matcher = _matcher(tmp_path, tree_only=("secret.txt",))
    result = run_scan(
        paths=[tmp_path],
        cfg={},
        ignores=matcher,
        dependencies=ScanDependencies(text_detector=fail_detect, text_reader=fail_read),
    )

    assert "secret.txt" in "\n".join(result.builder.tree_output())
    assert result.builder.files_json() == []
    summary = dict(result.builder.metadata_items())["secret.txt"]
    assert summary.included is False
    assert summary.content_reason is not None
    assert summary.content_reason["state"] == "tree_only"


def test_omit_needs_no_duplicate_tree_only_rule(tmp_path: Path) -> None:
    target = tmp_path / "generated.txt"
    target.write_text("generated", encoding="utf-8")
    matcher = _matcher(tmp_path, exclude=("generated.txt",))

    result = run_scan(paths=[tmp_path], cfg={}, ignores=matcher)

    assert "generated.txt" not in "\n".join(result.builder.tree_output())
    assert "generated.txt" not in dict(result.builder.metadata_items())


def test_deeper_config_can_restore_full_inclusion(tmp_path: Path) -> None:
    subtree = tmp_path / "generated"
    subtree.mkdir()
    target = subtree / "keep.txt"
    target.write_text("keep", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        'exclude = ["generated/**"]\n', encoding="utf-8"
    )
    (subtree / ".grobl.toml").write_text(
        'include = ["keep.txt"]\n', encoding="utf-8"
    )

    matcher = build_layered_ignores(
        repo_root=tmp_path,
        scan_paths=[subtree],
        include_defaults=False,
        include_config=True,
        default_cfg={},
    )

    decision = matcher.explain_inclusion(target, is_dir=False)
    assert decision.level is InclusionLevel.FULL
    assert decision.reason is not None
    assert decision.reason.config_path == (subtree / ".grobl.toml").resolve()
