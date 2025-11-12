from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner

from grobl import tty
from grobl.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_explicit_full_table_even_when_not_tty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force non-tty but request full table explicitly
    monkeypatch.setattr(tty, "stdout_is_tty", lambda: False)
    (tmp_path / "f.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["scan", str(tmp_path), "--mode", "summary", "--table", "full", "--no-clipboard"],
    )
    assert res.exit_code == 0
    assert " Project Summary " in res.output


def test_quiet_suppresses_summary_output(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("data", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["scan", str(tmp_path), "--mode", "summary", "--quiet", "--no-clipboard"],
    )
    assert res.exit_code == 0
    assert not res.output.strip()


def test_heavy_dir_warning_can_abort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Create an explicit heavy directory and scan that path
    heavy = tmp_path / "node_modules"
    heavy.mkdir()
    (heavy / "x.txt").write_text("x", encoding="utf-8")

    # Cause interactive confirmation to respond 'no'
    import grobl.cli as grobl_cli

    # The function uses a default param bound at definition time; wrap to override confirm.
    original_warn = grobl_cli._maybe_warn_on_common_heavy_dirs

    def wrapped_warn(*, paths, ignore_defaults, assume_yes):  # type: ignore[no-redef,unused-ignore]
        return original_warn(
            paths=paths,
            ignore_defaults=ignore_defaults,
            assume_yes=assume_yes,
            confirm=lambda _msg: False,
        )

    monkeypatch.setattr(grobl_cli, "_maybe_warn_on_common_heavy_dirs", wrapped_warn)

    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "scan",
            str(tmp_path),  # scan parent so heavy dir is detected
            "--ignore-defaults",
            "--no-clipboard",
        ],
    )
    assert res.exit_code == 1
