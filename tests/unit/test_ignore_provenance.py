from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grobl.ignore import LayeredIgnoreMatcher, LayerSource, build_layered_ignores

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.small


def _matcher(
    *,
    repo_root: Path,
    tree_patterns: tuple[str, ...] = (),
    print_patterns: tuple[str, ...] = (),
) -> LayeredIgnoreMatcher:
    return build_layered_ignores(
        repo_root=repo_root,
        scan_paths=[repo_root],
        include_defaults=False,
        include_config=False,
        runtime_tree_patterns=tree_patterns,
        runtime_print_patterns=print_patterns,
        default_cfg={},
    )


def test_last_match_wins_for_runtime_includes(tmp_path: Path) -> None:
    matcher = _matcher(
        repo_root=tmp_path,
        tree_patterns=("foo/**", "!foo/bar/keep.txt"),
    )

    target = tmp_path / "foo" / "bar" / "keep.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("ok")

    decision = matcher.explain_tree(target, is_dir=False)
    assert decision.excluded is False
    assert decision.reason is not None
    assert decision.reason.source is LayerSource.CLI_RUNTIME
    assert decision.reason.negated is True
    assert decision.reason.raw == "!foo/bar/keep.txt"
    assert decision.reason.base_dir == tmp_path


def test_tree_and_content_decisions_have_separate_reasons(tmp_path: Path) -> None:
    matcher = _matcher(
        repo_root=tmp_path,
        print_patterns=("**/*.md",),
    )

    notes = tmp_path / "docs" / "writing.md"
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text("doc")

    tree_decision = matcher.explain_tree(notes, is_dir=False)
    content_decision = matcher.explain_content(notes, is_dir=False)

    assert tree_decision.excluded is False
    assert tree_decision.reason is None

    assert content_decision.excluded is True
    assert content_decision.reason is not None
    assert content_decision.reason.source is LayerSource.CLI_RUNTIME
