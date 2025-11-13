from __future__ import annotations

from typing import Any

import pytest
from click.testing import CliRunner

from grobl.cli import scan as cli_scan


@pytest.fixture(autouse=True)
def _patch_scan_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_scan, "load_and_adjust_config", lambda **_: {})
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

    helper_calls: dict[str, int] = {"count": 0}

    def exit_stub() -> None:
        helper_calls["count"] += 1
        raise SystemExit(0)

    monkeypatch.setattr(cli_scan, "exit_on_broken_pipe", exit_stub, raising=True)

    print_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def raising_print(*args: Any, **kwargs: Any) -> None:
        print_calls.append((args, kwargs))
        raise BrokenPipeError

    monkeypatch.setattr(cli_scan, "print", raising_print, raising=False)

    result = runner.invoke(cli_scan.scan, [])

    assert result.exit_code == 0
    assert helper_calls["count"] == 1
    assert print_calls, "expected print to be invoked before the helper ran"


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

    print_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def raising_print(*args: Any, **kwargs: Any) -> None:
        print_calls.append((args, kwargs))
        raise BrokenPipeError

    monkeypatch.setattr(cli_scan, "print", raising_print, raising=False)

    result = runner.invoke(cli_scan.scan, ["--summary", "json"])

    assert result.exit_code == 0
    assert helper_calls["count"] == 1
    assert print_calls, "expected print to be invoked before the helper ran"
