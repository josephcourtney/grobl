from __future__ import annotations

import os
from pathlib import Path

import pytest

from grobl import utils
from grobl.errors import PathNotFoundError
from grobl.utils import detect_text, find_common_ancestor, is_text, resolve_repo_root

pytestmark = pytest.mark.medium



def test_find_common_ancestor_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        find_common_ancestor([])


def test_find_common_ancestor_single_path(tmp_path: Path) -> None:
    got = find_common_ancestor([tmp_path])
    assert got == tmp_path


@pytest.mark.skipif(os.name != "posix", reason="POSIX-only path assumptions")
def test_find_common_ancestor_allows_filesystem_root() -> None:
    got = find_common_ancestor([Path("/"), Path("/tmp")])  # ruff: ignore[hardcoded-temp-file] - controlled use in test
    assert got == Path("/")


def test_is_text_missing_file_returns_false(tmp_path: Path) -> None:
    missing = tmp_path / "nope.txt"
    assert is_text(missing) is False
    detection = detect_text(missing)
    assert detection.is_text is False
    assert detection.content is None


def test_detect_text_detects_text_without_prefetching(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("héllo\nworld", encoding="utf-8")

    detection = detect_text(sample)

    assert detection.is_text is True
    assert detection.content is None


def test_detect_text_binary_payload(tmp_path: Path) -> None:
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"\x00\xff\x01\x02")

    detection = detect_text(blob)

    assert detection.is_text is False
    assert detection.content is None


def test_detect_text_handles_utf8_chunk_boundary(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    em_dash = b"\xe2\x80\x94"
    payload = b"a" * 4095 + em_dash + b"rest"
    plan.write_bytes(payload)

    detection = detect_text(plan)

    assert detection.is_text is True
    assert detection.content is None


def test_detect_text_returns_false_on_invalid_utf8(tmp_path: Path) -> None:
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff\xfe\xff")

    detection = detect_text(bad)

    assert detection.is_text is False
    assert detection.content is None
    assert detection.detail is not None
    assert "unicode decode error" in detection.detail


def test_detect_text_catches_invalid_after_probe(tmp_path: Path) -> None:
    file = tmp_path / "spread.txt"
    chunk = b"a" * 4096
    invalid = b"\xff\xfe"
    file.write_bytes(chunk + invalid)

    detection = detect_text(file)

    assert detection.is_text is False
    assert detection.content is None
    assert detection.detail is not None
    assert "unicode decode error" in detection.detail


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
