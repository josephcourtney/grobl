from __future__ import annotations

from pathlib import Path

import pytest
import tomlkit
from click.testing import CliRunner

from grobl.cli import cli
from grobl.cli.root import main

pytestmark = pytest.mark.medium


def test_config_prune_help_documents_modes() -> None:
    result = CliRunner().invoke(cli, ["config", "prune", "--help"])

    assert result.exit_code == 0
    assert "Remove redundant canonical config entries" in result.stdout
    assert "--current-tree" in result.stdout
    assert "--stdout" in result.stdout
    assert "--check" in result.stdout
    assert "--backup" in result.stdout


def test_config_prune_writes_backup_and_removes_shadowed_rule(tmp_path: Path) -> None:
    path = tmp_path / ".grobl.toml"
    original = 'exclude = ["build", "build"]\n'
    path.write_text(original, encoding="utf-8")

    result = CliRunner().invoke(cli, ["config", "prune", str(path)])

    assert result.exit_code == 0
    assert Path(f"{path}.bak").read_text(encoding="utf-8") == original
    assert list(tomlkit.parse(path.read_text(encoding="utf-8"))["exclude"]) == ["build"]
    assert "Pruned" in result.stdout
    assert "entry" in result.stdout


def test_config_prune_stdout_does_not_modify_file(tmp_path: Path) -> None:
    path = tmp_path / ".grobl.toml"
    original = 'exclude = ["build", "build"]\n'
    path.write_text(original, encoding="utf-8")

    result = CliRunner().invoke(cli, ["config", "prune", str(path), "--stdout"])

    assert result.exit_code == 0
    assert path.read_text(encoding="utf-8") == original
    assert list(tomlkit.parse(result.stdout)["exclude"]) == ["build"]
    assert not Path(f"{path}.bak").exists()


def test_config_prune_check_exit_code_through_console_wrapper(tmp_path: Path) -> None:
    path = tmp_path / ".grobl.toml"
    path.write_text('exclude = ["build", "build"]\n', encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(["config", "prune", str(path), "--check"])

    assert excinfo.value.code == 1


def test_config_prune_rejects_legacy_policy(tmp_path: Path) -> None:
    path = tmp_path / ".grobl.toml"
    original = 'exclude_tree = ["build"]\n'
    path.write_text(original, encoding="utf-8")

    result = CliRunner().invoke(cli, ["config", "prune", str(path)])

    assert result.exit_code == 1
    assert "config migrate" in result.stderr
    assert path.read_text(encoding="utf-8") == original
