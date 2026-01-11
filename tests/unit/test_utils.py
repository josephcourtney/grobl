from __future__ import annotations

import os
from pathlib import Path

import pytest

from grobl import utils
from grobl.config import apply_runtime_ignore_edits
from grobl.errors import PathNotFoundError
from grobl.utils import detect_text, find_common_ancestor, is_text, resolve_repo_root

pytestmark = pytest.mark.small

try:  # import at module level; skip the whole module if unavailable
    from hypothesis import given
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover - tooling availability
    pytest.skip("hypothesis not available", allow_module_level=True)


def test_find_common_ancestor_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        find_common_ancestor([])


def test_find_common_ancestor_single_path(tmp_path: Path) -> None:
    got = find_common_ancestor([tmp_path])
    assert got == tmp_path


@pytest.mark.skipif(os.name != "posix", reason="POSIX-only path assumptions")
def test_find_common_ancestor_allows_filesystem_root() -> None:
    got = find_common_ancestor([Path("/"), Path("/tmp")])  # noqa: S108 - controlled use in test
    assert got == Path("/")


def test_is_text_missing_file_returns_false(tmp_path: Path) -> None:
    missing = tmp_path / "nope.txt"
    assert is_text(missing) is False
    detection = detect_text(missing)
    assert detection.is_text is False
    assert detection.content is None


def test_detect_text_prefetches_content(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("héllo\nworld", encoding="utf-8")

    detection = detect_text(sample)

    assert detection.is_text is True
    assert detection.content == sample.read_text(encoding="utf-8", errors="ignore")


def test_detect_text_binary_payload(tmp_path: Path) -> None:
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"\x00\xff\x01\x02")

    detection = detect_text(blob)

    assert detection.is_text is False
    assert detection.content is None


@pytest.mark.parametrize(
    ("components", "expected_rel"),
    [
        (("a",), "a"),
        (("a", "a/b"), "a"),
        (("x/y/z", "x/y/w"), "x/y"),
    ],
)
def test_common_ancestor_param(tmp_path: Path, components: tuple[str, ...], expected_rel: str) -> None:
    paths = [tmp_path / c for c in components]
    got = find_common_ancestor(paths)
    expected = tmp_path / expected_rel
    assert got == expected


@pytest.mark.skipif(os.name != "posix", reason="POSIX-only path assumptions")
def test_common_ancestor_disjoint_drives_like(tmp_path: Path) -> None:
    # Mixing unrelated absolute paths should still converge on the filesystem root
    got = find_common_ancestor([Path("/usr"), tmp_path / "q"])
    assert got == Path("/")


@pytest.mark.skipif(os.name != "nt", reason="Windows-only drive semantics")
def test_common_ancestor_windows_disjoint_drives() -> None:
    with pytest.raises(PathNotFoundError):
        find_common_ancestor([Path("C:/alpha"), Path("D:/beta")])


SEGMENT = st.text(
    min_size=1,
    max_size=5,
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
)


@given(
    base=st.lists(SEGMENT, max_size=5),
    add=st.lists(SEGMENT, max_size=3),
    remove=st.lists(SEGMENT, max_size=3),
    no_ignore=st.booleans(),
)
def test_apply_runtime_ignore_edits_matches_manual_logic(
    base: list[str], add: list[str], remove: list[str], *, no_ignore: bool
) -> None:
    result = apply_runtime_ignore_edits(
        base_tree=list(base),
        base_print=[],
        add_ignore=tuple(add),
        remove_ignore=tuple(remove),
        add_ignore_files=(),
        unignore=(),
        no_ignore=no_ignore,
    )
    if no_ignore:
        assert result.tree_patterns == []
        return

    expected = base.copy()
    for pattern in add:
        if pattern not in expected:
            expected.append(pattern)
    for pattern in remove:
        if pattern in expected:
            expected.remove(pattern)
    assert result.tree_patterns == expected


def test_apply_runtime_ignore_edits_shared_excludes_and_includes() -> None:
    result = apply_runtime_ignore_edits(
        base_tree=[],
        base_print=[],
        add_ignore=(),
        remove_ignore=(),
        add_ignore_files=(),
        unignore=(),
        exclude=("foo",),
        include=("bar",),
    )
    assert result.tree_patterns == ["foo", "!bar"]
    assert result.print_patterns == ["foo", "!bar"]


def test_apply_runtime_ignore_edits_scoped_overrides() -> None:
    result = apply_runtime_ignore_edits(
        base_tree=[],
        base_print=[],
        add_ignore=(),
        remove_ignore=(),
        add_ignore_files=(),
        unignore=(),
        exclude_tree=("tree-only",),
        exclude_content=("content-only",),
        include_tree=("keep-tree",),
        include_content=("keep-content",),
    )
    assert "tree-only" in result.tree_patterns
    assert "content-only" not in result.tree_patterns
    assert "content-only" in result.print_patterns
    assert "tree-only" not in result.print_patterns
    assert "!keep-tree" in result.tree_patterns
    assert "!keep-content" in result.print_patterns


def test_common_ancestor_config_base(tmp_path: Path) -> None:
    base = tmp_path / "proj"
    (base / "a").mkdir(parents=True)
    (base / "b").mkdir(parents=True)
    p1 = base / "a" / "x.txt"
    p2 = base / "b" / "y.txt"
    p1.write_text("one", encoding="utf-8")
    p2.write_text("two", encoding="utf-8")

    common = find_common_ancestor([p1, p2])
    assert common == base


def test_resolve_repo_root_prefers_git_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    child = repo_root / "src"
    child.mkdir()
    monkeypatch.setattr(utils, "_git_root_for_cwd", lambda *_: repo_root)

    got = resolve_repo_root(cwd=repo_root, paths=(child,))
    assert got == repo_root


def test_resolve_repo_root_ignores_git_root_when_paths_outside(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    fork = tmp_path / "external"
    fork.mkdir()
    monkeypatch.setattr(utils, "_git_root_for_cwd", lambda *_: repo_root)

    got = resolve_repo_root(cwd=repo_root, paths=(fork,))
    assert got == repo_root


def test_resolve_repo_root_falls_back_to_cwd_when_common_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(utils, "_git_root_for_cwd", lambda *_: None)
    monkeypatch.setattr(
        utils, "find_common_ancestor", lambda _: (_ for _ in ()).throw(PathNotFoundError("boom"))
    )

    got = resolve_repo_root(cwd=tmp_path, paths=(tmp_path / "missing",))
    assert got == tmp_path
