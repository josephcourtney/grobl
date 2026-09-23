from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli

pytestmark = pytest.mark.medium

if TYPE_CHECKING:
    from pathlib import Path


def _make_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    links = repo / "links"
    shared = repo / "shared"
    links.mkdir(parents=True)
    shared.mkdir()
    (repo / ".git").mkdir()
    target = shared / "target.txt"
    target.write_text("shared contents\n", encoding="utf-8")
    (links / "alias.txt").symlink_to(target)
    monkeypatch.chdir(repo)
    return repo, links


def test_follow_symlinks_cli_reads_internal_target_under_logical_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _repo, links = _make_repo(tmp_path, monkeypatch)

    result = CliRunner().invoke(
        cli,
        [
            "scan",
            str(links),
            "--follow-symlinks",
            "--format",
            "json",
            "--output",
            "-",
            "--summary",
            "none",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert [entry["path"] for entry in payload["files"]] == ["links/alias.txt"]
    alias = next(entry for entry in payload["tree"] if entry["path"] == "links/alias.txt")
    assert alias["type"] == "symlink"
    assert alias["target_scope"] == "internal"


def test_follow_symlinks_can_be_persisted_in_project_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, links = _make_repo(tmp_path, monkeypatch)
    (repo / ".grobl.toml").write_text("follow_symlinks = true\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "scan",
            str(links),
            "--format",
            "json",
            "--output",
            "-",
            "--summary",
            "none",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert [entry["path"] for entry in payload["files"]] == ["links/alias.txt"]


def test_external_symlink_opt_in_requires_following(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _repo, links = _make_repo(tmp_path, monkeypatch)

    result = CliRunner().invoke(
        cli,
        [
            "scan",
            str(links),
            "--allow-external-symlinks",
            "--format",
            "json",
            "--output",
            "-",
            "--summary",
            "none",
        ],
    )

    assert result.exit_code != 0
    assert "--allow-external-symlinks requires --follow-symlinks" in result.output
