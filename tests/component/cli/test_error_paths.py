from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from grobl.cli import cli
from grobl.constants import EXIT_CONFIG, EXIT_USAGE

pytestmark = pytest.mark.small


def test_usage_error_invalid_scope(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path), "--scope", "bogus"])
    # Click treats invalid option values as usage error (SystemExit 2)
    assert res.exit_code == EXIT_USAGE


@pytest.mark.skipif(os.name != "posix", reason="POSIX-only path assumptions")
def test_path_accepts_filesystem_root_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, Path] = {}

    def fake_load_and_adjust_config(**kwargs: object) -> dict[str, object]:
        base_path = kwargs.get("base_path")
        assert isinstance(base_path, Path)
        observed["base_path"] = base_path
        return {}

    monkeypatch.setattr("grobl.cli.scan.load_and_adjust_config", fake_load_and_adjust_config)
    monkeypatch.setattr("grobl.cli.scan.build_writer_from_config", lambda **_: lambda _text: None)
    monkeypatch.setattr("grobl.cli.scan.resolve_table_style", lambda style: style)
    monkeypatch.setattr("grobl.cli.scan._execute_with_handling", lambda **_: ("", {}))

    runner = CliRunner()
    res = runner.invoke(cli, ["scan", "/", "/tmp"])  # noqa: S108 - controlled use in test
    assert res.exit_code == 0
    assert observed["base_path"] == Path("/")


def test_config_load_error_bad_explicit_config(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("= broken =\n", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path), "--config", str(bad)])
    assert res.exit_code == EXIT_CONFIG


def test_config_load_error_bad_pyproject(tmp_path: Path) -> None:
    # Create project base with bad pyproject.toml
    base = tmp_path / "proj"
    base.mkdir()
    (base / "pyproject.toml").write_text("[tool.grobl\n# missing closing bracket", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(base)])
    assert res.exit_code == EXIT_CONFIG


def test_config_load_error_missing_explicit_config(tmp_path: Path) -> None:
    missing = tmp_path / "missing.toml"
    runner = CliRunner()
    res = runner.invoke(cli, ["scan", str(tmp_path), "--config", str(missing)])
    assert res.exit_code == EXIT_CONFIG
    assert "missing.toml" in res.output
