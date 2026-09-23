from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grobl.core import run_scan
from tests.support import build_ignore_matcher

pytestmark = pytest.mark.medium

if TYPE_CHECKING:
    from pathlib import Path


def test_followed_omitted_directory_symlink_can_reinclude_descendant(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    links = repo / "links"
    target = repo / "target"
    links.mkdir(parents=True)
    target.mkdir()
    (target / "keep.txt").write_text("keep\n", encoding="utf-8")
    (target / "drop.txt").write_text("drop\n", encoding="utf-8")
    (links / "tree-link").symlink_to(target, target_is_directory=True)

    ignores = build_ignore_matcher(
        repo_root=repo,
        exclude_patterns=("links/tree-link/",),
        include_patterns=("links/tree-link/keep.txt",),
    )
    result = run_scan(
        paths=[links],
        cfg={"_follow_symlinks": True},
        ignores=ignores,
        repo_root=repo,
    )

    tree = "\n".join(result.builder.tree_output())
    assert "tree-link ->" not in tree
    assert "keep.txt" in tree
    assert "drop.txt" not in tree
    assert [entry["path"] for entry in result.builder.files_json()] == ["links/tree-link/keep.txt"]
