"""Bundled configuration resource access."""

from __future__ import annotations

import importlib.resources
import tomllib
from typing import TYPE_CHECKING, Any

from grobl.errors import ConfigLoadError

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_CONFIG_RESOURCE = "default_config.toml"
DEFAULT_CONFIG_PACKAGE = "grobl.resources"
TOML_CONFIG = ".grobl.toml"


def load_default_config() -> dict[str, Any]:
    """Return the bundled default configuration as a Python dict."""
    try:
        cfg_path = importlib.resources.files(DEFAULT_CONFIG_PACKAGE).joinpath(DEFAULT_CONFIG_RESOURCE)
        with cfg_path.open("r", encoding="utf-8") as handle:  # type: ignore[attr-defined]
            text = handle.read()
    except OSError as err:  # pragma: no cover - exercised via CLI
        msg = f"Error loading default configuration: {err}"
        raise ConfigLoadError(msg) from err
    return tomllib.loads(text)


def load_default_config_text() -> str:
    """Return the bundled default configuration text with formatting preserved."""
    try:
        cfg_path = importlib.resources.files(DEFAULT_CONFIG_PACKAGE).joinpath(DEFAULT_CONFIG_RESOURCE)
        with cfg_path.open("r", encoding="utf-8") as handle:  # type: ignore[attr-defined]
            return handle.read()
    except OSError as err:  # pragma: no cover - exercised via CLI
        msg = f"Error loading default configuration: {err}"
        raise ConfigLoadError(msg) from err


def write_default_config(target_dir: Path) -> Path:
    """Write the bundled default configuration into ``target_dir``."""
    text = load_default_config_text()
    toml_path = target_dir / TOML_CONFIG
    toml_path.write_text(text, encoding="utf-8")
    return toml_path
