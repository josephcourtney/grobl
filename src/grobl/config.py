"""Utilities for loading and writing configuration files."""

from __future__ import annotations

import importlib.resources
import os
import tomllib
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

from grobl.errors import ConfigLoadError

# Configuration filenames
TOML_CONFIG = ".grobl.toml"
# Legacy filename we still detect and optionally migrate:
LEGACY_TOML_CONFIG = ".grobl.config.toml"


def load_default_config() -> dict[str, Any]:
    """Return the bundled default configuration as a Python dict."""
    try:
        cfg_path = importlib.resources.files("grobl.resources").joinpath("default_config.toml")
        with cfg_path.open("r", encoding="utf-8") as f:  # type: ignore[attr-defined]
            text = f.read()
    except OSError as err:  # pragma: no cover - exercised via CLI
        msg = f"Error loading default configuration: {err}"
        raise ConfigLoadError(msg) from err
    return tomllib.loads(text)


def load_default_config_text() -> str:
    """Return the bundled default configuration text.

    This preserves formatting (one item per line arrays, comments, spacing)
    so that `grobl init` writes a nicely formatted file.
    """
    try:
        cfg_path = importlib.resources.files("grobl.resources").joinpath("default_config.toml")
        with cfg_path.open("r", encoding="utf-8") as f:  # type: ignore[attr-defined]
            return f.read()
    except OSError as err:  # pragma: no cover - exercised via CLI
        msg = f"Error loading default configuration: {err}"
        raise ConfigLoadError(msg) from err


def write_default_config(target_dir: Path) -> Path:
    """Write the bundled default configuration into ``target_dir``.

    Writes the original resource text to preserve human-friendly formatting
    (arrays split one item per line, comments, and spacing).
    """
    text = load_default_config_text()
    toml_path = target_dir / TOML_CONFIG
    toml_path.write_text(text, encoding="utf-8")
    return toml_path


def _load_with_extends(path: Path, *, _visited: set[Path] | None = None) -> dict[str, Any]:
    """Load a TOML file supporting an optional 'extends' key for inheritance.

    Later files override earlier ones. Relative paths in 'extends' are resolved
    relative to the parent of ``path``.
    """
    if _visited is None:
        _visited = set()
    real = path.resolve()
    if real in _visited:
        # Prevent cycles; later file wins so just stop here.
        return {}
    _visited.add(real)

    raw = path.read_text(encoding="utf-8")
    try:
        data = tomlkit.loads(raw)
    except TOMLKitError as e:
        msg = f"Error parsing {path.name}: {e}"
        raise ConfigLoadError(msg) from e

    # Handle 'extends' (string or list of strings)
    base_cfg: dict[str, Any] = {}
    ext = data.get("extends")
    if isinstance(ext, str):
        ext_list = [ext]
    elif isinstance(ext, list):
        ext_list = [e for e in ext if isinstance(e, str)]
    else:
        ext_list = []
    for entry in ext_list:
        ext_path = Path(entry)
        if not ext_path.is_absolute():
            ext_path = (path.parent / ext_path).resolve()
        if ext_path.exists():
            base_cfg |= _load_with_extends(ext_path, _visited=_visited)

    # Current file overrides extended values
    base_cfg |= {k: v for k, v in data.items() if k != "extends"}
    return base_cfg


def load_toml_config(path: Path) -> dict[str, Any]:
    """Load configuration from a TOML file (supports 'extends')."""
    return _load_with_extends(path)


def _xdg_config_path() -> Path:
    xdg_home = os.environ.get("XDG_CONFIG_HOME")
    xdg_dir = Path(xdg_home) if xdg_home else Path.home() / ".config"
    return xdg_dir / "grobl" / "config.toml"


def _merge_pyproject_cfg(pyproject_path: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    if not pyproject_path.exists():
        return cfg
    try:
        data = tomlkit.loads(pyproject_path.read_text(encoding="utf-8"))
    except TOMLKitError as e:
        msg = f"Error parsing pyproject.toml: {e}"
        raise ConfigLoadError(msg) from e
    tool = data.get("tool", {})
    if isinstance(tool, dict):
        grobl_cfg = tool.get("grobl")
        if isinstance(grobl_cfg, dict):
            cfg |= grobl_cfg
    return cfg


def read_config(
    *,
    base_path: Path,
    ignore_default: bool = False,
    explicit_config: Path | None = None,
) -> dict[str, Any]:
    """Read configuration merging multiple sources with clear precedence.

    Precedence (low → high):
      1. bundled defaults (unless ``ignore_default``)
      2. XDG config: $XDG_CONFIG_HOME/grobl/config.toml (or ~/.config/grobl/config.toml)
      3. local project files in ``base_path``: .grobl.toml
      4. [tool.grobl] table in pyproject.toml at ``base_path``
      5. $GROBL_CONFIG_PATH (if set)
      6. ``explicit_config`` (from --config)
    Later sources override earlier ones.
    """
    cfg: dict[str, Any] = {} if ignore_default else load_default_config()

    # 2-4) layer XDG, local TOML, then pyproject table
    for p in (
        _xdg_config_path(),
        base_path / TOML_CONFIG,
    ):
        if p.exists():
            cfg |= load_toml_config(p)

    cfg = _merge_pyproject_cfg(base_path / "pyproject.toml", cfg)

    # 5) env override
    env_path = os.environ.get("GROBL_CONFIG_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            cfg |= load_toml_config(p)

    # 6) explicit path override
    if explicit_config:
        if not explicit_config.exists():
            msg = f"Explicit config file not found: {explicit_config}"
            raise ConfigLoadError(msg)
        cfg |= load_toml_config(explicit_config)

    return cfg


def apply_runtime_ignores(
    cfg: dict[str, Any],
    *,
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
    add_ignore_files: tuple[Path, ...] = (),
    no_ignore: bool = False,
) -> dict[str, Any]:
    """Apply one-off ignore adjustments from CLI to the loaded config."""
    # "Centralized here to keep CLI thin and make testing easier."
    cfg = dict(cfg)
    exclude = list(cfg.get("exclude_tree", []))
    # merge ignore files
    for f in add_ignore_files:
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in lines:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s not in exclude:
                exclude.append(s)
    for pat in add_ignore:
        if pat not in exclude:
            exclude.append(pat)
    for pat in remove_ignore:
        if pat in exclude:
            exclude.remove(pat)
    cfg["exclude_tree"] = [] if no_ignore else exclude
    return cfg


def load_and_adjust_config(
    *,
    base_path: Path,
    explicit_config: Path | None,
    ignore_defaults: bool,
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
    add_ignore_files: tuple[Path, ...] = (),
    no_ignore: bool = False,
) -> dict[str, Any]:
    """Read config and apply ad-hoc ignore edits."""
    base = read_config(base_path=base_path, ignore_default=ignore_defaults, explicit_config=explicit_config)
    return apply_runtime_ignores(
        base,
        add_ignore=add_ignore,
        remove_ignore=remove_ignore,
        add_ignore_files=add_ignore_files,
        no_ignore=no_ignore,
    )
