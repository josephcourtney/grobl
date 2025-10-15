"""Unit tests for grobl_cli.cli module behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest
from click.testing import CliRunner

from grobl_cli.cli.scan import scan

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_scan_cli_default_calls_runner(runner: CliRunner, tmp_path: Path) -> None:
    with mock.patch("grobl_cli.cli.scan.run_scan_command", return_value="FAKE SUMMARY") as mock_runner:
        result = runner.invoke(scan, [str(tmp_path)])

    assert result.exit_code == 0
    assert "FAKE SUMMARY" in result.output
    mock_runner.assert_called_once()
    params = mock_runner.call_args.args[0]
    assert params.paths == (tmp_path,)
    assert params.mode == "summary"
    assert params.table == "auto"
    assert params.fmt == "human"


def test_scan_cli_output_to_file(runner: CliRunner, tmp_path: Path) -> None:
    output_file = tmp_path / "out.txt"
    with mock.patch("grobl_cli.cli.scan.run_scan_command", return_value="FILE OUTPUT") as mock_runner:
        result = runner.invoke(scan, [str(tmp_path), "--output", str(output_file)])

    assert result.exit_code == 0
    assert "FILE OUTPUT" in result.output
    params = mock_runner.call_args.args[0]
    assert params.output == output_file


def test_scan_cli_invalid_table_combo(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(scan, [str(tmp_path), "--mode", "summary", "--table", "none"])
    assert result.exit_code == 2
    assert "No output would be produced" in result.output


def test_scan_cli_propagates_scan_failure(runner: CliRunner, tmp_path: Path) -> None:
    with mock.patch("grobl_cli.cli.scan.run_scan_command", side_effect=SystemExit(3)):
        result = runner.invoke(scan, [str(tmp_path)])

    assert result.exit_code == 3
