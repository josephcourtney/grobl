from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from typing import TYPE_CHECKING

import grobl.__init__ as grobl_init

if TYPE_CHECKING:
    import pytest


def test_distribution_version_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(grobl_init, "version", lambda _name: "9.9.9")
    version, source = grobl_init._resolve_version()
    assert version == "9.9.9"
    assert source == "distribution"


def test_pyproject_version_source_on_missing_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_missing(_name: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(grobl_init, "version", raise_missing)
    monkeypatch.setattr(grobl_init, "_load_pyproject_version", lambda: ("1.2.3", "pyproject"))
    version, source = grobl_init._resolve_version()
    assert version == "1.2.3"
    assert source == "pyproject"
