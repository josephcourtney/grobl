from __future__ import annotations

import io
import runpy
import sys

import pytest

from grobl.cli import root as cli_root
from grobl.cli.root import main as module_main


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


def test_main_injects_scan_after_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyCLI()
    monkeypatch.setattr(cli_root, "cli", dummy, raising=True)

    module_main(["-v", "patharg"])

    assert dummy.called_with is not None
    assert dummy.called_with == ["-v", "scan", "patharg"]

    module_main(["--json"])
    assert dummy.called_with is not None
    assert dummy.called_with[0] == "scan"
    assert dummy.called_with[1:] == ["--json"]


def test_main_does_not_inject_when_subcommand_present(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyCLI()
    monkeypatch.setattr(cli_root, "cli", dummy, raising=True)
    module_main(["version"])
    assert dummy.called_with is not None
    assert dummy.called_with[0] == "version"


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
