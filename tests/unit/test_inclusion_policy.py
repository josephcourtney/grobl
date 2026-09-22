from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grobl.app.command_support import ScanParams
from grobl.app.scan_runtime import assemble_layered_ignores
from grobl.constants import (
    ContentScope,
    InclusionLevel,
    PayloadFormat,
    SummaryFormat,
    TableStyle,
)
from grobl.core import run_scan
from grobl.file_handling import ScanDependencies
from grobl.ignore import InclusionLayer, InclusionRule, LayerSource, build_layered_ignores
from grobl.metadata_visibility import DEFAULT_METADATA_VISIBILITY
from grobl.resource_limits import UNLIMITED_RESOURCE_LIMITS

if TYPE_CHECKING:
    from collections.abc import Iterator
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


@pytest.mark.medium
def test_unrelated_reinclude_does_not_open_omitted_vendor_subtree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".gitmodules").write_text("root module\n", encoding="utf-8")
    source_dir = tmp_path / "third_party" / "vendor" / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "vendor.c").write_text("vendor implementation\n", encoding="utf-8")

    matcher = _matcher(
        tmp_path,
        exclude=("third_party/*/*",),
        include=("/.gitmodules",),
    )

    assert matcher.may_reinclude_descendant(source_dir) is False

    path_type = type(source_dir)
    original_iterdir = path_type.iterdir

    def guarded_iterdir(path: Path) -> Iterator[Path]:
        if path == source_dir:
            msg = "unrelated omitted subtree should have been pruned"
            raise AssertionError(msg)
        return original_iterdir(path)

    monkeypatch.setattr(path_type, "iterdir", guarded_iterdir)

    result = run_scan(paths=[tmp_path], cfg={}, ignores=matcher)
    tree = "\n".join(result.builder.tree_output())

    assert ".gitmodules" in tree
    assert "vendor.c" not in tree


@pytest.mark.medium
def test_targeted_reinclude_descends_only_far_enough_to_restore_target(tmp_path: Path) -> None:
    private = tmp_path / "generated" / "private"
    private.mkdir(parents=True)
    keep = private / "keep.txt"
    drop = private / "drop.txt"
    keep.write_text("keep\n", encoding="utf-8")
    drop.write_text("drop\n", encoding="utf-8")

    matcher = _matcher(
        tmp_path,
        exclude=("generated/*",),
        include=("generated/private/keep.txt",),
    )

    assert matcher.may_reinclude_descendant(private) is True

    result = run_scan(paths=[tmp_path], cfg={}, ignores=matcher)
    tree = "\n".join(result.builder.tree_output())

    assert "keep.txt" in tree
    assert "drop.txt" not in tree
    metadata = dict(result.builder.metadata_items())
    assert metadata["generated/private/keep.txt"].included is True
    assert "generated/private/drop.txt" not in metadata


@pytest.mark.medium
def test_unanchored_basename_reinclude_remains_conservative_without_leaking(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "third_party" / "vendor" / "src"
    source_dir.mkdir(parents=True)
    (source_dir / ".gitmodules").write_text("nested module\n", encoding="utf-8")
    (source_dir / "vendor.c").write_text("vendor implementation\n", encoding="utf-8")

    matcher = _matcher(
        tmp_path,
        exclude=("third_party/*/*",),
        include=(".gitmodules",),
    )

    # Gitignore-style basename patterns can match at any depth, so Grobl cannot
    # prove that an arbitrary subtree is irrelevant to this restoration.
    assert matcher.may_reinclude_descendant(source_dir) is True

    result = run_scan(paths=[tmp_path], cfg={}, ignores=matcher)
    tree = "\n".join(result.builder.tree_output())

    assert ".gitmodules" in tree
    assert "vendor.c" not in tree


@pytest.mark.medium
def test_reinclude_layer_below_omitted_directory_keeps_ancestor_traversable(
    tmp_path: Path,
) -> None:
    omitted = tmp_path / "generated"
    deeper = omitted / "special"
    deeper.mkdir(parents=True)
    keep = deeper / "keep.txt"
    drop = deeper / "drop.txt"
    keep.write_text("keep\n", encoding="utf-8")
    drop.write_text("drop\n", encoding="utf-8")

    matcher = build_layered_ignores(
        repo_root=tmp_path,
        include_defaults=False,
        default_cfg={},
        config_layers=(
            InclusionLayer(
                base_dir=tmp_path,
                rules=(
                    InclusionRule(
                        pattern="generated",
                        level=InclusionLevel.OMIT,
                    ),
                ),
                source=LayerSource.CONFIG,
                config_path=tmp_path / ".grobl.toml",
            ),
            InclusionLayer(
                base_dir=deeper,
                rules=(
                    InclusionRule(
                        pattern="keep.txt",
                        level=InclusionLevel.FULL,
                    ),
                ),
                source=LayerSource.CONFIG,
                config_path=deeper / ".grobl.toml",
            ),
        ),
    )

    assert matcher.may_reinclude_descendant(omitted) is True

    result = run_scan(paths=[tmp_path], cfg={}, ignores=matcher)
    tree = "\n".join(result.builder.tree_output())

    assert "keep.txt" in tree
    assert "drop.txt" not in tree
