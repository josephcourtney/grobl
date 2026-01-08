from __future__ import annotations

import pytest
from click.testing import BytesIOCopy, CliRunner

from grobl.cli import scan as cli_scan
from grobl.constants import SummaryDestination, SummaryFormat, TableStyle

pytestmark = pytest.mark.small


@pytest.fixture(autouse=True)
def _patch_scan_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_scan, "load_config", lambda **_: {})
    monkeypatch.setattr(cli_scan, "build_writer_from_config", lambda **_: lambda _payload: None)
    monkeypatch.setattr(cli_scan, "resolve_table_style", lambda style: style)


def test_broken_pipe_does_not_traceback_and_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(
        cli_scan,
        "_execute_with_handling",
        lambda **kwargs: ("summary output", {"ok": True}),
        raising=True,
    )

    def raising_summary_writer(_: str) -> None:
        raise BrokenPipeError

    monkeypatch.setattr(cli_scan, "_build_summary_writer", lambda **_: raising_summary_writer, raising=True)

    orig_getvalue = BytesIOCopy.getvalue

    def _safe_getvalue(self: BytesIOCopy) -> bytes:
        try:
            return orig_getvalue(self)
        except ValueError:
            return b""

    monkeypatch.setattr(BytesIOCopy, "getvalue", _safe_getvalue)

    result = runner.invoke(
        cli_scan.scan,
        ["--scope", "tree"],
        obj={
            "summary": SummaryFormat.TABLE.value,
            "summary_style": TableStyle.AUTO.value,
            "summary_to": SummaryDestination.STDERR.value,
        },
    )
    assert result.exit_code == 0

    blob = (result.stdout or "") + (result.stderr or "")
    assert "Traceback" not in blob
