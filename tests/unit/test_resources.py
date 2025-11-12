"""Regression tests for bundled resource files."""

from importlib.resources import files


def test_default_config_excludes_legacy_filename() -> None:
    text = files("grobl.resources").joinpath("default_config.toml").read_text("utf-8")
    assert ".grobl.config.toml" in text
    assert ".grobl.toml" not in text
