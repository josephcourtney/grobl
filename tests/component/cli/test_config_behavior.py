from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from grobl.cli import cli

pytestmark = pytest.mark.medium


@pytest.fixture(autouse=True)
def _isolate_external_config(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROBL_CONFIG_PATH", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(repo_root / "xdg-empty"))


def test_scan_reads_persistent_behavior_from_project_config(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("hello\n", encoding="utf-8")
    (repo_root / ".grobl.toml").write_text(
        'format = "json"\n'
        'summary = "none"\n'
        'scope = "files"\n'
        "lines = false\n"
        "tokens = false\n"
        "inclusion_status = false\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["scan", str(repo_root), "--output", "-"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["scope"] == "files"
    entry = next(item for item in payload["files"] if item["name"] == "a.txt")
    assert "lines" not in entry
    assert "tokens" not in entry
    assert "included" not in entry


def test_explicit_cli_behavior_overrides_project_config(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("hello\n", encoding="utf-8")
    (repo_root / ".grobl.toml").write_text(
        'format = "json"\nsummary = "none"\n',
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli,
        [
            "scan",
            str(repo_root),
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


def test_json_alias_overrides_persistent_format_and_summary(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("hello\n", encoding="utf-8")
    (repo_root / ".grobl.toml").write_text(
        'format = "markdown"\nsummary = "table"\n',
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["scan", str(repo_root), "--json"])

    assert result.exit_code == 0
    json.loads(result.stdout)


def test_inherit_defaults_false_disables_only_bundled_policy(repo_root: Path) -> None:
    (repo_root / "LICENSE").write_text("license body\n", encoding="utf-8")
    (repo_root / ".grobl.toml").write_text(
        'inherit_defaults = false\nsummary = "none"\n',
        encoding="utf-8",
    )
    runner = CliRunner()

    without_defaults = runner.invoke(cli, ["scan", str(repo_root), "--output", "-"])
    assert without_defaults.exit_code == 0
    assert "license body" in without_defaults.stdout

    explicit_defaults = runner.invoke(
        cli,
        [
            "scan",
            str(repo_root),
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


def test_legacy_config_warns_without_modifying(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("hello\n", encoding="utf-8")
    path = repo_root / ".grobl.toml"
    source = 'exclude_tree = ["dist"]\n'
    path.write_text(source, encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "scan",
            str(repo_root),
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


def test_explain_legacy_config_warns_without_modifying(repo_root: Path) -> None:
    target = repo_root / "a.txt"
    target.write_text("hello\n", encoding="utf-8")
    path = repo_root / ".grobl.toml"
    source = 'exclude_tree = ["dist", "dist"]\n'
    path.write_text(source, encoding="utf-8")

    result = CliRunner().invoke(cli, ["explain", "--format", "json", str(target)])

    assert result.exit_code == 0
    assert "legacy inclusion schema" in result.stderr
    json.loads(result.stdout)
    assert path.read_text(encoding="utf-8") == source
    assert not Path(f"{path}.bak").exists()


def test_cli_ignore_defaults_overrides_configured_all_policy(repo_root: Path) -> None:
    (repo_root / "LICENSE").write_text("license body\n", encoding="utf-8")
    (repo_root / ".grobl.toml").write_text(
        'ignore_policy = "all"\nsummary = "none"\n',
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli,
        ["scan", str(repo_root), "--ignore-defaults", "--output", "-"],
    )

    assert result.exit_code == 0
    assert "license body" in result.stdout


def test_invalid_persistent_behavior_is_config_error(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("hello\n", encoding="utf-8")
    (repo_root / ".grobl.toml").write_text('scope = "bogus"\n', encoding="utf-8")

    result = CliRunner().invoke(cli, ["scan", str(repo_root), "--output", "-"])

    assert result.exit_code == 3
    assert "invalid config value for 'scope'" in result.stderr


def test_scan_rejects_removed_interactive_flag(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("hello\n", encoding="utf-8")
    path = repo_root / ".grobl.toml"
    source = 'exclude_tree = ["dist"]\n'
    path.write_text(source, encoding="utf-8")

    result = CliRunner().invoke(cli, ["scan", str(repo_root), "--interactive"])

    assert result.exit_code == 2
    output = result.stdout + result.stderr
    assert "No such option" in output
    assert "--interactive" in output
    assert path.read_text(encoding="utf-8") == source
    assert not Path(f"{path}.bak").exists()


def test_bundled_policy_omits_migration_backup(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("hello\n", encoding="utf-8")
    (repo_root / ".grobl.toml.bak").write_text("legacy-secret\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["scan", str(repo_root), "--summary", "none", "--output", "-"],
    )

    assert result.exit_code == 0
    assert ".grobl.toml.bak" not in result.stdout
    assert "legacy-secret" not in result.stdout


def test_sensitive_defaults_filter_common_credential_files(repo_root: Path) -> None:
    (repo_root / ".env.local").write_text("TOKEN=secret-value\n", encoding="utf-8")
    (repo_root / ".env.example").write_text("TOKEN=template-value\n", encoding="utf-8")
    (repo_root / ".npmrc").write_text("//registry/:_authToken=npm-secret\n", encoding="utf-8")
    (repo_root / "id_ed25519").write_text("private-key-material\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["scan", str(repo_root), "--summary", "none", "--output", "-"],
    )

    assert result.exit_code == 0
    for sensitive_value in (
        "secret-value",
        "template-value",
        "npm-secret",
        "private-key-material",
    ):
        assert sensitive_value not in result.stdout


def test_explicit_include_can_restore_sensitive_named_file(repo_root: Path) -> None:
    secret = repo_root / ".env.local"
    secret.write_text("TOKEN=intentional\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "scan",
            str(repo_root),
            "--include",
            ".env.local",
            "--summary",
            "none",
            "--output",
            "-",
        ],
    )

    assert result.exit_code == 0
    assert "TOKEN=intentional" in result.stdout


def test_configured_resource_limit_can_be_disabled_explicitly(repo_root: Path) -> None:
    target = repo_root / "large.txt"
    target.write_text("hello\n", encoding="utf-8")
    (repo_root / ".grobl.toml").write_text("max_file_bytes = 1\n", encoding="utf-8")

    limited = CliRunner().invoke(cli, ["explain", "--format", "json", str(target)])
    assert limited.exit_code == 0
    limited_entry = json.loads(limited.stdout)[0]
    assert limited_entry["content"]["included"] is False
    assert limited_entry["content"]["reason"]["source"] == "resource-limit"

    unlimited = CliRunner().invoke(
        cli,
        ["explain", "--format", "json", "--max-file-bytes", "0", str(target)],
    )
    assert unlimited.exit_code == 0
    unlimited_entry = json.loads(unlimited.stdout)[0]
    assert unlimited_entry["content"]["included"] is True


def test_explain_reports_sensitive_default_provenance(repo_root: Path) -> None:
    target = repo_root / ".env.local"
    target.write_text("TOKEN=secret-value\n", encoding="utf-8")

    result = CliRunner().invoke(cli, ["explain", "--format", "json", str(target)])

    assert result.exit_code == 0
    entry = json.loads(result.stdout)[0]
    assert entry["state"] == "omit"
    assert entry["reason"]["source"] == "defaults"
    assert entry["reason"]["pattern"] == ".env.*"


def test_legacy_filename_warns_without_modifying(repo_root: Path) -> None:
    target = repo_root / "a.txt"
    target.write_text("hello\n", encoding="utf-8")
    path = repo_root / ".grobl.config.toml"
    source = 'exclude_tree = ["dist"]\n'
    path.write_text(source, encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["scan", str(repo_root), "--summary", "none", "--output", "-"],
    )

    assert result.exit_code == 0
    assert "legacy inclusion schema" in result.stderr
    assert str(path) in result.stderr
    assert path.read_text(encoding="utf-8") == source
    assert not Path(f"{path}.bak").exists()
