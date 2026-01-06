from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl.cli import cli

pytestmark = pytest.mark.small


if TYPE_CHECKING:
    from pathlib import Path


def _mkfile(p: Path, text: str = "x\n") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _run(args: list[str]) -> tuple[int, str, str]:
    runner = CliRunner()
    res = runner.invoke(cli, args)
    return res.exit_code, res.stdout, res.stderr


def test_deterministic_ordering_is_repo_root_relative_and_case_folded(repo_root: Path) -> None:
    _mkfile(repo_root / "B.txt", "b\n")
    _mkfile(repo_root / "a.txt", "a\n")

    code, out, _ = _run(["scan", str(repo_root), "--scope", "tree", "--summary", "none", "--output", "-"])
    assert code == 0

    idx_a = out.lower().find("a.txt")
    idx_b = out.lower().find("b.txt")
    assert idx_a != -1
    assert idx_b != -1
    assert idx_a < idx_b


def test_path_separators_normalized_to_posix(repo_root: Path) -> None:
    sub = repo_root / "subdir"
    sub.mkdir()
    _mkfile(sub / "x.txt", "x\n")

    code, out, _ = _run([
        "scan",
        str(repo_root),
        "--scope",
        "tree",
        "--summary",
        "none",
        "--format",
        "json",
        "--output",
        "-",
    ])
    assert code == 0
    payload = json.loads(out)
    for entry in payload.get("tree", []):
        p = entry.get("path")
        if isinstance(p, str):
            assert "\\" not in p


def test_json_output_is_stable_across_runs_and_has_trailing_newline(repo_root: Path) -> None:
    _mkfile(repo_root / "a.txt", "hello\n")

    args = ["scan", str(repo_root), "--format", "json", "--summary", "none", "--output", "-"]

    code1, out1, err1 = _run(args)
    code2, out2, err2 = _run(args)

    assert code1 == 0
    assert code2 == 0
    assert not err1
    assert not err2
    assert out1.endswith("\n")
    assert out2.endswith("\n")
    assert out1 == out2
    json.loads(out1)


def test_ndjson_output_is_one_record_per_line_and_trailing_newline_and_stable(repo_root: Path) -> None:
    _mkfile(repo_root / "a.txt", "a\n")
    _mkfile(repo_root / "b.txt", "b\n")

    args = ["scan", str(repo_root), "--format", "ndjson", "--summary", "none", "--output", "-"]

    code1, out1, err1 = _run(args)
    code2, out2, err2 = _run(args)

    assert code1 == 0
    assert code2 == 0
    assert not err1
    assert not err2
    assert out1.endswith("\n")
    assert out2.endswith("\n")
    assert out1 == out2

    lines = out1.splitlines()
    assert lines, "expected at least one NDJSON record"
    for ln in lines:
        obj = json.loads(ln)
        assert isinstance(obj, dict)
