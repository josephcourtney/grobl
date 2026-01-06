from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from grobl.cli import cli

pytestmark = pytest.mark.medium


def test_readme_scan_quick_start(repo_root: Path) -> None:
    # README suggests: grobl (defaults to scan current dir). We emulate with explicit path.
    (repo_root / "a.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(repo_root),
            "--scope",
            "tree",
            "--summary",
            "table",
            "--output",
            "-",
        ],
    )
    assert res.exit_code == 0


def test_readme_output_to_file(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("data", encoding="utf-8")
    out = repo_root / "context.txt"
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(repo_root), "--output", str(out)])
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
    assert res.exit_code == 0
    assert (tmp_path / ".grobl.toml").exists()


def test_readme_documents_scan_flags() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    assert "--scope {all,tree,files}" in text
    assert "--format {llm,markdown,json,ndjson,none}" in text
    assert "--summary {auto,none,table,json}" in text
    assert "--summary-style {auto,full,compact}" in text
    assert "--summary-to {stderr,stdout,file}" in text
    assert "--summary-output PATH" in text
    assert "--copy" in text
    assert "--output PATH" in text
    assert "--ignore-policy {auto,all,none,defaults,config,cli}" in text
    assert "--mode" not in text
