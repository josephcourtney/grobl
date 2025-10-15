"""Integration tests for the grobl CLI commands."""

from __future__ import annotations

import io
import sys
from typing import TYPE_CHECKING

import grobl_cli.output as output_module
from click.testing import CliRunner
from grobl_cli import tty
from grobl_cli.cli import cli
from grobl_cli.cli.scan import scan as scan_cmd

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_summary_mode_writes_to_file(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    out_path = tmp_path / "out.txt"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["scan", "--mode", "summary", "--output", str(out_path), str(tmp_path)],
    )
    assert result.exit_code == 0
    assert out_path.read_text(encoding="utf-8")
    assert "Total lines" in result.output


def test_cli_scan_accepts_file_path(tmp_path: Path) -> None:
    target = tmp_path / "solo.txt"
    target.write_text("hello\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, ["scan", str(target), "--mode", "summary"])
    assert result.exit_code == 0


def test_completions_command_outputs_script() -> None:
    runner = CliRunner()
    res = runner.invoke(cli, ["completions", "--shell", "bash"])
    assert res.exit_code == 0
    assert "_GROBL_COMPLETE" in res.output
    zsh_res = runner.invoke(cli, ["completions", "--shell", "zsh"])
    assert zsh_res.exit_code == 0
    assert 'eval "$(env _GROBL_COMPLETE=zsh_source grobl)"' in zsh_res.output


def test_non_tty_disables_clipboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyStdout(io.StringIO):
        def isatty(self) -> bool:  # type: ignore[override]
            return False

    monkeypatch.setattr(sys, "stdout", DummyStdout())
    (tmp_path / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path), "--mode", "summary"])
    assert res.exit_code == 0


def test_auto_table_compact_when_not_tty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tty, "stdout_is_tty", lambda: False)
    (tmp_path / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path), "--mode", "summary", "--table", "auto"])
    assert res.exit_code == 0
    out = res.output
    assert "Total lines:" in out
    assert " Project Summary " not in out


def test_cli_flags_matrix_smoke(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(tmp_path),
            "--mode",
            "all",
            "--table",
            "compact",
            "--no-clipboard",
            "--add-ignore",
            "*.ignoreme",
            "--remove-ignore",
            "*.ignoreme",
            "--format",
            "human",
        ],
    )
    assert res.exit_code == 0


def test_explicit_full_table_even_when_not_tty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tty, "stdout_is_tty", lambda: False)
    (tmp_path / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["scan", str(tmp_path), "--mode", "summary", "--table", "full", "--no-clipboard"],
    )
    assert res.exit_code == 0
    assert " Project Summary " in res.output


def test_defaults_to_summary_on_tty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tty, "stdout_is_tty", lambda: True)
    monkeypatch.setattr(scan_cmd, "stdout_is_tty", lambda: True)
    monkeypatch.setattr(
        output_module,
        "clipboard_allowed",
        lambda _cfg, *, no_clipboard_flag: False,
    )
    (tmp_path / "a.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path)])
    assert res.exit_code == 0
    assert " Project Summary " in res.output
    assert "<directory" not in res.output


def test_quiet_suppresses_summary_output(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["scan", str(tmp_path), "--mode", "summary", "--quiet", "--no-clipboard"],
    )
    assert res.exit_code == 0
    assert not res.output.strip()


def test_init_writes_nicely_formatted_config(tmp_path: Path) -> None:
    runner = CliRunner()
    res = runner.invoke(cli, ["init", "--path", str(tmp_path), "--force"])
    assert res.exit_code == 0
    text = (tmp_path / ".grobl.toml").read_text(encoding="utf-8")
    assert "exclude_tree = [" in text
    assert '\n  ".venv",\n' in text or '\n  ".venv"\n' in text
