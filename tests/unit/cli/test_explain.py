from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.medium


def test_explain_json_reports_content_reason(repo_root: Path) -> None:
    target = repo_root / "notes.md"
    target.write_text("hello\nworld\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, ["explain", "--format", "json", str(target)])
    assert result.exit_code == 0

    entries = json.loads(result.stdout)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["state"] == "full"
    assert entry["content"]["included"] is True
    assert entry["content"]["reason"] is None

    assert entry["tree"]["included"] is True
    assert entry["tree"]["reason"] is None


def test_explain_json_returns_text_detection(repo_root: Path) -> None:
    binary = repo_root / "binary.txt"
    binary.write_bytes(b"\x00\x01")

    runner = CliRunner()
    result = runner.invoke(cli, ["explain", "--format", "json", str(binary)])
    assert result.exit_code == 0

    entries = json.loads(result.stdout)
    assert entries[0]["content"]["included"] is False
    reason = entries[0]["content"]["reason"]
    assert reason["pattern"] == "<non-text>"
    assert entries[0]["text_detection"]["detail"] == "null byte detected"


def test_explain_include_restores_full_docs_state(repo_root: Path) -> None:
    (repo_root / "docs").mkdir()
    doc = repo_root / "docs" / "guide.md"
    doc.write_text("guide", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["explain", "--format", "json", "--include", "docs/**", "docs"],
    )
    assert result.exit_code == 0

    entries = json.loads(result.stdout)
    assert entries[0]["state"] == "full"
    assert entries[0]["content"]["included"] is True


def test_explain_preserves_local_format_when_root_options_follow_command(repo_root: Path) -> None:
    target = repo_root / "notes.md"
    target.write_text("hello\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["explain", "--format", "json", "--log-level", "DEBUG", str(target)],
    )
    assert result.exit_code == 0

    entries = json.loads(result.stdout)
    assert entries[0]["path"] == str(target)


def test_explain_applies_aggregate_budget_across_explicit_files(repo_root: Path) -> None:
    first = repo_root / "a.txt"
    second = repo_root / "b.txt"
    first.write_text("aaaa", encoding="utf-8")
    second.write_text("bbbb", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "explain",
            "--format",
            "json",
            "--max-total-bytes",
            "4",
            str(second),
            str(first),
        ],
    )

    assert result.exit_code == 0
    entries = {entry["path"]: entry for entry in json.loads(result.stdout)}
    assert entries[str(first)]["content"]["included"] is True
    assert entries[str(second)]["content"]["included"] is False
    reason = entries[str(second)]["content"]["reason"]
    assert reason["source"] == "resource-limit"
    assert "max_total_bytes exceeded" in reason["detail"]
