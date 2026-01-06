from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl import tty
from grobl.cli import cli, print_interrupt_diagnostics
from grobl.cli import scan as cli_scan
from grobl.directory import DirectoryTreeBuilder

pytestmark = pytest.mark.small

if TYPE_CHECKING:
    from pathlib import Path


def test_summary_scope_choice_is_rejected(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("hello", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "--scope", "summary", str(repo_root)])
    assert result.exit_code != 0
    assert "Invalid value for '--scope'" in result.output


def test_cli_scan_accepts_file_path(repo_root: Path) -> None:
    target = repo_root / "solo.txt"
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


def test_non_tty_auto_sink_prefers_stdout(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from grobl import output as output_mod

    monkeypatch.setattr(cli_scan, "stdout_is_tty", lambda: False, raising=True)

    def explode(_: str) -> None:
        msg = "clipboard should not be used when stdout is not a TTY"
        raise AssertionError(msg)

    monkeypatch.setattr(output_mod.pyperclip, "copy", explode, raising=True)

    (repo_root / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(repo_root),
            "--summary",
            "none",
            "--format",
            "json",
            "--output",
            "-",
        ],
    )
    assert res.exit_code == 0
    assert res.output.strip().startswith("{")


def test_tty_auto_sink_prefers_clipboard(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from grobl import output as output_mod

    (repo_root / "payload.txt").write_text("payload", encoding="utf-8")
    monkeypatch.setattr(cli_scan, "stdout_is_tty", lambda: True, raising=True)
    monkeypatch.setattr(tty, "stdout_is_tty", lambda: True, raising=True)

    captured: list[str] = []

    def fake_copy(text: str) -> None:
        captured.append(text)

    monkeypatch.setattr(output_mod.pyperclip, "copy", fake_copy, raising=True)

    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(repo_root)])

    assert res.exit_code == 0
    assert captured, "clipboard copy should be used when stdout is a TTY"
    # Payload should not leak to stdout when clipboard succeeds.
    assert "<directory" not in res.stdout
    assert "Total lines" in res.stderr


def test_auto_table_compact_when_not_tty(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force TTY helper to return False regardless of Click's runner internals
    from grobl import tty

    monkeypatch.setattr(tty, "stdout_is_tty", lambda: False)
    (repo_root / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(repo_root), "--summary", "table", "--summary-style", "auto"])
    assert res.exit_code == 0
    assert not res.stdout
    summary_out = res.stderr
    # compact table prints simple totals; full table includes a title with spaces around
    assert "Total lines:" in summary_out
    assert " Project Summary " not in summary_out


def test_cli_summary_json_printed_when_payload_saved(repo_root: Path) -> None:
    (repo_root / "x.txt").write_text("x", encoding="utf-8")
    payload_file = repo_root / "payload.json"
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(repo_root),
            "--format",
            "json",
            "--summary",
            "json",
            "--output",
            str(payload_file),
        ],
    )
    assert res.exit_code == 0
    assert payload_file.exists()
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    assert payload["scope"] == "all"
    summary = json.loads(res.stderr.strip())
    assert summary["root"] == str(repo_root)
    assert summary["style"] == "auto"


def test_summary_auto_suppresses_when_stdout_not_tty(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from grobl import tty

    monkeypatch.setattr(tty, "stdout_is_tty", lambda: False, raising=True)
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(repo_root)])
    assert res.exit_code == 0
    assert not res.stderr
