from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grobl.constants import InclusionLevel
from grobl.ignore import LayeredIgnoreMatcher, LayerSource, build_layered_ignores

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.medium


def _matcher(
    *,
    repo_root: Path,
    exclude: tuple[str, ...] = (),
    tree_only: tuple[str, ...] = (),
    include: tuple[str, ...] = (),
    tree_patterns: tuple[str, ...] = (),
    print_patterns: tuple[str, ...] = (),
) -> LayeredIgnoreMatcher:
    return build_layered_ignores(
        repo_root=repo_root,
        scan_paths=[repo_root],
        include_defaults=False,
        include_config=False,
        runtime_exclude=exclude,
        runtime_tree_only=tree_only,
        runtime_include=include,
        runtime_tree_patterns=tree_patterns,
        runtime_print_patterns=print_patterns,
        default_cfg={},
    )


@pytest.mark.parametrize(
    ("patterns_name", "expected"),
    [
        ("exclude", InclusionLevel.OMIT),
        ("tree_only", InclusionLevel.TREE_ONLY),
        ("include", InclusionLevel.FULL),
    ],
)
def test_runtime_rules_assign_one_inclusion_state(
    tmp_path: Path, patterns_name: str, expected: InclusionLevel
) -> None:
    target = tmp_path / "notes.md"
    target.write_text("doc", encoding="utf-8")
    kwargs = {patterns_name: ("notes.md",)}
    matcher = _matcher(repo_root=tmp_path, **kwargs)

    decision = matcher.explain_inclusion(target, is_dir=False)

    assert decision.level is expected
    assert decision.reason is not None
    assert decision.reason.source is LayerSource.CLI_RUNTIME


def test_include_supersedes_less_inclusive_runtime_states(tmp_path: Path) -> None:
    target = tmp_path / "keep.txt"
    target.write_text("ok", encoding="utf-8")
    matcher = _matcher(
        repo_root=tmp_path,
        exclude=("keep.txt",),
        tree_only=("keep.txt",),
        include=("keep.txt",),
    )

    decision = matcher.explain_inclusion(target, is_dir=False)

    assert decision.level is InclusionLevel.FULL
    assert decision.reason is not None
    assert decision.reason.raw == "keep.txt"


def test_legacy_negation_still_restores_full_inclusion(tmp_path: Path) -> None:
    matcher = _matcher(
        repo_root=tmp_path,
        tree_patterns=("foo/**", "!foo/bar/keep.txt"),
    )

    target = tmp_path / "foo" / "bar" / "keep.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("ok", encoding="utf-8")

    decision = matcher.explain_inclusion(target, is_dir=False)
    assert decision.level is InclusionLevel.FULL
    assert decision.reason is not None
    assert decision.reason.negated is True
    assert decision.reason.raw == "!foo/bar/keep.txt"


def test_legacy_content_exclusion_maps_to_tree_only(tmp_path: Path) -> None:
    matcher = _matcher(
        repo_root=tmp_path,
        print_patterns=("**/*.md",),
    )

    notes = tmp_path / "docs" / "writing.md"
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text("doc", encoding="utf-8")

    decision = matcher.explain_inclusion(notes, is_dir=False)
    tree_decision = matcher.explain_tree(notes, is_dir=False)
    content_decision = matcher.explain_content(notes, is_dir=False)

    assert decision.level is InclusionLevel.TREE_ONLY
    assert tree_decision.excluded is False
    assert tree_decision.reason is None
    assert content_decision.excluded is True
    assert content_decision.reason is not None
