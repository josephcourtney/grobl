from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli
from grobl.constants import EXIT_CONFIG, EXIT_USAGE

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.small


def test_usage_error_invalid_scope(repo_root: Path) -> None:
    (repo_root / "f.txt").write_text("x", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(repo_root), "--scope", "bogus"])
    # Click treats invalid option values as usage error (SystemExit 2)
    assert res.exit_code == EXIT_USAGE


def test_config_load_error_bad_explicit_config(repo_root: Path) -> None:
    bad = repo_root / "bad.toml"
    bad.write_text("= broken =\n", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(repo_root), "--config", str(bad)])
    assert res.exit_code == EXIT_CONFIG


def test_config_load_error_bad_pyproject(repo_root: Path) -> None:
    # Create project base with bad pyproject.toml
    base = repo_root / "proj"
    base.mkdir()
    (base / "pyproject.toml").write_text("[tool.grobl\n# missing closing bracket", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(base)])
    assert res.exit_code == EXIT_CONFIG


def test_config_load_error_missing_explicit_config(repo_root: Path) -> None:
    missing = repo_root / "missing.toml"
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(repo_root), "--config", str(missing)])
    assert res.exit_code == EXIT_CONFIG
    assert "missing.toml" in res.output
