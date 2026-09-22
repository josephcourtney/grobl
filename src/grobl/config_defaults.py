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

STARTER_CONFIG_TEXT = """# Inherit Grobl's bundled inclusion policy before applying this project config.
# Set to false to define inclusion policy entirely in project configuration.
inherit_defaults = true

# Project-specific inclusion rules. Patterns use gitignore-style matching.
# exclude = [
#   "generated/",
# ]
#
# tree_only = [
#   "docs/",
# ]
#
# include = [
#   "docs/architecture.md",
# ]

# Stable scan defaults can also live here. Explicit CLI options override them.
# scope = "all"
# format = "llm"
# summary = "auto"
# summary_style = "auto"  # only meaningful with summary = "table"
# lines = true
# characters = true
# tokens = true
# inclusion_status = true
# ignore_policy = "auto"
# max_file_bytes = 1048576   # 0 disables
# max_total_bytes = 16777216 # 0 disables
# max_tokens = 200000        # 0 disables

# LLM payload tag names:
# include_tree_tags = "directory"
# include_file_tags = "files"
"""


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


def write_starter_config(target_dir: Path) -> Path:
    """Write the minimal commented starter configuration into target_dir."""
    toml_path = target_dir / TOML_CONFIG
    toml_path.write_text(STARTER_CONFIG_TEXT, encoding="utf-8")
    return toml_path
