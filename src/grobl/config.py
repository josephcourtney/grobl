"""Utilities for loading and writing configuration files."""

from __future__ import annotations

import importlib.resources
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

from grobl.errors import ConfigLoadError

# Configuration filenames
TOML_CONFIG = ".grobl.toml"
# Legacy filename we still detect and optionally migrate:
LEGACY_TOML_CONFIG = ".grobl.config.toml"
PYPROJECT_TOML = "pyproject.toml"


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


def _load_config_sources(
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
        base_path / LEGACY_TOML_CONFIG,
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


def _append_unique(exclude: list[str], patterns: tuple[str, ...]) -> None:
    for pat in patterns:
        if pat not in exclude:
            exclude.append(pat)


def _append_ignore_file_patterns(exclude: list[str], add_ignore_files: tuple[Path, ...]) -> None:
    for f in add_ignore_files:
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        cleaned = [line.strip() for line in lines]
        patterns = tuple(s for s in cleaned if s and not s.startswith("#"))
        _append_unique(exclude, patterns)


def _remove_patterns(exclude: list[str], remove_ignore: tuple[str, ...]) -> None:
    for pat in remove_ignore:
        if pat in exclude:
            exclude.remove(pat)
        else:
            print(f"warning: ignore pattern not found: {pat}", file=sys.stderr)


def _append_unignore_patterns(exclude: list[str], unignore: tuple[str, ...]) -> None:
    for pat in unignore:
        negated = pat if pat.startswith("!") else f"!{pat}"
        if negated not in exclude:
            exclude.append(negated)


@dataclass(frozen=True, slots=True)
class RuntimeIgnoreEdits:
    """Runtime ignore edits applied on top of a base pattern list."""

    tree_patterns: list[str]
    print_patterns: list[str]


def apply_runtime_ignore_edits(
    *,
    base_tree: list[str],
    base_print: list[str],
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
    add_ignore_files: tuple[Path, ...] = (),
    unignore: tuple[str, ...] = (),
    no_ignore: bool = False,
    exclude: tuple[str, ...] = (),
    include: tuple[str, ...] = (),
    exclude_tree: tuple[str, ...] = (),
    include_tree: tuple[str, ...] = (),
    exclude_content: tuple[str, ...] = (),
    include_content: tuple[str, ...] = (),
) -> RuntimeIgnoreEdits:
    """Apply CLI ignore overrides to both tree and content layers."""
    tree = list(base_tree)
    if no_ignore:
        return RuntimeIgnoreEdits(tree_patterns=[], print_patterns=[])

    _append_ignore_file_patterns(tree, add_ignore_files)
    _append_unique(tree, add_ignore)

    print_patterns = list(base_print)

    for pat in exclude:
        _append_unique(tree, (pat,))
        _append_unique(print_patterns, (pat,))
    for pat in exclude_tree:
        _append_unique(tree, (pat,))
    for pat in exclude_content:
        _append_unique(print_patterns, (pat,))

    _remove_patterns(tree, remove_ignore)
    _append_unignore_patterns(tree, unignore)
    _append_unignore_patterns(tree, include)
    _append_unignore_patterns(tree, include_tree)
    _append_unignore_patterns(print_patterns, include)
    _append_unignore_patterns(print_patterns, include_content)

    return RuntimeIgnoreEdits(tree_patterns=tree, print_patterns=print_patterns)


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
