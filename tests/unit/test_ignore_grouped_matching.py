from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grobl.constants import InclusionLevel
from grobl.ignore import InclusionLayer, InclusionRule, LayerSource, build_layered_ignores

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.small


def test_grouped_matcher_preserves_last_rule_across_ancestor_and_target(tmp_path: Path) -> None:
    matcher = build_layered_ignores(
        repo_root=tmp_path,
        include_defaults=False,
        default_cfg={},
        runtime_exclude=("generated/",),
        runtime_include=("generated/keep.txt",),
    )

    keep = matcher.explain_inclusion(tmp_path / "generated" / "keep.txt", is_dir=False)
    drop = matcher.explain_inclusion(tmp_path / "generated" / "drop.txt", is_dir=False)

    assert keep.level is InclusionLevel.FULL
    assert keep.reason is not None
    assert keep.reason.raw == "generated/keep.txt"
    assert drop.level is InclusionLevel.OMIT
    assert drop.reason is not None
    assert drop.reason.raw == "generated/"


def test_grouped_matcher_preserves_basename_and_root_anchored_patterns(tmp_path: Path) -> None:
    matcher = build_layered_ignores(
        repo_root=tmp_path,
        include_defaults=False,
        default_cfg={},
        runtime_exclude=("*.log", "/root-only.txt"),
    )

    assert matcher.explain_inclusion(tmp_path / "a" / "b" / "trace.log", is_dir=False).level is InclusionLevel.OMIT
    assert matcher.explain_inclusion(tmp_path / "root-only.txt", is_dir=False).level is InclusionLevel.OMIT
    assert (
        matcher.explain_inclusion(tmp_path / "nested" / "root-only.txt", is_dir=False).level
        is InclusionLevel.FULL
    )


def test_grouped_matcher_preserves_higher_layer_precedence(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    matcher = build_layered_ignores(
        repo_root=tmp_path,
        include_defaults=False,
        default_cfg={},
        config_layers=(
            InclusionLayer(
                base_dir=tmp_path,
                rules=(InclusionRule(pattern="docs/**", level=InclusionLevel.OMIT),),
                source=LayerSource.CONFIG,
                config_path=tmp_path / ".grobl.toml",
            ),
            InclusionLayer(
                base_dir=docs,
                rules=(InclusionRule(pattern="keep.md", level=InclusionLevel.FULL),),
                source=LayerSource.CONFIG,
                config_path=docs / ".grobl.toml",
            ),
        ),
    )

    decision = matcher.explain_inclusion(docs / "keep.md", is_dir=False)

    assert decision.level is InclusionLevel.FULL
    assert decision.reason is not None
    assert decision.reason.config_path == docs / ".grobl.toml"


def test_grouped_matcher_preserves_explicit_negated_restoration(tmp_path: Path) -> None:
    matcher = build_layered_ignores(
        repo_root=tmp_path,
        include_defaults=False,
        default_cfg={},
        runtime_exclude=("*.txt",),
        runtime_rules=(InclusionRule(pattern="!keep.txt", level=InclusionLevel.OMIT),),
    )

    keep = matcher.explain_inclusion(tmp_path / "keep.txt", is_dir=False)
    drop = matcher.explain_inclusion(tmp_path / "drop.txt", is_dir=False)

    assert keep.level is InclusionLevel.FULL
    assert keep.reason is not None
    assert keep.reason.raw == "!keep.txt"
    assert drop.level is InclusionLevel.OMIT
