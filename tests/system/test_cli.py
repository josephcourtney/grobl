from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from grobl import tty
from grobl.cli import cli
from grobl.cli import scan as cli_scan
from grobl.constants import EXIT_USAGE

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.medium


def test_cli_help_and_scan_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output

    scan_help = runner.invoke(cli, ["scan", "--help"])
    assert scan_help.exit_code == 0
    # Spot-check that key options are documented
    assert "--scope" in scan_help.output
    assert "--format" in scan_help.output
    assert "--summary" in scan_help.output


@pytest.mark.skipif(os.name != "posix", reason="POSIX-only filesystem root semantics")
def test_cli_scan_accepts_filesystem_root(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, Path] = {}

    def fake_load_config(**kwargs: object) -> dict[str, object]:
        base_path = kwargs.get("base_path")
        assert isinstance(base_path, Path)
        observed["base_path"] = base_path
        return {}

    monkeypatch.setattr("grobl.cli.scan.load_config", fake_load_config)
    monkeypatch.setattr("grobl.cli.scan.build_writer_from_config", lambda **_: lambda _text: None)
    monkeypatch.setattr("grobl.cli.scan.resolve_table_style", lambda style: style)
    monkeypatch.setattr("grobl.cli.scan._execute_with_handling", lambda **_: ("", {}))

    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "/"])

    assert result.exit_code != 0
    assert "scan paths must be within the resolved repository root" in result.output


def test_cli_root_invocation_forwards_scan_options(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROBL_CONFIG_PATH", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(repo_root / "xdg-empty"))

    base = repo_root / "proj"
    base.mkdir()
    (base / "src").mkdir()
    (base / "src" / "keep.txt").write_text("keep\n", encoding="utf-8")
    (base / "tests").mkdir()
    (base / "tests" / "skip.txt").write_text("skip\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--scope",
            "tree",
            "--summary",
            "none",
            "--output",
            "-",
            "--ignore-defaults",
            "--add-ignore",
            "tests",
            str(base),
        ],
    )

    assert result.exit_code == 0
    out = result.output
    assert "src/" in out
    assert "tests/" not in out


