"""Compatibility wrappers for config loading helpers."""

from grobl.config_loading import (
    LEGACY_TOML_CONFIG,
    PYPROJECT_TOML,
    load_config,
    load_toml_config,
    resolve_config_base,
)

__all__ = [
    "LEGACY_TOML_CONFIG",
    "PYPROJECT_TOML",
    "load_config",
    "load_toml_config",
    "resolve_config_base",
]
