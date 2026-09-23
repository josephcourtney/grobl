from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grobl.app.explain import build_explain_entries
from grobl.constants import ContentScope, TableStyle
from grobl.core import run_scan
from grobl.summary import SummaryContext, build_sink_payload_json
from tests.support import build_ignore_matcher

pytestmark = pytest.mark.medium

if TYPE_CHECKING:
    from pathlib import Path


def test_file_symlink_is_relationship_only_by_default(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "target.txt"
    target.write_text("target contents\n", encoding="utf-8")
    link = repo / "alias.txt"
    link.symlink_to(target.name)

    ignores = build_ignore_matcher(repo_root=repo)
    result = run_scan(paths=[repo], cfg={}, ignores=ignores, repo_root=repo)

    tree = "\n".join(result.builder.tree_output())
    assert "alias.txt -> target.txt" in tree
    assert [entry["path"] for entry in result.builder.files_json()] == ["target.txt"]
    assert result.builder.symlink_info("alias.txt") is not None


def test_internal_file_symlink_can_be_followed_under_logical_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    links = repo / "links"
    shared = repo / "shared"
    links.mkdir(parents=True)
    shared.mkdir()
    target = shared / "target.txt"
    target.write_text("shared contents\n", encoding="utf-8")
    link = links / "alias.txt"
    link.symlink_to(target)

    ignores = build_ignore_matcher(repo_root=repo)
    result = run_scan(
        paths=[links],
        cfg={"_follow_symlinks": True},
        ignores=ignores,
        repo_root=repo,
    )

    files = result.builder.files_json()
    assert len(files) == 1
    assert files[0]["path"] == "links/alias.txt"
    assert files[0]["content"] == "shared contents\n"


def test_logical_exclusion_prevents_following_symlink(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    links = repo / "links"
    shared = repo / "shared"
    links.mkdir(parents=True)
    shared.mkdir()
    target = shared / "target.txt"
    target.write_text("secret-ish contents\n", encoding="utf-8")
    (links / "alias.txt").symlink_to(target)

    ignores = build_ignore_matcher(repo_root=repo, exclude_patterns=("links/alias.txt",))
    result = run_scan(
        paths=[links],
        cfg={"_follow_symlinks": True},
        ignores=ignores,
        repo_root=repo,
    )

    assert "alias.txt" not in "\n".join(result.builder.tree_output())
    assert result.builder.files_json() == []


def test_omitted_directory_symlink_can_reach_reincluded_descendant(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    links = repo / "links"
    shared = repo / "shared"
    links.mkdir(parents=True)
    shared.mkdir()
    (shared / "keep.txt").write_text("keep\n", encoding="utf-8")
    (shared / "drop.txt").write_text("drop\n", encoding="utf-8")
    (links / "tree-link").symlink_to(shared, target_is_directory=True)

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

    rendered = "\n".join(result.builder.tree_output())
    assert "tree-link ->" not in rendered
    assert "keep.txt" in rendered
    assert "drop.txt" not in rendered
    assert [entry["path"] for entry in result.builder.files_json()] == ["links/tree-link/keep.txt"]


def test_external_symlink_requires_second_opt_in(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    link = repo / "outside.txt"
    link.symlink_to(outside)
    ignores = build_ignore_matcher(repo_root=repo)

    blocked = run_scan(
        paths=[repo],
        cfg={"_follow_symlinks": True},
        ignores=ignores,
        repo_root=repo,
    )
    assert blocked.builder.files_json() == []
    assert "[external]" in "\n".join(blocked.builder.tree_output())

    allowed = run_scan(
        paths=[repo],
        cfg={"_follow_symlinks": True, "_allow_external_symlinks": True},
        ignores=ignores,
        repo_root=repo,
    )
    assert [entry["path"] for entry in allowed.builder.files_json()] == ["outside.txt"]


def test_broken_symlink_is_retained_without_dereferencing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    link = repo / "missing.txt"
    link.symlink_to("does-not-exist.txt")

    ignores = build_ignore_matcher(repo_root=repo)
    result = run_scan(paths=[repo], cfg={}, ignores=ignores, repo_root=repo)

    assert "missing.txt -> does-not-exist.txt [broken]" in "\n".join(result.builder.tree_output())
    assert result.builder.files_json() == []


def test_single_symlink_scan_uses_logical_parent_as_root(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("hello\n", encoding="utf-8")
    link = tmp_path / "alias.txt"
    link.symlink_to(target.name)

    ignores = build_ignore_matcher(repo_root=tmp_path)
    result = run_scan(paths=[link], cfg={}, ignores=ignores)

    assert result.common == tmp_path
    assert result.builder.ordered_entries() == [("symlink", link.relative_to(tmp_path))]
    assert result.builder.files_json() == []


def test_following_directory_symlink_deduplicates_cycle_by_inode(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    links = repo / "links"
    tree = repo / "tree"
    links.mkdir(parents=True)
    tree.mkdir()
    (tree / "leaf.txt").write_text("leaf\n", encoding="utf-8")
    (tree / "again").symlink_to(tree, target_is_directory=True)
    (links / "tree-link").symlink_to(tree, target_is_directory=True)

    ignores = build_ignore_matcher(repo_root=repo)
    result = run_scan(
        paths=[links],
        cfg={"_follow_symlinks": True},
        ignores=ignores,
        repo_root=repo,
    )

    rendered = "\n".join(result.builder.tree_output())
    assert rendered.count("leaf.txt") == 1
    assert rendered.count("again ->") == 1


def test_following_does_not_duplicate_target_selected_by_real_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "target.txt"
    target.write_text("once\n", encoding="utf-8")
    (repo / "alias.txt").symlink_to(target.name)

    ignores = build_ignore_matcher(repo_root=repo)
    result = run_scan(
        paths=[repo],
        cfg={"_follow_symlinks": True},
        ignores=ignores,
        repo_root=repo,
    )

    assert [entry["path"] for entry in result.builder.files_json()] == ["target.txt"]


def test_json_tree_exposes_symlink_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "target.txt"
    target.write_text("contents\n", encoding="utf-8")
    (repo / "alias.txt").symlink_to(target.name)

    ignores = build_ignore_matcher(repo_root=repo)
    result = run_scan(paths=[repo], cfg={}, ignores=ignores, repo_root=repo)
    payload = build_sink_payload_json(
        SummaryContext(
            builder=result.builder,
            common=result.common,
            scope=ContentScope.ALL,
            style=TableStyle.AUTO,
        )
    )

    alias = next(entry for entry in payload["tree"] if entry["path"] == "alias.txt")
    assert alias["type"] == "symlink"
    assert alias["target"] == "target.txt"
    assert alias["target_scope"] == "internal"
    assert alias["broken"] is False


def test_explain_reports_external_symlink_disposition(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    link = repo / "outside.txt"
    link.symlink_to(outside)
    ignores = build_ignore_matcher(repo_root=repo)

    entries = build_explain_entries(
        paths=(link,),
        ignores=ignores,
        repo_root=repo,
        follow_symlinks=True,
        allow_external_symlinks=False,
    )

    symlink = entries[0]["symlink"]
    assert symlink["target_scope"] == "external"
    assert symlink["disposition"] == "not followed; target is outside the repository root"
    assert entries[0]["content"]["included"] is False


def test_explain_reports_tree_only_symlink_as_not_followed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "target.txt"
    target.write_text("contents\n", encoding="utf-8")
    link = repo / "alias.txt"
    link.symlink_to(target.name)
    ignores = build_ignore_matcher(repo_root=repo, tree_only_patterns=("alias.txt",))

    entries = build_explain_entries(
        paths=(link,),
        ignores=ignores,
        repo_root=repo,
        follow_symlinks=True,
    )

    assert entries[0]["state"] == "tree_only"
    assert entries[0]["symlink"]["disposition"] == "not followed; content state is tree_only"
    assert entries[0]["content"]["included"] is False
