from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli
from grobl.constants import EXIT_PATH

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.medium


@pytest.mark.parametrize(
    ("args", "seed_repo", "expect_exit", "expect_unknown_command"),
    [
        (["./"], True, 0, False),  # path-like token
        (["--summary", "json", "."], True, 0, False),  # begins with dash, then path
        (["notapath"], False, EXIT_PATH, False),  # implicit missing path
        (["scan1"], False, EXIT_PATH, False),  # implicit missing path
        (["sc-an"], False, EXIT_PATH, False),
        (["sc_an"], False, EXIT_PATH, False),
        (["Σ"], False, EXIT_PATH, False),
        (["~definitely-not-a-real-path"], False, EXIT_PATH, False),  # implicit missing path
        (["doesnotexist"], False, EXIT_PATH, False),
    ],
)
def test_root_injection_and_unknown_command_contract(
    repo_root: Path, args: list[str], expect_exit: int, *, seed_repo: bool, expect_unknown_command: bool
) -> None:
    if seed_repo:
        (repo_root / "a.txt").write_text("x\n", encoding="utf-8")

    res = CliRunner().invoke(cli, args)
    assert res.exit_code == expect_exit
    blob = res.stdout + res.stderr
    assert ("Unknown command:" in blob) is expect_unknown_command
    # Avoid double-rendering of help/usage text on errors.
    assert blob.count("Usage: ") <= 1


@pytest.mark.skipif(os.name != "nt", reason="Windows-only path-like token semantics")
def test_root_injection_windows_backslash_path_token(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("x\n", encoding="utf-8")
    res = CliRunner().invoke(cli, [r".\\"])
    assert "Unknown command:" not in (res.stdout + res.stderr)


def test_root_injection_env_var_expansion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")
    # Ensure $PWD expands to an existing path on POSIX shells; for the CLI we expand env vars ourselves.
    monkeypatch.setenv("GROBL_TEST_PATH", str(tmp_path))
    res = CliRunner().invoke(cli, ["$GROBL_TEST_PATH", "--summary", "none", "--output", "-"])
    assert res.exit_code == 0
    assert "a.txt" in res.stdout


def test_missing_path_with_help_uses_scan_help_not_unknown_command() -> None:
    result = CliRunner().invoke(cli, ["doesnotexist", "--help"])

    assert result.exit_code == 0
    assert "Unknown command:" not in (result.stdout + result.stderr)
    assert "--scope" in result.output


def test_debug_flag_preserves_implicit_scan(repo_root: Path) -> None:
    (repo_root / "timed.txt").write_text("timed\n", encoding="utf-8")
    result = CliRunner().invoke(
        cli,
        [
            "--debug",
            str(repo_root),
            "--stdout",
            "--summary",
            "none",
        ],
    )

    assert result.exit_code == 0
    assert "timed.txt" in result.stdout
    assert "Grobl timings:" in result.stderr
