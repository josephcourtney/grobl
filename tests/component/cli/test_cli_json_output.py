from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli

pytestmark = pytest.mark.small

if TYPE_CHECKING:
    from pathlib import Path


def test_cli_format_json_pretty_and_schema(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\nworld\n", encoding="utf-8")
    # simple binary
    (tmp_path / "bin.dat").write_bytes(b"\x00\x01\x02")

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
            "none",
            "--sink",
            "stdout",
        ],
    )
    assert res.exit_code == 0
    out = res.output.strip()
    decoder = json.JSONDecoder()
    data, index = decoder.raw_decode(out)
    remainder = out[index:].strip()
    if remainder:
        summary, _ = decoder.raw_decode(remainder)
    else:
        summary = data["summary"]
    # schema basics
    assert set(data.keys()) == {"root", "scope", "summary", "tree", "files"}
    assert isinstance(data["files"], list)
    assert summary["style"] == "none"
    # determinism: keys in entries are stable
    for entry in data["files"]:
        assert "name" in entry
        assert "lines" in entry
        assert "chars" in entry
        assert "content" in entry
