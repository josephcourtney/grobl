from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grobl.app.scan_runtime import assemble_layered_ignores
from grobl.constants import InclusionLevel
from grobl.core import run_scan
from grobl.file_handling import ScanDependencies
from grobl.ignore import build_layered_ignores

if TYPE_CHECKING:
    from pathlib import Path

    from grobl.utils import TextDetectionResult


def _matcher(
    root: Path,
    *,
    exclude: tuple[str, ...] = (),
    tree_only: tuple[str, ...] = (),
    include: tuple[str, ...] = (),
):
    return build_layered_ignores(
        repo_root=root,
        include_defaults=False,
        runtime_exclude=exclude,
        runtime_tree_only=tree_only,
        runtime_include=include,
        default_cfg={},
    )


@pytest.mark.small
def test_three_states_have_expected_tree_and_content_projection(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"

    cases = (
        (InclusionLevel.OMIT, _matcher(tmp_path, exclude=("sample.txt",))),
        (InclusionLevel.TREE_ONLY, _matcher(tmp_path, tree_only=("sample.txt",))),
        (InclusionLevel.FULL, _matcher(tmp_path, include=("sample.txt",))),
    )
    for expected, matcher in cases:
        decision = matcher.explain_inclusion(target, is_dir=False)
        assert decision.level is expected
        assert matcher.explain_tree(target, is_dir=False).excluded is (expected is InclusionLevel.OMIT)
        assert matcher.explain_content(target, is_dir=False).excluded is (expected is not InclusionLevel.FULL)


@pytest.mark.medium
def test_tree_only_scan_does_not_read_or_detect_file(tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    target.write_text("do not read me", encoding="utf-8")

    def fail_detect(_path: Path) -> TextDetectionResult:
        msg = "TREE_ONLY file was text-detected"
        raise AssertionError(msg)

    def fail_read(_path: Path) -> str:
        msg = "TREE_ONLY file was read"
        raise AssertionError(msg)

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


@pytest.mark.medium
def test_omit_needs_no_duplicate_tree_only_rule(tmp_path: Path) -> None:
    target = tmp_path / "generated.txt"
    target.write_text("generated", encoding="utf-8")
    matcher = _matcher(tmp_path, exclude=("generated.txt",))

    result = run_scan(paths=[tmp_path], cfg={}, ignores=matcher)

    assert "generated.txt" not in "\n".join(result.builder.tree_output())
    assert "generated.txt" not in dict(result.builder.metadata_items())


@pytest.mark.medium
def test_deeper_config_can_restore_full_inclusion(tmp_path: Path) -> None:
    subtree = tmp_path / "generated"
    subtree.mkdir()
    target = subtree / "keep.txt"
    target.write_text("keep", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text('exclude = ["generated/**"]\n', encoding="utf-8")
    (subtree / ".grobl.toml").write_text('include = ["keep.txt"]\n', encoding="utf-8")

    from grobl.app.command_support import ScanParams
    from grobl.constants import ContentScope, PayloadFormat, SummaryFormat, TableStyle
    from grobl.metadata_visibility import DEFAULT_METADATA_VISIBILITY
    from grobl.resource_limits import UNLIMITED_RESOURCE_LIMITS

    params = ScanParams(
        paths=(subtree,),
        repo_root=tmp_path,
        config_path=None,
        scope=ContentScope.ALL,
        payload=PayloadFormat.NONE,
        summary=SummaryFormat.NONE,
        summary_style=TableStyle.AUTO,
        payload_copy=False,
        payload_output=None,
        visibility=DEFAULT_METADATA_VISIBILITY,
        limits=UNLIMITED_RESOURCE_LIMITS,
        pattern_base=tmp_path,
    )
    matcher = assemble_layered_ignores(
        repo_root=tmp_path,
        scan_paths=(subtree,),
        params=params,
        ignore_policy="config",
        inherit_defaults=False,
        ignore_defaults_flag=False,
        no_ignore_config_flag=False,
        no_ignore_flag=False,
    )

    decision = matcher.explain_inclusion(target, is_dir=False)
    assert decision.level is InclusionLevel.FULL
    assert decision.reason is not None
    assert decision.reason.config_path == (subtree / ".grobl.toml").resolve()
