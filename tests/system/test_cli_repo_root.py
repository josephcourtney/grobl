from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl import utils
from grobl.cli import cli

pytestmark = pytest.mark.small


if TYPE_CHECKING:
    from pathlib import Path


def _mkfile(p: Path, text: str = "x\n") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_repo_root_common_ancestor_used_when_multiple_paths(repo_root: Path) -> None:
    base = repo_root / "proj"
    a = base / "a"
    b = base / "b"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    _mkfile(a / "one.txt", "1\n")
    _mkfile(b / "two.txt", "2\n")

    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["scan", str(a), str(b), "--summary", "json", "--format", "none"],
    )
    assert res.exit_code == 0
    blob = (res.stdout + res.stderr).strip()
    data = json.loads(blob)
    assert data["root"] == str(base)


def test_repo_root_git_root_precedence_affects_ordering_base(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git_root = repo_root / "gitroot"
    proj = git_root / "proj"
    proj.mkdir(parents=True)
    _mkfile(proj / "b.txt", "b\n")
    _mkfile(proj / "a.txt", "a\n")

    monkeypatch.chdir(proj)
    monkeypatch.setattr(utils, "_git_root_for_cwd", lambda *_: git_root)

    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(proj),
            "--scope",
            "tree",
            "--summary",
            "none",
            "--format",
            "json",
            "--output",
            "-",
        ],
    )
    assert res.exit_code == 0
    payload_blob = (res.stdout + res.stderr).strip()
    payload = json.loads(payload_blob)
    assert payload["root"] == str(git_root)
