from __future__ import annotations

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


def test_layered_config_discovery_root_to_deepest_and_relative_patterns(repo_root: Path) -> None:
    _mkfile(repo_root / ".grobl.toml", "exclude_tree = ['root_excluded.txt']\nexclude_print = []\n")
    sub = repo_root / "sub"
    sub.mkdir()
    _mkfile(sub / ".grobl.toml", "exclude_tree = ['sub_excluded.txt']\nexclude_print = []\n")

    _mkfile(repo_root / "root_excluded.txt", "x\n")
    _mkfile(sub / "sub_excluded.txt", "y\n")
    _mkfile(sub / "keep.txt", "k\n")

    code, out, _ = _run([
        "scan",
        str(repo_root),
        str(sub),
        "--scope",
        "tree",
        "--summary",
        "none",
        "--output",
        "-",
    ])
    assert code == 0
    assert "root_excluded.txt" not in out
    assert "sub_excluded.txt" not in out
    assert "keep.txt" in out


def test_ignore_negation_can_reinclude_child_when_parent_excluded(repo_root: Path) -> None:
    _mkfile(
        repo_root / ".grobl.toml",
        "exclude_tree = ['parent/**', '!parent/keep.txt']\nexclude_print = []\n",
    )
    _mkfile(repo_root / "parent" / "keep.txt", "keep\n")
    _mkfile(repo_root / "parent" / "drop.txt", "drop\n")

    code, out, _ = _run(["scan", str(repo_root), "--scope", "tree", "--summary", "none", "--output", "-"])
    assert code == 0
    assert "parent/keep.txt" in out or "keep.txt" in out
    assert "drop.txt" not in out


def test_no_ignore_defaults_disables_bundled_defaults(repo_root: Path) -> None:
    venv = repo_root / ".venv"
    venv.mkdir()
    _mkfile(venv / "inner.txt", "x\n")

    runner = CliRunner()
    res1 = runner.invoke(
        cli,
        ["scan", str(repo_root), "--scope", "tree", "--summary", "none", "--output", "-"],
    )
    assert res1.exit_code == 0

    res2 = runner.invoke(
        cli,
        [
            "scan",
            str(repo_root),
            "--no-ignore-defaults",
            "--scope",
            "tree",
            "--summary",
            "none",
            "--output",
            "-",
        ],
    )
    assert res2.exit_code == 0
    assert ".venv/" in res2.stdout


def test_no_ignore_config_disables_all_grobl_toml_rules(repo_root: Path) -> None:
    _mkfile(repo_root / ".grobl.toml", "exclude_tree = ['blocked.txt']\nexclude_print = []\n")
    _mkfile(repo_root / "blocked.txt", "x\n")

    code1, out1, _ = _run(["scan", str(repo_root), "--scope", "tree", "--summary", "none", "--output", "-"])
    assert code1 == 0
    assert "blocked.txt" not in out1

    code2, out2, _ = _run([
        "scan",
        str(repo_root),
        "--no-ignore-config",
        "--scope",
        "tree",
        "--summary",
        "none",
        "--output",
        "-",
    ])
    assert code2 == 0
    assert "blocked.txt" in out2


@pytest.mark.parametrize("flag", ["--no-ignore-defaults", "--no-ignore-config"])
def test_ignore_control_flags_are_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: str
) -> None:
    monkeypatch.chdir(tmp_path)
    _mkfile(tmp_path / "a.txt", "a\n")
    code, _out, _ = _run([
        "scan",
        str(tmp_path),
        flag,
        "--scope",
        "tree",
        "--summary",
        "none",
        "--output",
        "-",
    ])
    assert code == 0
