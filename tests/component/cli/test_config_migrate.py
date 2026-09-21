from __future__ import annotations

from pathlib import Path

import pytest
import tomlkit
from click.testing import CliRunner

from grobl.cli import cli

pytestmark = pytest.mark.medium


def test_config_migrate_help_reaches_nested_command() -> None:
    result = CliRunner().invoke(cli, ["config", "migrate", "--help"])

    assert result.exit_code == 0
    assert "Translate legacy inclusion keys" in result.stdout
    assert "--stdout" in result.stdout
    assert "--check" in result.stdout
    assert "--backup" in result.stdout


def test_config_migrate_writes_backup_and_canonical_file(tmp_path: Path) -> None:
    path = tmp_path / ".grobl.toml"
    original = 'exclude_tree = ["dist/", "build/"]\nexclude_print = ["dist/", "LICENSE*"]\n'
    path.write_text(original, encoding="utf-8")

    result = CliRunner().invoke(cli, ["config", "migrate", str(path)])

    assert result.exit_code == 0
    assert Path(f"{path}.bak").read_text(encoding="utf-8") == original
    parsed = tomlkit.parse(path.read_text(encoding="utf-8"))
    assert list(parsed["exclude"]) == ["dist/", "build/"]
    assert list(parsed["tree_only"]) == ["LICENSE*"]


def test_config_migrate_stdout_does_not_modify_file(tmp_path: Path) -> None:
    path = tmp_path / ".grobl.toml"
    original = 'exclude_tree = ["dist/"]\n'
    path.write_text(original, encoding="utf-8")

    result = CliRunner().invoke(cli, ["config", "migrate", str(path), "--stdout"])

    assert result.exit_code == 0
    assert path.read_text(encoding="utf-8") == original
    parsed = tomlkit.parse(result.stdout)
    assert list(parsed["exclude"]) == ["dist/"]
    assert not Path(f"{path}.bak").exists()


def test_config_migrate_check_reports_legacy_and_canonical(tmp_path: Path) -> None:
    path = tmp_path / ".grobl.toml"
    path.write_text('exclude_tree = ["dist/"]\n', encoding="utf-8")

    legacy = CliRunner().invoke(cli, ["config", "migrate", str(path), "--check"])
    assert legacy.exit_code == 1
    assert "uses legacy inclusion keys" in legacy.stderr

    path.write_text('exclude = ["dist/"]\n', encoding="utf-8")
    canonical = CliRunner().invoke(cli, ["config", "migrate", str(path), "--check"])
    assert canonical.exit_code == 0
    assert "already canonical" in canonical.stdout


def test_config_migrate_rejects_mixed_config_without_writing(tmp_path: Path) -> None:
    path = tmp_path / ".grobl.toml"
    original = 'exclude = ["new"]\nexclude_tree = ["old"]\n'
    path.write_text(original, encoding="utf-8")

    result = CliRunner().invoke(cli, ["config", "migrate", str(path)])

    assert result.exit_code == 1
    assert "mixes canonical and legacy" in result.stderr
    assert path.read_text(encoding="utf-8") == original
    assert not Path(f"{path}.bak").exists()
