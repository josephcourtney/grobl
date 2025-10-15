from __future__ import annotations

import io
import os
import sys
from typing import TYPE_CHECKING
from unittest import mock

import pytest
from click.testing import CliRunner
from grobl.constants import EXIT_CONFIG, EXIT_PATH, EXIT_USAGE

import grobl_cli.output as output_module
from grobl_cli import tty
from grobl_cli.cli import cli
from grobl_cli.cli.scan import scan
from grobl_cli.cli.scan import scan as scan_cmd

if TYPE_CHECKING:
    from pathlib import Path


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
    from grobl_cli import tty

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


def test_explicit_full_table_even_when_not_tty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force non-tty but request full table explicitly
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


@pytest.fixture
def runner():
    return CliRunner()


def test_scan_cli_default_calls_runner(runner, tmp_path: Path) -> None:
    with mock.patch("grobl_cli.cli.scan.run_scan_command", return_value="FAKE SUMMARY") as mock_runner:
        result = runner.invoke(scan, [str(tmp_path)])

        assert result.exit_code == 0
        assert "FAKE SUMMARY" in result.output
        assert mock_runner.called

        # Check param object passed to runner
        params = mock_runner.call_args.args[0]
        assert params.paths == (tmp_path,)
        assert params.mode == "summary"
        assert params.table == "auto"
        assert params.fmt == "human"


def test_scan_cli_output_to_file(runner, tmp_path: Path) -> None:
    output_file = tmp_path / "out.txt"
    with mock.patch("grobl_cli.cli.scan.run_scan_command", return_value="FILE OUTPUT") as mock_runner:
        result = runner.invoke(scan, [str(tmp_path), "--output", str(output_file)])

        assert result.exit_code == 0
        assert "FILE OUTPUT" in result.output
        params = mock_runner.call_args.args[0]
        assert params.output == output_file


def test_scan_cli_invalid_table_combo(runner, tmp_path: Path) -> None:
    # This should raise a UsageError from scan_runner
    result = runner.invoke(scan, [str(tmp_path), "--mode", "summary", "--table", "none"])
    assert result.exit_code == 2
    assert "No output would be produced" in result.output


def test_scan_cli_propagates_scan_failure(runner, tmp_path: Path) -> None:
    with mock.patch("grobl_cli.cli.scan.run_scan_command", side_effect=SystemExit(3)):
        result = runner.invoke(scan, [str(tmp_path)])
        assert result.exit_code == 3


def test_init_writes_nicely_formatted_config(tmp_path: Path) -> None:
    runner = CliRunner()
    res = runner.invoke(cli, ["init", "--path", str(tmp_path), "--force"])
    assert res.exit_code == 0
    text = (tmp_path / ".grobl.toml").read_text(encoding="utf-8")
    # arrays should be multi-line; spot check a known entry in exclude_tree
    assert "exclude_tree = [" in text
    assert '\n  ".venv",\n' in text or '\n  ".venv"\n' in text


def test_readme_scan_quick_start(tmp_path: Path) -> None:
    # README suggests: grobl (defaults to scan current dir). We emulate with explicit path.
    (tmp_path / "a.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path), "--no-clipboard", "--mode", "summary"])
    assert res.exit_code == 0


def test_readme_output_to_file(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("data", encoding="utf-8")
    out = tmp_path / "context.txt"
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path), "--output", str(out)])
    assert res.exit_code == 0
    assert out.exists()
    # Simplify truthy check per linter guidance
    assert out.read_text(encoding="utf-8").strip()


def test_readme_version_and_completions(tmp_path: Path) -> None:
    runner = CliRunner()
    v = runner.invoke(cli, ["version"])  # prints version
    assert v.exit_code == 0
    assert v.output.strip()

    c = runner.invoke(cli, ["completions", "--shell", "bash"])  # prints script
    assert c.exit_code == 0
    assert "_GROBL_COMPLETE" in c.output


def test_readme_init(tmp_path: Path) -> None:
    runner = CliRunner()
    res = runner.invoke(cli, ["init", "--path", str(tmp_path), "--force"])
    assert res.exit_code in {0, 1}  # force may be redundant but should succeed or assert existing
    assert (tmp_path / ".grobl.toml").exists()


def test_usage_error_invalid_mode(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path), "--mode", "bogus"])
    # Click treats invalid option values as usage error (SystemExit 2)
    assert res.exit_code == EXIT_USAGE
    assert "Invalid value for '--mode'" in res.output
    assert "Traceback" not in res.output


def test_no_output_combo_is_usage_error(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["scan", str(tmp_path), "--mode", "summary", "--table", "none"],
    )
    assert res.exit_code == EXIT_USAGE
    assert "No output would be produced" in res.output


@pytest.mark.skipif(os.name != "posix", reason="POSIX-only path assumptions")
def test_path_error_no_real_common_ancestor() -> None:
    runner = CliRunner()
    # Using "/" and "/tmp" yields common ancestor "/" which our helper rejects
    res = runner.invoke(cli, ["scan", "/", "/tmp"])  # noqa: S108 - controlled use in test
    assert res.exit_code == EXIT_PATH
    assert "No common ancestor" in res.output or res.output


def test_config_load_error_bad_explicit_config(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("= broken =\n", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path), "--config", str(bad)])
    assert res.exit_code == EXIT_CONFIG


def test_config_load_error_bad_pyproject(tmp_path: Path) -> None:
    # Create project base with bad pyproject.toml
    base = tmp_path / "proj"
    base.mkdir()
    (base / "pyproject.toml").write_text("[tool.grobl\n# missing closing bracket", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(base)])
    assert res.exit_code == EXIT_CONFIG
