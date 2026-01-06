from __future__ import annotations

import pytest
from click.testing import CliRunner

from grobl.cli import cli

pytestmark = pytest.mark.small


def _run(args: list[str]) -> tuple[int, str, str]:
    runner = CliRunner()
    res = runner.invoke(cli, args)
    return res.exit_code, res.stdout, res.stderr


def test_help_rendered_exactly_once_on_root_help() -> None:
    code, out, _ = _run(["--help"])
    assert code == 0
    assert out.count("Usage: ") == 1


def test_version_flags_output_semver_only() -> None:
    for flag in ("--version", "-V"):
        code, out, err = _run([flag])
        assert code == 0
        assert not err
        v = out.strip()
        parts = v.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
