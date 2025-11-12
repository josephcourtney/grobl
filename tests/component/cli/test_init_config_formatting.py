from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner

from grobl.cli import cli

if TYPE_CHECKING:
    from pathlib import Path


def test_init_writes_nicely_formatted_config(tmp_path: Path) -> None:
    runner = CliRunner()
    res = runner.invoke(cli, ["init", "--path", str(tmp_path), "--force"])
    assert res.exit_code == 0
    text = (tmp_path / ".grobl.toml").read_text(encoding="utf-8")
    # arrays should be multi-line; spot check a known entry in exclude_tree
    assert "exclude_tree = [" in text
    assert '\n  ".venv",\n' in text or '\n  ".venv"\n' in text
