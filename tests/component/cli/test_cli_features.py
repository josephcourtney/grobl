from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli, print_interrupt_diagnostics
from grobl.directory import DirectoryTreeBuilder

pytestmark = pytest.mark.small

if TYPE_CHECKING:
    from pathlib import Path


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


def test_non_tty_auto_sink_prefers_stdout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from grobl import output as output_mod

    monkeypatch.setattr(output_mod, "stdout_is_tty", lambda: False, raising=True)

    def explode(_: str) -> None:
        msg = "clipboard should not be used when stdout is not a TTY"
        raise AssertionError(msg)

    monkeypatch.setattr(output_mod.pyperclip, "copy", explode, raising=True)

    (tmp_path / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(tmp_path),
            "--summary",
            "none",
            "--payload",
            "json",
        ],
    )
    assert res.exit_code == 0
    assert res.output.strip().startswith("{")


def test_tty_auto_sink_prefers_clipboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from grobl import output as output_mod

    (tmp_path / "payload.txt").write_text("payload", encoding="utf-8")
    monkeypatch.setattr(output_mod, "stdout_is_tty", lambda: True, raising=True)

    captured: list[str] = []

    def fake_copy(text: str) -> None:
        captured.append(text)

    monkeypatch.setattr(output_mod.pyperclip, "copy", fake_copy, raising=True)

    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path)])

    assert res.exit_code == 0
    assert captured, "clipboard copy should be used when stdout is a TTY"
    # Payload should not leak to stdout when clipboard succeeds.
    assert "<directory" not in res.output
    assert "Total lines" in res.output


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


def test_cli_summary_json_printed_when_payload_saved(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    payload_file = tmp_path / "payload.json"
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(tmp_path),
            "--payload",
            "json",
            "--summary",
            "json",
            "--summary-style",
            "full",
            "--sink",
            "file",
            "--output",
            str(payload_file),
        ],
    )
    assert res.exit_code == 0
    assert payload_file.exists()
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    assert payload["scope"] == "all"
    summary = json.loads(res.output.strip())
    assert summary["root"] == str(tmp_path)
    assert summary["style"] == "full"


def test_cli_summary_none_suppresses_summary(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(tmp_path),
            "--payload",
            "json",
            "--summary",
            "none",
            "--sink",
            "stdout",
        ],
    )
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["scope"] == "all"
    assert "Total lines" not in res.output
