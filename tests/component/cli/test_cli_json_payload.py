from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli

pytestmark = pytest.mark.small

if TYPE_CHECKING:
    from pathlib import Path


def test_cli_json_tree_payload(tmp_path: Path) -> None:
    d = tmp_path / "dir"
    d.mkdir()
    (d / "a.txt").write_text("aa", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(tmp_path),
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
    assert data["root"] == str(tmp_path)
    assert "summary" in data
    assert "totals" in data["summary"]
    # entries should include dir and file paths
    paths = {e["path"] for e in data.get("tree", [])}
    assert "dir" in {e["type"] for e in data.get("tree", [])}
    assert "dir/a.txt" in paths or "a.txt" in paths  # depending on tree ordering when base is tmp_path


def test_cli_json_files_payload(tmp_path: Path) -> None:
    (tmp_path / "inc.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "skip.txt").write_text("skip", encoding="utf-8")
    cfg = tmp_path / "explicit.toml"
    cfg.write_text("", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(tmp_path),
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


def test_cli_json_all_payload(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(tmp_path),
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
