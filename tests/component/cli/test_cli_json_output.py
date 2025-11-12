from __future__ import annotations

import json
from typing import TYPE_CHECKING

from click.testing import CliRunner

from grobl.cli import cli

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
            "--mode",
            "summary",
            "--format",
            "json",
        ],
    )
    assert res.exit_code == 0
    out = res.output.strip()
    # pretty printed: indented and multi-line
    assert out.startswith("{\n  ")
    assert '\n  "files": [' in out

    data = json.loads(out)
    # schema basics
    assert set(data.keys()) == {"root", "mode", "table", "totals", "files"}
    assert isinstance(data["files"], list)
    # determinism: keys in entries are stable
    for entry in data["files"]:
        assert "path" in entry
        assert "lines" in entry
        assert "chars" in entry
        assert "included" in entry
