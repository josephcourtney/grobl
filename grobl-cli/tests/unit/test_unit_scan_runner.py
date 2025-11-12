"""Unit tests for grobl_cli.service.scan_runner helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest
from grobl_cli.service.scan_runner import ScanCommandParams, run_scan_command

if TYPE_CHECKING:
    from pathlib import Path


def minimal_params(tmp_path: Path) -> ScanCommandParams:
    return ScanCommandParams(
        ignore_defaults=False,
        no_ignore=False,
        no_clipboard=True,
        output=None,
        add_ignore=(),
        remove_ignore=(),
        ignore_file=(),
        mode="summary",
        table="none",
        config_path=None,
        fmt="human",
        quiet=True,
        paths=(tmp_path,),
        yes=True,
    )


def test_run_scan_summary_none(tmp_path: Path) -> None:
    params = minimal_params(tmp_path)

    with mock.patch("grobl_cli.service.scan_runner.ScanExecutor") as mock_executor:
        instance = mock_executor.return_value
        instance.execute.return_value = "SUMMARY"

        result = run_scan_command(params)

    assert result == "SUMMARY"
    instance.execute.assert_called_once()


def test_run_scan_keyboard_interrupt(tmp_path: Path) -> None:
    params = minimal_params(tmp_path)

    with mock.patch("grobl_cli.service.scan_runner.ScanExecutor.execute", side_effect=KeyboardInterrupt):
        with pytest.raises(SystemExit) as excinfo_raw:
            run_scan_command(params)

    excinfo = cast("pytest.ExceptionInfo[SystemExit]", excinfo_raw)
    assert excinfo.value.code == 130
