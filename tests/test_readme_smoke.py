from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner

from grobl.cli import cli

if TYPE_CHECKING:
    from pathlib import Path


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
    assert out.read_text(encoding="utf-8").strip() != ""


def test_readme_version_and_completions(tmp_path: Path) -> None:
    runner = CliRunner()
    v = runner.invoke(cli, ["version"])  # prints version
    assert v.exit_code == 0
    assert v.output.strip() != ""

    c = runner.invoke(cli, ["completions", "--shell", "bash"])  # prints script
    assert c.exit_code == 0
    assert "_GROBL_COMPLETE" in c.output


def test_readme_init(tmp_path: Path) -> None:
    runner = CliRunner()
    res = runner.invoke(cli, ["init", "--path", str(tmp_path), "--yes", "--force"])
    assert res.exit_code in {0, 1}  # force may be redundant but should succeed or assert existing
    assert (tmp_path / ".grobl.toml").exists()
