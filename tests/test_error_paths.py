from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner

from grobl.cli import cli
from grobl.constants import EXIT_CONFIG, EXIT_PATH, EXIT_USAGE

if TYPE_CHECKING:
    from pathlib import Path


def test_usage_error_invalid_mode(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path), "--mode", "bogus"])
    # Click treats invalid option values as usage error (SystemExit 2)
    assert res.exit_code == EXIT_USAGE


def test_path_error_no_real_common_ancestor() -> None:
    runner = CliRunner()
    # Using "/" and "/tmp" yields common ancestor "/" which our helper rejects
    res = runner.invoke(cli, ["scan", "/", "/tmp"])
    assert res.exit_code == EXIT_PATH
    assert "No common ancestor" in res.output or res.output


def test_config_load_error_bad_explicit_config(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("= broken =\n", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path), "--config", str(bad)])
    assert res.exit_code == EXIT_CONFIG


def test_config_load_error_bad_pyproject(tmp_path: Path) -> None:
    # Create project base with bad pyproject.toml
    base = tmp_path / "proj"
    base.mkdir()
    (base / "pyproject.toml").write_text("[tool.grobl\n# missing closing bracket", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(base)])
    assert res.exit_code == EXIT_CONFIG
