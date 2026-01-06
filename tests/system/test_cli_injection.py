from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli
from grobl.constants import EXIT_USAGE

pytestmark = pytest.mark.small


if TYPE_CHECKING:
    from pathlib import Path


def _mkfile(p: Path, text: str = "x\n") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _run(args: list[str]) -> tuple[int, str, str]:
    runner = CliRunner()
    res = runner.invoke(cli, args)
    return res.exit_code, res.stdout, res.stderr


def test_default_scan_injection_when_first_token_is_path_like_tilde(repo_root: Path) -> None:
    code, out, err = _run(["~definitely-not-a-real-path"])
    blob = out + err
    assert code != 0
    assert "Unknown command:" not in blob


@pytest.mark.skipif(os.name != "nt", reason="Backslash path-like token test is Windows-only")
def test_default_scan_injection_when_first_token_is_path_like_backslash_windows(repo_root: Path) -> None:
    code, out, err = _run([".\\"])
    blob = out + err
    assert code != 0
    assert "Unknown command:" not in blob


def test_no_args_does_not_crash_and_behaves_per_default_command_rules(repo_root: Path) -> None:
    _mkfile(repo_root / "a.txt", "a\n")
    code, out, err = _run([])
    assert code in {0, EXIT_USAGE}
    if code == 0:
        blob = out + err
        assert "Unknown command:" not in blob
