from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.small


def test_changelog_mentions_current_version() -> None:
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    version = config["project"]["version"]
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{version}]" in changelog
