from __future__ import annotations

import pytest
from click.testing import CliRunner

from grobl.cli import cli
from grobl.constants import EXIT_USAGE

pytestmark = pytest.mark.small


def _run(args: list[str]) -> tuple[int, str, str]:
    runner = CliRunner()
    res = runner.invoke(cli, args)
    return res.exit_code, res.stdout, res.stderr


@pytest.mark.parametrize(
    "token",
    [
        "scan1",  # non-alpha
        "sc-an",  # non-alpha
        "sc_an",  # non-alpha
        "Σ",  # non-ascii alphabetic, but not [A-Za-z]
    ],
)
def test_unknown_nonalpha_command_token_is_usage_error_when_not_injectable(token: str) -> None:
    code, out, err = _run([token])
    blob = out + err
    assert code == EXIT_USAGE
    assert f"Unknown command: {token}" in blob


def test_help_rendered_exactly_once_on_root_help() -> None:
    code, out, _ = _run(["--help"])
    assert code == 0
    assert out.count("Usage: ") == 1


def test_unknown_command_usage_is_rendered_once() -> None:
    code, out, err = _run(["doesnotexist"])
    blob = out + err
    assert code == EXIT_USAGE
    assert blob.count("Usage: ") <= 1
    assert "Unknown command:" in blob


def test_version_flags_output_semver_only() -> None:
    for flag in ("--version", "-V"):
        code, out, err = _run([flag])
        assert code == 0
        assert not err
        v = out.strip()
        parts = v.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


def test_unknown_command_is_usage_error() -> None:
    code, out, err = _run(["unknowncmd"])
    blob = out + err
    assert code == EXIT_USAGE
    assert "Unknown command:" in blob
