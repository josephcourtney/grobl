"""Compatibility wrappers for config resource helpers."""

from grobl.config_defaults import (
    TOML_CONFIG,
    load_default_config,
    load_default_config_text,
    write_default_config,
    write_starter_config,
)

__all__ = [
    "TOML_CONFIG",
    "load_default_config",
    "load_default_config_text",
    "write_default_config",
    "write_starter_config",
]
