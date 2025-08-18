"""Utilities for loading and writing configuration files."""

from __future__ import annotations

import importlib.resources
import tomllib
from typing import TYPE_CHECKING, Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

from grobl.errors import ConfigLoadError

if TYPE_CHECKING:
    from pathlib import Path

# Configuration filenames
TOML_CONFIG = ".grobl.toml"
# Legacy filename we still detect and optionally migrate:
LEGACY_TOML_CONFIG = ".grobl.config.toml"


def load_default_config() -> dict[str, Any]:
    """Return the bundled default configuration."""
    try:
        cfg_path = importlib.resources.files("grobl.resources").joinpath("default_config.toml")
        with cfg_path.open("r", encoding="utf-8") as f:  # type: ignore[attr-defined]
            text = f.read()
    except OSError as err:  # pragma: no cover - exercised via CLI
        msg = f"Error loading default configuration: {err}"
        raise ConfigLoadError(msg) from err
    return tomllib.loads(text)


def write_default_config(target_dir: Path) -> Path:
    """Write the bundled default configuration into ``target_dir``."""
    cfg = load_default_config()
    toml_path = target_dir / TOML_CONFIG
    toml_path.write_text(tomlkit.dumps(cfg), encoding="utf-8")
    return toml_path


def load_toml_config(path: Path) -> dict[str, Any]:
    """Load configuration from a TOML file."""
    raw = path.read_text(encoding="utf-8")
    try:
        return tomlkit.loads(raw)
    except TOMLKitError as e:
        msg = f"Error parsing {path.name}: {e}"
        raise ConfigLoadError(msg) from e


def read_config(
    base_path: Path,
    *,
    ignore_default: bool = False,
) -> dict[str, Any]:
    """Read configuration from ``base_path`` and merge defaults.

    Preference: new file (.grobl.toml) -> legacy file (.grobl.config.toml) -> none.
    """
    toml_path = base_path / TOML_CONFIG
    pyproject_path = base_path / "pyproject.toml"

    cfg: dict[str, Any] = {} if ignore_default else load_default_config()

    if toml_path.exists():
        cfg |= load_toml_config(toml_path)
    else:
        legacy = base_path / LEGACY_TOML_CONFIG
        if legacy.exists():
            # Still load it for backward compatibility (CLI will also prompt to migrate)
            cfg.update(load_toml_config(legacy))
    if pyproject_path.exists():
        try:
            data = tomlkit.loads(pyproject_path.read_text(encoding="utf-8"))
        except TOMLKitError as e:
            msg = f"Error parsing pyproject.toml: {e}"
            raise ConfigLoadError(msg) from e
        tool = data.get("tool", {})
        if isinstance(tool, dict):
            grobl_cfg = tool.get("grobl")
            if isinstance(grobl_cfg, dict):
                cfg.update(grobl_cfg)

    return cfg


def apply_runtime_ignores(
    cfg: dict[str, Any],
    *,
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
) -> dict[str, Any]:
    """Apply one-off ignore adjustments from CLI to the loaded config."""
    # "Centralized here to keep CLI thin and make testing easier."
    cfg = dict(cfg)
    exclude = list(cfg.get("exclude_tree", []))
    for pat in add_ignore:
        if pat not in exclude:
            exclude.append(pat)
    for pat in remove_ignore:
        if pat in exclude:
            exclude.remove(pat)
    cfg["exclude_tree"] = exclude
    return cfg


def load_and_adjust_config(
    *,
    cwd: Path,
    ignore_defaults: bool,
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
) -> dict[str, Any]:
    """Read config and apply ad-hoc ignore edits."""
    base = read_config(base_path=cwd, ignore_default=ignore_defaults)
    return apply_runtime_ignores(base, add_ignore=add_ignore, remove_ignore=remove_ignore)
