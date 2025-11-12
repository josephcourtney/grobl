from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner

from grobl import tty
from grobl.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_explicit_full_table_even_when_not_tty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force non-tty but request full table explicitly
    monkeypatch.setattr(tty, "stdout_is_tty", lambda: False)
    (tmp_path / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["scan", str(tmp_path), "--summary-style", "full", "--sink", "stdout"],
    )
    assert res.exit_code == 0
    assert " Project Summary " in res.output


def test_quiet_suppresses_summary_output(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["scan", str(tmp_path), "--summary", "none", "--sink", "stdout"],
    )
    assert res.exit_code == 0
    out = res.output
    assert "Project Summary" not in out
