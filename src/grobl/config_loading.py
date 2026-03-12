"""Configuration discovery and merge logic."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

from grobl.errors import ConfigLoadError

from .config_defaults import TOML_CONFIG, load_default_config

LEGACY_TOML_CONFIG = ".grobl.config.toml"
PYPROJECT_TOML = "pyproject.toml"


def resolve_config_base(*, base_path: Path, explicit_config: Path | None = None) -> Path:
    """Return the project config root for local matching/loading."""
    if explicit_config is not None:
        return explicit_config.resolve().parent

    base = base_path.resolve()
    if base.is_file():
        base = base.parent

    for candidate in (base, *base.parents):
        if (candidate / TOML_CONFIG).exists():
            return candidate
        if (candidate / LEGACY_TOML_CONFIG).exists():
            return candidate
        if (candidate / PYPROJECT_TOML).exists():
            return candidate

    return base


def load_toml_config(path: Path) -> dict[str, Any]:
    """Load configuration from a TOML file with optional ``extends`` support."""
    return _load_with_extends(path)


def load_config(
    *,
    base_path: Path,
    explicit_config: Path | None,
    ignore_defaults: bool,
) -> dict[str, Any]:
    """Read configuration sources and merge precedence without runtime CLI edits."""
    return _load_config_sources(
        base_path=base_path,
        ignore_default=ignore_defaults,
        explicit_config=explicit_config,
    )


def _load_with_extends(path: Path, *, _visited: set[Path] | None = None) -> dict[str, Any]:
    if _visited is None:
        _visited = set()
    real = path.resolve()
    if real in _visited:
        return {}
    _visited.add(real)

    raw = path.read_text(encoding="utf-8")
    try:
        data = tomlkit.loads(raw)
    except TOMLKitError as err:
        msg = f"Error parsing {path.name}: {err}"
        raise ConfigLoadError(msg) from err

    base_cfg: dict[str, Any] = {}
    ext = data.get("extends")
    if isinstance(ext, str):
        ext_list = [ext]
    elif isinstance(ext, list):
        ext_list = [entry for entry in ext if isinstance(entry, str)]
    else:
        ext_list = []
    for entry in ext_list:
        ext_path = Path(entry)
        if not ext_path.is_absolute():
            ext_path = (path.parent / ext_path).resolve()
        if ext_path.exists():
            base_cfg |= _load_with_extends(ext_path, _visited=_visited)

    base_cfg |= {key: value for key, value in data.items() if key != "extends"}
    return base_cfg


def _xdg_config_path() -> Path:
    xdg_home = os.environ.get("XDG_CONFIG_HOME")
    xdg_dir = Path(xdg_home) if xdg_home else Path.home() / ".config"
    return xdg_dir / "grobl" / "config.toml"


def _merge_pyproject_cfg(pyproject_path: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    if not pyproject_path.exists():
        return cfg
    try:
        data = tomlkit.loads(pyproject_path.read_text(encoding="utf-8"))
    except TOMLKitError as err:
        msg = f"Error parsing pyproject.toml: {err}"
        raise ConfigLoadError(msg) from err
    tool = data.get("tool", {})
    if isinstance(tool, dict):
        grobl_cfg = tool.get("grobl")
        if isinstance(grobl_cfg, dict):
            cfg |= grobl_cfg
    return cfg


def _load_config_sources(
    *,
    base_path: Path,
    ignore_default: bool = False,
    explicit_config: Path | None = None,
) -> dict[str, Any]:
    cfg: dict[str, Any] = {} if ignore_default else load_default_config()

    for path in (
        _xdg_config_path(),
        base_path / LEGACY_TOML_CONFIG,
        base_path / TOML_CONFIG,
    ):
        if path.exists():
            cfg |= load_toml_config(path)

    cfg = _merge_pyproject_cfg(base_path / PYPROJECT_TOML, cfg)

    env_path = os.environ.get("GROBL_CONFIG_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            cfg |= load_toml_config(path)

    if explicit_config:
        if not explicit_config.exists():
            msg = f"Explicit config file not found: {explicit_config}"
            raise ConfigLoadError(msg)
        cfg |= load_toml_config(explicit_config)

    return cfg
