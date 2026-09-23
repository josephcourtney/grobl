from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.medium


def test_config_prune_debug_profiles_to_stderr_without_corrupting_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-empty"))
    config = tmp_path / ".grobl.toml"
    config.write_text('exclude = ["build"]\n', encoding="utf-8")
    (tmp_path / "build").mkdir()

    result = CliRunner().invoke(
        cli,
        ["--debug", "config", "prune", str(config), "--current-tree", "--stdout"],
    )

    assert result.exit_code == 0
    assert "Grobl config prune debug:" in result.stderr
    assert "elapsed wall time:" in result.stderr
    assert "top 30 functions by cumulative time:" in result.stderr
    assert "_prune_current_tree" in result.stderr
    assert "Grobl config prune debug:" not in result.stdout
