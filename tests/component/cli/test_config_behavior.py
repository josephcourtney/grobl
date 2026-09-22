from __future__ import annotations

import json
from pathlib import Path

import pytest
import tomlkit
from click.testing import CliRunner

from grobl.cli import cli

pytestmark = pytest.mark.medium


@pytest.fixture(autouse=True)
def _isolate_external_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROBL_CONFIG_PATH", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-empty"))


def test_scan_reads_persistent_behavior_from_project_config(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        'format = "json"\n'
        'summary = "none"\n'
        'scope = "files"\n'
        'lines = false\n'
        'tokens = false\n'
        'inclusion_status = false\n',
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["scan", str(tmp_path), "--output", "-"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["scope"] == "files"
    entry = next(item for item in payload["files"] if item["name"] == "a.txt")
    assert "lines" not in entry
    assert "tokens" not in entry
    assert "included" not in entry


def test_explicit_cli_behavior_overrides_project_config(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        'format = "json"\nsummary = "none"\n',
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli,
        [
            "scan",
            str(tmp_path),
            "--format",
            "markdown",
            "--summary",
            "none",
            "--output",
            "-",
        ],
    )

    assert result.exit_code == 0
    assert "```tree" in result.stdout


def test_json_alias_overrides_persistent_format_and_summary(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        'format = "markdown"\nsummary = "table"\n',
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["scan", str(tmp_path), "--json"])

    assert result.exit_code == 0
    json.loads(result.stdout)


def test_inherit_defaults_false_disables_only_bundled_policy(tmp_path: Path) -> None:
    (tmp_path / "LICENSE").write_text("license body\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        'inherit_defaults = false\nsummary = "none"\n',
        encoding="utf-8",
    )
    runner = CliRunner()

    without_defaults = runner.invoke(cli, ["scan", str(tmp_path), "--output", "-"])
    assert without_defaults.exit_code == 0
    assert "license body" in without_defaults.stdout

    explicit_defaults = runner.invoke(
        cli,
        [
            "scan",
            str(tmp_path),
            "--ignore-policy",
            "defaults",
            "--summary",
            "none",
            "--output",
            "-",
        ],
    )
    assert explicit_defaults.exit_code == 0
    assert "LICENSE" in explicit_defaults.stdout
    assert "license body" not in explicit_defaults.stdout


def test_noninteractive_legacy_config_warns_without_modifying(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    path = tmp_path / ".grobl.toml"
    source = 'exclude_tree = ["dist"]\n'
    path.write_text(source, encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "scan",
            str(tmp_path),
            "--no-interactive",
            "--format",
            "none",
            "--summary",
            "table",
        ],
    )

    assert result.exit_code == 0
    assert "legacy inclusion schema" in result.stderr
    assert path.read_text(encoding="utf-8") == source
    assert not Path(f"{path}.bak").exists()


def test_interactive_legacy_config_offers_migration_then_pruning(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    path = tmp_path / ".grobl.toml"
    source = 'exclude_tree = ["dist", "dist"]\n'
    path.write_text(source, encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "scan",
            str(tmp_path),
            "--interactive",
            "--format",
            "none",
            "--summary",
            "table",
        ],
        input="y\ny\nn\n",
    )

    assert result.exit_code == 0
    parsed = tomlkit.parse(path.read_text(encoding="utf-8"))
    assert "exclude_tree" not in parsed
    assert list(parsed["exclude"]) == ["dist"]
    assert Path(f"{path}.bak").read_text(encoding="utf-8") == source


def test_cli_ignore_defaults_overrides_configured_all_policy(tmp_path: Path) -> None:
    (tmp_path / "LICENSE").write_text("license body\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        'ignore_policy = "all"\nsummary = "none"\n',
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli,
        ["scan", str(tmp_path), "--ignore-defaults", "--output", "-"],
    )

    assert result.exit_code == 0
    assert "license body" in result.stdout


def test_invalid_persistent_behavior_is_config_error(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text('scope = "bogus"\n', encoding="utf-8")

    result = CliRunner().invoke(cli, ["scan", str(tmp_path), "--output", "-"])

    assert result.exit_code == 3
    assert "invalid config value for 'scope'" in result.stderr


def test_interactive_legacy_migration_can_be_declined(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    path = tmp_path / ".grobl.toml"
    source = 'exclude_tree = ["dist"]\n'
    path.write_text(source, encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "scan",
            str(tmp_path),
            "--interactive",
            "--format",
            "none",
            "--summary",
            "table",
        ],
        input="n\n",
    )

    assert result.exit_code == 0
    assert path.read_text(encoding="utf-8") == source
    assert not Path(f"{path}.bak").exists()


def test_bundled_policy_omits_migration_backup(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    (tmp_path / ".grobl.toml.bak").write_text("legacy-secret\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["scan", str(tmp_path), "--summary", "none", "--output", "-"],
    )

    assert result.exit_code == 0
    assert ".grobl.toml.bak" not in result.stdout
    assert "legacy-secret" not in result.stdout
