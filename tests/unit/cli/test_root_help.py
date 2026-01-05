from __future__ import annotations

import pytest
from click.testing import CliRunner

from grobl import __version__
from grobl.cli import root as cli_root

pytestmark = pytest.mark.small


def test_root_help_is_concise() -> None:
    runner = CliRunner()
    result = runner.invoke(cli_root.cli, ["--help"])

    assert result.exit_code == 0
    assert "Commands:" not in result.output
    assert "Default command: scan. Use `grobl scan --help` for command details." in result.output
    assert result.output.count("Usage: ") == 1


@pytest.mark.parametrize("flag", ["--version", "-V"])
def test_version_flag_outputs_only_the_version(flag: str) -> None:
    runner = CliRunner()
    result = runner.invoke(cli_root.cli, [flag])

    assert result.exit_code == 0
    assert result.output == f"{__version__}\n"
