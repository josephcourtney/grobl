from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.small


@pytest.mark.parametrize(("is_tty", "expect_summary"), [(True, True), (False, False)])
def test_summary_auto_contract(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch, *, is_tty: bool, expect_summary: bool
) -> None:
    from grobl import tty
    from grobl.cli import scan as cli_scan

    (repo_root / "a.txt").write_text("x\n", encoding="utf-8")

    monkeypatch.setattr(tty, "stdout_is_tty", lambda: is_tty, raising=True)
    monkeypatch.setattr(cli_scan, "stdout_is_tty", lambda: is_tty, raising=True)

    res = CliRunner().invoke(cli, ["scan", str(repo_root), "--summary", "auto", "--output", "-"])
    assert res.exit_code == 0

    if expect_summary:
        assert "Total lines" in (res.stdout + res.stderr)
    else:
        assert res.stderr.strip() == ""
