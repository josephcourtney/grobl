"""Unit tests for grobl_cli.service.prompt utilities."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from grobl_cli.service import prompt


def test_env_assume_yes_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROBL_ASSUME_YES", "true")
    assert prompt.env_assume_yes() is True


def test_env_assume_yes_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROBL_ASSUME_YES", "no")
    assert prompt.env_assume_yes() is False


def test_warn_skipped_if_assume_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Should not call confirm if assume_yes is True
    paths = (Path(),)
    with mock.patch("grobl_cli.service.prompt._detect_heavy_dirs", return_value={"node_modules"}):
        prompt.maybe_warn_on_common_heavy_dirs(
            paths=paths,
            ignore_defaults=True,
            assume_yes=True,
            confirm=lambda _: pytest.fail("Should not prompt"),
        )


def test_warn_shown_and_aborted(monkeypatch: pytest.MonkeyPatch) -> None:
    paths = (Path(),)
    with mock.patch("grobl_cli.service.prompt._detect_heavy_dirs", return_value={"node_modules"}):
        with pytest.raises(SystemExit) as excinfo:
            prompt.maybe_warn_on_common_heavy_dirs(
                paths=paths,
                ignore_defaults=True,
                assume_yes=False,
                confirm=lambda _: False,  # User says "no"
            )
        assert excinfo.value.code == 2


def test_warn_shown_and_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    paths = (Path(),)
    with mock.patch("grobl_cli.service.prompt._detect_heavy_dirs", return_value={"node_modules"}):
        # Should not raise
        prompt.maybe_warn_on_common_heavy_dirs(
            paths=paths,
            ignore_defaults=True,
            assume_yes=False,
            confirm=lambda _: True,  # User says "yes"
        )
