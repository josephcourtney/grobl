from __future__ import annotations

import io
import sys
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import _maybe_offer_legacy_migration, cli, print_interrupt_diagnostics
from grobl.constants import EXIT_INTERRUPT
from grobl.directory import DirectoryTreeBuilder

if TYPE_CHECKING:
    from pathlib import Path


def test_warn_on_summary_table_none(tmp_path: Path, monkeypatch: object) -> None:
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "--mode", "summary", "--table", "none", str(tmp_path)])
    assert result.exit_code == 0
    assert "warning: --mode summary with --table none" in result.output


def test_completions_command_outputs_script() -> None:
    runner = CliRunner()
    res = runner.invoke(cli, ["completions", "--shell", "bash"])
    assert res.exit_code == 0
    assert "_GROBL_COMPLETE" in res.output
    zsh_res = runner.invoke(cli, ["completions", "--shell", "zsh"])
    assert zsh_res.exit_code == 0
    assert 'eval "$(env _GROBL_COMPLETE=zsh_source grobl)"' in zsh_res.output


def test_legacy_migration_renames_file(tmp_path: Path) -> None:
    legacy = tmp_path / ".grobl.config.toml"
    legacy.write_text("exclude_tree=['x']\n", encoding="utf-8")
    # Create a file referencing the legacy name
    (tmp_path / "README.md").write_text("see .grobl.config.toml", encoding="utf-8")
    _maybe_offer_legacy_migration(tmp_path, assume_yes=True)
    assert not legacy.exists()
    assert (tmp_path / ".grobl.toml").exists()


def test_interrupt_diagnostics_exit_code(tmp_path: Path) -> None:
    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    with pytest.raises(SystemExit) as excinfo:
        print_interrupt_diagnostics(tmp_path, {"exclude_tree": []}, builder)
    exc = excinfo.value
    assert isinstance(exc, SystemExit)
    assert exc.code == EXIT_INTERRUPT


def test_non_tty_disables_clipboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force non-tty for stdout
    class DummyStdout(io.StringIO):
        def isatty(self) -> bool:  # type: ignore[override]
            return False

    monkeypatch.setattr(sys, "stdout", DummyStdout())
    (tmp_path / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    # If clipboard were used, we'd not see output; ensure command still succeeds.
    res = runner.invoke(cli, ["scan", str(tmp_path), "--mode", "summary"])
    assert res.exit_code == 0


def test_auto_table_compact_when_not_tty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force TTY helper to return False regardless of Click's runner internals
    from grobl import tty

    monkeypatch.setattr(tty, "stdout_is_tty", lambda: False)
    (tmp_path / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path), "--mode", "summary", "--table", "auto"])
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
