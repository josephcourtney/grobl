from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grobl.cli import root as cli_root
from grobl.cli.root import main as module_main

if TYPE_CHECKING:
    import pytest


class _DummyCLI:
    def __init__(self) -> None:
        self.called_with: list[str] | None = None

    # Click's Group exposes .main(); our tests only need to capture args.
    def main(self, *, args: list[str], prog_name: str, standalone_mode: bool) -> None:
        self.called_with = args


def test_main_injects_scan_after_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyCLI()
    monkeypatch.setattr(cli_root, "cli", dummy, raising=True)
    module_main(["-v", "patharg"])
    assert dummy.called_with is not None
    # injection occurs *after* leading verbosity/log-level flags
    assert dummy.called_with == ["-v", "scan", "patharg"]


def test_main_does_not_inject_when_subcommand_present(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyCLI()
    monkeypatch.setattr(cli_root, "cli", dummy, raising=True)
    module_main(["version"])
    assert dummy.called_with is not None
    assert dummy.called_with[0] == "version"
