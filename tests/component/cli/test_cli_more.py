from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl import tty
from grobl.cli import cli

pytestmark = pytest.mark.small

if TYPE_CHECKING:
    from pathlib import Path


def test_explicit_full_table_even_when_not_tty(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force non-tty but request full table explicitly
    monkeypatch.setattr(tty, "stdout_is_tty", lambda: False)
    (repo_root / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["scan", str(repo_root), "--summary", "table", "--summary-style", "full", "--output", "-"],
    )
    assert res.exit_code == 0
    assert " Project Summary " in res.stderr


def test_quiet_suppresses_summary_output(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["scan", str(repo_root), "--summary", "none", "--output", "-"],
    )
    assert res.exit_code == 0
    out = res.output
    assert "Project Summary" not in out
