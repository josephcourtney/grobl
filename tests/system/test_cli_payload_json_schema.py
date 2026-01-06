from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.small


@pytest.mark.parametrize(
    ("scope", "expect_tree", "expect_files"),
    [
        ("tree", True, False),
        ("files", False, True),
        ("all", True, True),
    ],
)
def test_json_payload_schema_by_scope(
    repo_root: Path, scope: str, *, expect_tree: bool, expect_files: bool
) -> None:
    (repo_root / "dir").mkdir()
    (repo_root / "dir" / "a.txt").write_text("aa\n", encoding="utf-8")

    res = CliRunner().invoke(
        cli,
        ["scan", str(repo_root), "--scope", scope, "--format", "json", "--summary", "none", "--output", "-"],
    )
    assert res.exit_code == 0
    assert res.stdout.endswith("\n")

    data = json.loads(res.stdout)
    assert set(data.keys()) == {"root", "scope", "summary", "tree", "files"}
    assert data["root"] == str(repo_root)
    assert data["scope"] == scope

    # Summary basics (schema-lite)
    assert isinstance(data["summary"], dict)
    assert "totals" in data["summary"]
    assert isinstance(data["summary"].get("files", []), list)

    # Tree/files presence by scope
    assert isinstance(data["tree"], list)
    assert isinstance(data["files"], list)

    if expect_tree:
        assert data["tree"], "expected non-empty tree for this scope"
    else:
        assert data["tree"] == []

    if expect_files:
        assert data["files"], "expected non-empty files list for this scope"
        for entry in data["files"]:
            # stable keys for entries
            assert {"name", "path", "lines", "chars", "included", "content"} <= set(entry.keys())
    else:
        assert data["files"] == []
