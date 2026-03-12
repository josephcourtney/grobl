from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli

pytestmark = pytest.mark.small

if TYPE_CHECKING:
    from pathlib import Path


def test_summary_scope_choice_is_rejected(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("hello", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "--scope", "summary", str(repo_root)])
    assert result.exit_code != 0
    assert "Invalid value for '--scope'" in result.output


@pytest.mark.parametrize(
    ("shell", "expected_substrings"),
    [
        ("bash", ("_GROBL_COMPLETE", "bash_source", "complete -F")),
        ("zsh", ("_GROBL_COMPLETE", "zsh_source", "compinit")),
        ("fish", ("_GROBL_COMPLETE", "fish_source")),
    ],
)
def test_completions_command_outputs_script(shell: str, expected_substrings: tuple[str, ...]) -> None:
    runner = CliRunner()
    res = runner.invoke(cli, ["completions", "--shell", shell])
    assert res.exit_code == 0
    for s in expected_substrings:
        assert s in res.output


def test_auto_table_compact_when_not_tty(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force TTY helper to return False regardless of Click's runner internals
    from grobl import tty

    monkeypatch.setattr(tty, "stdout_is_tty", lambda: False)
    (repo_root / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(repo_root), "--summary", "table", "--summary-style", "auto"])
    assert res.exit_code == 0
    summary_out = res.stderr
    # compact table prints simple totals; full table includes a title with spaces around
    assert "Total lines:" in summary_out
    assert " Project Summary " not in summary_out


def test_scan_rejects_empty_work(repo_root: Path) -> None:
    (repo_root / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(repo_root), "--format", "none", "--summary", "none"])
    assert res.exit_code != 0
    assert "nothing to do" in res.output
    assert "Traceback" not in res.output


def test_scan_json_alias_emits_json_to_stdout(repo_root: Path) -> None:
    (repo_root / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(repo_root), "--json"])
    assert res.exit_code == 0
    assert '"files"' in res.stdout
    assert "Total lines:" not in res.stdout


def test_scan_stdout_alias_writes_payload_to_stdout(repo_root: Path) -> None:
    (repo_root / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(repo_root), "--stdout", "--summary", "none"])
    assert res.exit_code == 0
    assert "<directory" in res.stdout


def test_human_summary_notes_omitted_files(repo_root: Path) -> None:
    (repo_root / "LICENSE").write_text("license text\n", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(repo_root), "--summary", "table", "--format", "none"])
    assert res.exit_code == 0
    assert "file contents omitted" in res.stderr
    assert "grobl explain <path>" in res.stderr


def test_scan_metadata_visibility_flags_filter_json_output(repo_root: Path) -> None:
    import json

    (repo_root / "f.txt").write_text("data\n", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(repo_root),
            "--format",
            "json",
            "--summary",
            "none",
            "--output",
            "-",
            "--no-lines",
            "--no-tokens",
            "--no-inclusion-status",
        ],
    )
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    file_entry = payload["files"][0]
    assert "chars" in file_entry
    assert "lines" not in file_entry
    assert "tokens" not in file_entry
    assert "included" not in file_entry
    totals = payload["summary"]["totals"]
    assert "total_characters" in totals
    assert "total_lines" not in totals
    assert "total_tokens" not in totals