def test_cli_default_scan_outputs_summary_and_payload(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (repo_root / "sample.txt").write_text("content\n", encoding="utf-8")
    runner = CliRunner()
    monkeypatch.setattr(tty, "stdout_is_tty", lambda: True, raising=True)
    monkeypatch.setattr(cli_scan, "stdout_is_tty", lambda: True, raising=True)
    result = runner.invoke(cli, ["scan", str(repo_root)])
    assert result.exit_code == 0
    assert not result.stdout
    assert "Total lines" in result.stderr
    assert "test_cli_default_scan_outputs_0/" in result.stderr


def test_cli_multiple_paths_uses_common_ancestor_in_json_root(repo_root: Path) -> None:
    base = repo_root / "proj"
    a_dir = base / "a"
    b_dir = base / "b"
    a_dir.mkdir(parents=True)
    b_dir.mkdir(parents=True)
    (a_dir / "one.txt").write_text("1\n", encoding="utf-8")
    (b_dir / "two.txt").write_text("2\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "scan",
            str(a_dir),
            str(b_dir),
            "--summary",
            "json",
            "--format",
            "none",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    # Common ancestor of a/ and b/ should be the project root
    assert data["root"] == str(base)


def test_cli_modes_human_payload_variants(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Isolate from any user/global grobl config
    monkeypatch.delenv("GROBL_CONFIG_PATH", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(repo_root / "xdg-empty"))

    base = repo_root / "proj"
    base.mkdir()
    (base / "x.txt").write_text("x\n", encoding="utf-8")

    runner = CliRunner()
    common_args = [
        "scan",
        str(base),
        "--output",
        "-",
        "--summary",
        "none",
    ]

    # mode=all → tree + files payload
    res_all = runner.invoke(cli, [*common_args, "--scope", "all"])
    assert res_all.exit_code == 0
    out_all = res_all.output
    assert "<directory" in out_all
    assert "<file" in out_all

    # mode=tree → only tree payload
    res_tree = runner.invoke(cli, [*common_args, "--scope", "tree"])
    assert res_tree.exit_code == 0
    out_tree = res_tree.output
    assert "<directory" in out_tree
    assert "<file" not in out_tree

    # mode=files → only file payload
    res_files = runner.invoke(cli, [*common_args, "--scope", "files"])
    assert res_files.exit_code == 0
    out_files = res_files.output
    assert "<file" in out_files
    assert "<directory" not in out_files


def test_cli_ignore_file_hides_matching_entries(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROBL_CONFIG_PATH", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(repo_root / "xdg-empty"))

    base = repo_root / "proj"
    base.mkdir()
    (base / "keep.txt").write_text("keep\n", encoding="utf-8")
    (base / "skip.txt").write_text("skip\n", encoding="utf-8")
    logs = base / "logs"
    logs.mkdir()
    (logs / "app.log").write_text("log\n", encoding="utf-8")

    ignore_file = repo_root / "ignore.txt"
    ignore_file.write_text("# comment\nlogs/**\nskip.txt\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "scan",
            str(base),
            "--scope",
            "tree",
            "--summary",
            "none",
            "--output",
            "-",
            "--ignore-defaults",
            "--ignore-file",
            str(ignore_file),
        ],
    )
    assert result.exit_code == 0
    out = result.output
    # keep.txt is still visible, skip.txt and logs/ are hidden
    assert "keep.txt" in out
    assert "skip.txt" not in out
    assert "logs/" not in out


def test_cli_add_and_remove_ignore_roundtrip(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROBL_CONFIG_PATH", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(repo_root / "xdg-empty"))

    base = repo_root / "proj"
    d = base / "dir"
    d.mkdir(parents=True)
    (d / "keep.txt").write_text("k\n", encoding="utf-8")
    (d / "ignore.me").write_text("x\n", encoding="utf-8")

    runner = CliRunner()

    # With an added ignore pattern, ignore.me should be excluded from the tree
    res_add = runner.invoke(
        cli,
        [
            "scan",
            str(base),
            "--scope",
            "tree",
            "--summary",
            "none",
            "--output",
            "-",
            "--ignore-defaults",
            "--add-ignore",
            "dir/ignore.*",
        ],
    )
    assert res_add.exit_code == 0
    out_add = res_add.output
    assert "keep.txt" in out_add
    assert "ignore.me" not in out_add

    # Adding then removing the same pattern should restore ignore.me
    res_roundtrip = runner.invoke(
        cli,
        [
            "scan",
            str(base),
            "--scope",
            "tree",
            "--summary",
            "none",
            "--output",
            "-",
            "--ignore-defaults",
            "--add-ignore",
            "dir/ignore.*",
            "--remove-ignore",
            "dir/ignore.*",
        ],
    )
    assert res_roundtrip.exit_code == 0
    out_roundtrip = res_roundtrip.output
    assert "keep.txt" in out_roundtrip
    assert "ignore.me" in out_roundtrip


def test_cli_no_ignore_includes_default_excluded_dir(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROBL_CONFIG_PATH", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(repo_root / "xdg-empty"))

    base = repo_root / "proj"
    base.mkdir()
    venv = base / ".venv"
    venv.mkdir()
    (venv / "inner.txt").write_text("x\n", encoding="utf-8")

    runner = CliRunner()

    # With default config, .venv is excluded from the tree
    res_default = runner.invoke(
        cli,
        [
            "scan",
            str(base),
            "--scope",
            "tree",
            "--summary",
            "none",
            "--output",
            "-",
        ],
    )
    assert res_default.exit_code == 0
    out_default = res_default.output
    assert ".venv/" not in out_default

    # With --no-ignore, default exclude_tree patterns are disabled
    res_no_ignore = runner.invoke(
        cli,
        [
            "scan",
            str(base),
            "--scope",
            "tree",
            "--summary",
            "none",
            "--output",
            "-",
            "--no-ignore",
        ],
    )
    assert res_no_ignore.exit_code == 0
    out_no_ignore = res_no_ignore.output
    assert ".venv/" in out_no_ignore


def test_cli_config_tag_customisation_applies_to_llm_payload(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROBL_CONFIG_PATH", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(repo_root / "xdg-empty"))

    base = repo_root / "proj"
    base.mkdir()
    (base / "x.txt").write_text("x\n", encoding="utf-8")

    # Local config overrides tag names
    (base / ".grobl.toml").write_text(
        'exclude_tree = []\nexclude_print = []\ninclude_tree_tags = "project"\ninclude_file_tags = "snippet"'
        "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "scan",
            str(base),
            "--scope",
            "all",
            "--summary",
            "none",
            "--output",
            "-",
        ],
    )
    assert result.exit_code == 0
    out = result.output
    assert "<project " in out
    assert "<snippet " in out
    # Old default tags should not appear
    assert "<directory " not in out
    assert "<file " not in out


def test_cli_exclude_print_hides_contents_but_keeps_metadata(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROBL_CONFIG_PATH", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(repo_root / "xdg-empty"))

    base = repo_root / "proj"
    base.mkdir()
    (base / "keep.txt").write_text("keep-contents\n", encoding="utf-8")
    (base / "secret.txt").write_text("secret-contents\n", encoding="utf-8")

    (base / ".grobl.toml").write_text(
        "exclude_tree = []\nexclude_print = ['secret.txt']\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "scan",
            str(base),
            "--scope",
            "all",
            "--summary",
            "none",
            "--output",
            "-",
        ],
    )
    assert result.exit_code == 0
    out = result.output

    # secret.txt appears in the tree/metadata but its contents do not appear in the payload
    assert "secret.txt" in out
    assert "secret-contents" not in out

    # keep.txt appears with its contents included
    assert "keep.txt" in out
    assert "keep-contents" in out


def test_cli_binary_file_summary_marks_binary_flag(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROBL_CONFIG_PATH", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(repo_root / "xdg-empty"))

    base = repo_root / "proj"
    base.mkdir()
    (base / "blob.bin").write_bytes(b"\x00\x01\x02\x03")
    (base / "text.txt").write_text("hi\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "scan",
            str(base),
            "--summary",
            "json",
            "--format",
            "none",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    files = {entry["path"]: entry for entry in data["files"]}

    blob = files["blob.bin"]
    assert blob["lines"] == 0
    assert blob["chars"] == 4
    assert blob["included"] is False
    assert blob.get("binary") is True

    text = files["text.txt"]
    assert text["included"] is True
    assert text["lines"] > 0
    assert text["chars"] > 0


def test_cli_verbose_and_log_level_flags(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("data\n", encoding="utf-8")
    runner = CliRunner()

    res_verbose = runner.invoke(
        cli,
        [
            "-v",
            "scan",
            str(repo_root),
            "--summary",
            "none",
            "--output",
            "-",
        ],
    )
    assert res_verbose.exit_code == 0

    res_debug = runner.invoke(
        cli,
        [
            "--log-level",
            "DEBUG",
            "scan",
            str(repo_root),
            "--summary",
            "none",
            "--output",
            "-",
        ],
    )
    assert res_debug.exit_code == 0


def test_cli_unknown_command_errors() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["foo"])
    assert result.exit_code == 2
    assert "Unknown command: foo" in result.output


def test_cli_path_like_token_defaults_to_scan(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (repo_root / "data.txt").write_text("value\n", encoding="utf-8")
    runner = CliRunner()
    monkeypatch.setattr(tty, "stdout_is_tty", lambda: True, raising=True)
    monkeypatch.setattr(cli_scan, "stdout_is_tty", lambda: True, raising=True)
    result = runner.invoke(cli, [str(repo_root)])
    assert result.exit_code == 0
    assert "data.txt" in result.stderr


def test_cli_dash_prefixed_token_defaults_to_scan(repo_root: Path) -> None:
    (repo_root / "keep.txt").write_text("keep\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, ["--summary", "json", str(repo_root)])
    assert result.exit_code == 0
    assert '"root"' in result.output


def test_cli_existing_path_token_defaults_to_scan(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = repo_root / "existing"
    target.write_text("payload\n", encoding="utf-8")
    runner = CliRunner()
    monkeypatch.setattr(tty, "stdout_is_tty", lambda: True, raising=True)
    monkeypatch.setattr(cli_scan, "stdout_is_tty", lambda: True, raising=True)
    result = runner.invoke(cli, ["existing"])
    assert result.exit_code == 0
    assert "existing" in result.stderr


@dataclass(frozen=True)
class DestinationCase:
    name: str
    args: list[str]
    stdout_tty: bool
    expect_exit: int
    expect_stdout_json: bool
    expect_stderr_has_summary: bool
    expect_clipboard_used: bool
    expect_output_file: bool


@pytest.fixture
def fake_clipboard(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from grobl import output as output_mod

    captured: list[str] = []
    monkeypatch.setattr(output_mod.pyperclip, "copy", captured.append, raising=True)
    return captured


@pytest.fixture
def patch_tty(monkeypatch: pytest.MonkeyPatch) -> Callable[[bool], None]:
    # Patch both helpers used across codepaths (your tests already do this)
    from grobl import tty
    from grobl.cli import scan as cli_scan

    def _apply(is_tty: bool) -> None:
        monkeypatch.setattr(tty, "stdout_is_tty", lambda: is_tty, raising=True)
        monkeypatch.setattr(cli_scan, "stdout_is_tty", lambda: is_tty, raising=True)

    return _apply


def _mk_repo(repo_root: Path) -> None:
    (repo_root / "a.txt").write_text("hello\n", encoding="utf-8")


@pytest.mark.parametrize(
    "case",
    [
        DestinationCase(
            name="explicit_copy_writes_clipboard_no_stdout",
            args=["scan", "{root}", "--format", "json", "--summary", "none", "--copy"],
            stdout_tty=True,
            expect_exit=0,
            expect_stdout_json=False,
            expect_stderr_has_summary=False,
            expect_clipboard_used=True,
            expect_output_file=False,
        ),
        DestinationCase(
            name="output_dash_writes_stdout",
            args=["scan", "{root}", "--format", "json", "--summary", "none", "--output", "-"],
            stdout_tty=True,
            expect_exit=0,
            expect_stdout_json=True,
            expect_stderr_has_summary=False,
            expect_clipboard_used=False,
            expect_output_file=False,
        ),
        DestinationCase(
            name="output_file_writes_file",
            args=[
                "scan",
                "{root}",
                "--format",
                "json",
                "--summary",
                "none",
                "--output",
                "{root}/payload.json",
            ],
            stdout_tty=True,
            expect_exit=0,
            expect_stdout_json=False,
            expect_stderr_has_summary=False,
            expect_clipboard_used=False,
            expect_output_file=True,
        ),
        DestinationCase(
            name="copy_and_output_is_usage_error",
            args=["scan", "{root}", "--copy", "--output", "{root}/payload.json"],
            stdout_tty=True,
            expect_exit=2,
            expect_stdout_json=False,
            expect_stderr_has_summary=False,
            expect_clipboard_used=False,
            expect_output_file=False,
        ),
    ],
    ids=lambda c: c.name,
)
def test_payload_destination_contract(
    repo_root: Path,
    case: DestinationCase,
    patch_tty: Callable[[bool], None],
    fake_clipboard: list[str],
) -> None:
    _mk_repo(repo_root)
    patch_tty(case.stdout_tty)

    args = [a.format(root=str(repo_root)) for a in case.args]
    res = CliRunner().invoke(cli, args)

    assert res.exit_code == case.expect_exit

    if case.expect_stdout_json:
        # More robust than startswith("{")
        json.loads(res.stdout)
    else:
        assert res.stdout.strip() == ""

    if case.expect_stderr_has_summary:
        assert "Total lines" in res.stderr
    else:
        # don’t require exact emptiness unless that’s the contract
        pass

    if case.expect_clipboard_used:
        assert fake_clipboard
        # If JSON, parse it to ensure validity
        if fake_clipboard[0].lstrip().startswith("{"):
            json.loads(fake_clipboard[0])
    else:
        assert not fake_clipboard

    if case.expect_output_file:
        out_path = repo_root / "payload.json"
        assert out_path.exists()
        json.loads(out_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("fmt", ["llm", "markdown", "json", "ndjson", "none"])
def test_payload_format_contract(repo_root, fmt: str) -> None:
    (repo_root / "a.txt").write_text("x\n", encoding="utf-8")
    res = CliRunner().invoke(
        cli,
        ["scan", str(repo_root), "--format", fmt, "--summary", "none", "--output", "-"],
    )
    assert res.exit_code == 0

    out = res.stdout
    if fmt == "none":
        assert out.strip() == ""
        return

    assert out.endswith("\n")  # §11 trailing newline requirement (if you want it global)

    if fmt == "json":
        json.loads(out)
    elif fmt == "ndjson":
        for ln in out.splitlines():
            json.loads(ln)
    elif fmt == "markdown":
        assert "```tree" in out
    else:  # llm
        assert "<directory" in out or "<file" in out


@pytest.mark.parametrize(
    ("summary_mode", "summary_to", "expect_stdout", "expect_stderr"),
    [
        ("none", "stderr", False, False),
        ("table", "stderr", False, True),
        ("table", "stdout", True, False),
        ("json", "stderr", False, True),  # json summary goes to stderr by default in your tests
    ],
)
def test_summary_routing_contract(
    repo_root, summary_mode: str, summary_to: str, expect_stdout: bool, expect_stderr: bool
) -> None:
    (repo_root / "a.txt").write_text("x\n", encoding="utf-8")

    args = [
        "scan",
        str(repo_root),
        "--format",
        "json",
        "--output",
        "-",
        "--summary",
        summary_mode,
        "--summary-to",
        summary_to,
    ]
    res = CliRunner().invoke(cli, args)
    assert res.exit_code == 0

    # payload always on stdout here
    json.loads(res.stdout)

    if summary_mode == "json":
        if expect_stderr:
            json.loads(res.stderr.strip())
    elif summary_mode == "table":
        target = res.stdout if summary_to == "stdout" else res.stderr
        assert "Total lines" in target
    else:
        assert res.stderr.strip() == ""  # if that’s truly contractual


@pytest.mark.parametrize(
    ("args", "expect_exit", "expect_unknown_command"),
    [
        (["./"], 0, False),  # path-like token
        (["--summary", "json", "."], 0, False),  # begins with dash
        (["notapath"], EXIT_USAGE, True),  # non-injectable unknown token
    ],
)
def test_default_scan_injection_contract(repo_root, args, expect_exit, expect_unknown_command) -> None:
    (repo_root / "a.txt").write_text("x\n", encoding="utf-8")
    res = CliRunner().invoke(cli, args)

    assert res.exit_code == expect_exit
    blob = res.stdout + res.stderr
    assert ("Unknown command:" in blob) is expect_unknown_command
