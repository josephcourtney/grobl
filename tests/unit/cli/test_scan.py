from __future__ import annotations

import pytest
from click.testing import CliRunner

from grobl.cli import scan as cli_scan

pytestmark = pytest.mark.small


@pytest.fixture(autouse=True)
def _patch_scan_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_scan, "read_config", lambda **_: {})
    monkeypatch.setattr(cli_scan, "build_writer_from_config", lambda **_: lambda _payload: None)
    monkeypatch.setattr(cli_scan, "resolve_table_style", lambda style: style)


def test_scan_human_summary_uses_broken_pipe_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(
        cli_scan,
        "_execute_with_handling",
        lambda **kwargs: ("summary output", {"root": "dummy"}),
        raising=True,
    )
    monkeypatch.setattr(cli_scan, "stdout_is_tty", lambda: True, raising=True)

    helper_calls: dict[str, int] = {"count": 0}

    def exit_stub() -> None:
        helper_calls["count"] += 1
        raise SystemExit(0)

    monkeypatch.setattr(cli_scan, "exit_on_broken_pipe", exit_stub, raising=True)

    def raising_summary_writer(_: str) -> None:
        raise BrokenPipeError

    monkeypatch.setattr(cli_scan, "_build_summary_writer", lambda **_: raising_summary_writer, raising=True)

    result = runner.invoke(cli_scan.scan, [])

    assert result.exit_code == 0
    assert helper_calls["count"] == 1
    # summary writer should be invoked and raise before the helper runs


def test_scan_json_summary_uses_broken_pipe_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(
        cli_scan,
        "_execute_with_handling",
        lambda **kwargs: ("", {"ok": True}),
        raising=True,
    )

    helper_calls: dict[str, int] = {"count": 0}

    def exit_stub() -> None:
        helper_calls["count"] += 1
        raise SystemExit(0)

    monkeypatch.setattr(cli_scan, "exit_on_broken_pipe", exit_stub, raising=True)

    def raising_summary_writer(_: str) -> None:
        raise BrokenPipeError

    monkeypatch.setattr(cli_scan, "_build_summary_writer", lambda **_: raising_summary_writer, raising=True)

    result = runner.invoke(cli_scan.scan, ["--summary", "json"])

    assert result.exit_code == 0
    assert helper_calls["count"] == 1
    # summary writer should be invoked and raise before the helper runs
