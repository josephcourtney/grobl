from __future__ import annotations

import io
import sys
from typing import TYPE_CHECKING

from click.testing import CliRunner

from grobl.cli import cli, print_interrupt_diagnostics
from grobl.directory import DirectoryTreeBuilder

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_summary_scope_choice_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "--scope", "summary", str(tmp_path)])
    assert result.exit_code != 0
    assert "Invalid value for '--scope'" in result.output


def test_cli_scan_accepts_file_path(tmp_path: Path) -> None:
    target = tmp_path / "solo.txt"
    target.write_text("hello\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, ["scan", str(target)])
    assert result.exit_code == 0


def test_completions_command_outputs_script() -> None:
    runner = CliRunner()
    res = runner.invoke(cli, ["completions", "--shell", "bash"])
    assert res.exit_code == 0
    assert "_GROBL_COMPLETE" in res.output
    zsh_res = runner.invoke(cli, ["completions", "--shell", "zsh"])
    assert zsh_res.exit_code == 0
    assert 'eval "$(env _GROBL_COMPLETE=zsh_source grobl)"' in zsh_res.output


def test_interrupt_diagnostics_prints_debug_info(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    print_interrupt_diagnostics(tmp_path, {"exclude_tree": []}, builder)

    captured = capsys.readouterr()
    out = captured.out
    assert "Interrupted by user. Dumping debug info:" in out
    assert f"cwd: {tmp_path}" in out
    assert "exclude_tree: []" in out
    assert "DirectoryTreeBuilder(" in out


def test_non_tty_disables_clipboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force non-tty for stdout
    class DummyStdout(io.StringIO):
        def isatty(self) -> bool:  # type: ignore[override]
            return False

    monkeypatch.setattr(sys, "stdout", DummyStdout())
    (tmp_path / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    # If clipboard were used, we'd not see output; ensure command still succeeds.
    res = runner.invoke(cli, ["scan", str(tmp_path)])
    assert res.exit_code == 0


def test_auto_table_compact_when_not_tty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force TTY helper to return False regardless of Click's runner internals
    from grobl import tty

    monkeypatch.setattr(tty, "stdout_is_tty", lambda: False)
    (tmp_path / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path), "--summary-style", "auto"])
    assert res.exit_code == 0
    out = res.output
    # compact table prints simple totals; full table includes a title with spaces around
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
            "--scope",
            "all",
            "--summary-style",
            "compact",
            "--sink",
            "stdout",
            "--add-ignore",
            "*.ignoreme",
            "--remove-ignore",
            "*.ignoreme",
            "--summary",
            "human",
            "--payload",
            "json",
        ],
    )
    assert res.exit_code == 0


def test_cli_requires_some_output(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(tmp_path),
            "--payload",
            "none",
            "--summary",
            "none",
        ],
    )
    assert res.exit_code != 0
    assert "payload and summary" in res.output


def test_cli_sink_file_requires_output(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(tmp_path),
            "--sink",
            "file",
        ],
    )
    assert res.exit_code != 0
    assert "--output" in res.output
