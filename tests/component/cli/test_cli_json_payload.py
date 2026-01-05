from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli

pytestmark = pytest.mark.small

if TYPE_CHECKING:
    from pathlib import Path


def test_cli_json_tree_payload(repo_root: Path) -> None:
    d = repo_root / "dir"
    d.mkdir()
    (d / "a.txt").write_text("aa", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(repo_root),
            "--scope",
            "tree",
            "--format",
            "json",
            "--summary",
            "none",
            "--output",
            "-",
        ],
    )
    assert res.exit_code == 0
    output = res.output.strip()
    data = json.loads(output)
    assert data["scope"] == "tree"
    assert data["root"] == str(repo_root)
    assert "summary" in data
    assert "totals" in data["summary"]
    # entries should include dir and file paths
    paths = {e["path"] for e in data.get("tree", [])}
    assert "dir" in {e["type"] for e in data.get("tree", [])}
    assert "dir/a.txt" in paths or "a.txt" in paths  # depending on tree ordering when base is tmp_path


def test_cli_json_files_payload(repo_root: Path) -> None:
    (repo_root / "inc.txt").write_text("hello", encoding="utf-8")
    (repo_root / "skip.txt").write_text("skip", encoding="utf-8")
    cfg = repo_root / "explicit.toml"
    cfg.write_text("", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(repo_root),
            "--scope",
            "files",
            "--format",
            "json",
            "--summary",
            "none",
            "--config",
            str(cfg),
            "--output",
            "-",
        ],
    )
    assert res.exit_code == 0
    output = res.output.strip()
    data = json.loads(output)
    assert data["scope"] == "files"
    files = {f["name"]: f for f in data.get("files", [])}
    assert files["inc.txt"]["content"] == "hello"
    sfiles = {f["path"]: f for f in data.get("summary", {}).get("files", [])}
    assert "inc.txt" in sfiles


def test_cli_json_all_payload(repo_root: Path) -> None:
    (repo_root / "x.txt").write_text("x", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(repo_root),
            "--scope",
            "all",
            "--format",
            "json",
            "--summary",
            "none",
            "--output",
            "-",
        ],
    )
    assert res.exit_code == 0
    output = res.output.strip()
    data = json.loads(output)
    assert data["scope"] == "all"
    assert "tree" in data
    assert "files" in data
    assert "summary" in data
