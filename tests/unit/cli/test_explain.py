from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.small


def test_explain_json_reports_content_reason(repo_root: Path) -> None:
    target = repo_root / "notes.md"
    target.write_text("hello\nworld\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, ["explain", "--format", "json", str(target)])
    assert result.exit_code == 0

    entries = json.loads(result.stdout)
    assert len(entries) == 1
    entry = entries[0]
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


def test_explain_include_content_overrides_docs(repo_root: Path) -> None:
    (repo_root / "docs").mkdir()
    doc = repo_root / "docs" / "guide.md"
    doc.write_text("guide", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["explain", "--format", "json", "--include-content", "docs/**", "docs"],
    )
    assert result.exit_code == 0

    entries = json.loads(result.stdout)
    assert entries[0]["content"]["included"] is True
