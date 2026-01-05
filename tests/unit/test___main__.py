from __future__ import annotations

import io
import runpy
import sys

import click
import pytest
from click.testing import CliRunner

from grobl.cli import root as cli_root
from grobl.cli.root import main as module_main

pytestmark = pytest.mark.small


def test_main_module_invokes_cli(monkeypatch):
    called = {}
    monkeypatch.setattr("grobl.cli.main", lambda: called.setdefault("ran", True))
    runpy.run_module("grobl.__main__", run_name="__main__")
    assert called.get("ran")


class _DummyCLI:
    def __init__(self) -> None:
        self.called_with: list[str] | None = None

    # Click's Group exposes .main(); our tests only need to capture args.
    def main(self, *, args: list[str], prog_name: str, standalone_mode: bool) -> None:
        self.called_with = list(args)


def test_main_passes_arguments_through(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyCLI()
    monkeypatch.setattr(cli_root, "cli", dummy, raising=True)

    module_main(["-v", "patharg"])
    assert dummy.called_with == ["-v", "patharg"]

    module_main([])
    assert dummy.called_with == []


def test_main_preserves_explicit_subcommands(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyCLI()
    monkeypatch.setattr(cli_root, "cli", dummy, raising=True)

    module_main(["version"])
    assert dummy.called_with == ["version"]


def test_cli_defaults_to_scan_when_no_subcommand(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    called: dict[str, tuple[str, ...]] = {}

    @click.command()
    @click.argument("paths", nargs=-1)
    def fake_scan(paths: tuple[str, ...]) -> None:
        called["paths"] = paths

    monkeypatch.setitem(cli_root.cli.commands, "scan", fake_scan)
    monkeypatch.setattr(cli_root, "scan", fake_scan, raising=False)

    result = runner.invoke(cli_root.cli, ["alpha", "beta"])

    assert result.exit_code == 2
    assert "Unknown command: alpha" in result.output
    assert "paths" not in called


def test_cli_default_scan_does_not_use_protected_args(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    called: dict[str, tuple[str, ...]] = {}

    @click.command()
    @click.argument("paths", nargs=-1)
    def fake_scan(paths: tuple[str, ...]) -> None:
        called["paths"] = paths

    monkeypatch.setitem(cli_root.cli.commands, "scan", fake_scan)
    monkeypatch.setattr(cli_root, "scan", fake_scan, raising=False)

    def _raise_protected(self: click.Context) -> list[str]:
        msg = "protected args should not be accessed"
        raise RuntimeError(msg)

    monkeypatch.setattr(click.Context, "protected_args", property(_raise_protected), raising=False)

    result = runner.invoke(cli_root.cli, ["alpha", "beta"])

    assert result.exit_code == 2
    assert "Unknown command: alpha" in result.output
    assert "paths" not in called


def test_main_handles_broken_pipe(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenCLI:
        def __init__(self) -> None:
            self.called_with: list[str] | None = None

        def main(
            self,
            *,
            args: list[str],
            prog_name: str,
            standalone_mode: bool,
        ) -> None:
            self.called_with = list(args)
            # Simulate a downstream pipe error during output
            raise BrokenPipeError

    broken_cli = BrokenCLI()
    monkeypatch.setattr(cli_root, "cli", broken_cli, raising=True)

    helper_calls: dict[str, int] = {"count": 0}

    def exit_stub() -> None:
        helper_calls["count"] += 1
        raise SystemExit(0)

    monkeypatch.setattr(cli_root, "exit_on_broken_pipe", exit_stub, raising=True)

    # Protect pytest's own capture file objects: if the implementation closes
    # sys.stdout/stderr, it will only close these fakes.
    fake_out = io.StringIO()
    fake_err = io.StringIO()
    monkeypatch.setattr(sys, "stdout", fake_out)
    monkeypatch.setattr(sys, "stderr", fake_err)

    with pytest.raises(SystemExit) as excinfo:
        module_main(["scan"])

    # Use `.args[0]` instead of `.code` to keep static type checkers happy
    assert excinfo.value.args[0] == 0
    assert broken_cli.called_with == ["scan"]
    assert helper_calls["count"] == 1
