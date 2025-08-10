"""Utilities for loading and writing configuration files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import importlib.resources
import json
import tomllib
import tomlkit
from tomlkit.exceptions import TOMLKitError

from .errors import ConfigLoadError

# Configuration filenames
DOTIGNORE_CONFIG = ".groblignore"
JSON_CONFIG = ".grobl.config.json"
TOML_CONFIG = ".grobl.config.toml"


def load_default_config() -> dict[str, Any]:
    """Return the bundled default configuration."""

    try:
        cfg_path = importlib.resources.files("grobl.resources").joinpath(
            "default_config.toml"
        )
        with cfg_path.open("r", encoding="utf-8") as f:
            text = f.read()
    except OSError as err:  # pragma: no cover - exercised via CLI
        msg = f"Error loading default configuration: {err}"
        raise ConfigLoadError(msg) from err
    return tomllib.loads(text)


def write_default_config(target_dir: Path) -> Path:
    """Write the bundled default configuration into ``target_dir``.

    The file is written as :data:`TOML_CONFIG` and the full path is returned.
    Any existing file will be overwritten.
    """

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
        msg = f"Error parsing {TOML_CONFIG}: {e}"
        raise ConfigLoadError(msg) from e


def load_json_config(path: Path) -> dict[str, Any]:
    """Load configuration from a legacy JSON file."""

    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        msg = f"Error parsing {JSON_CONFIG}: {e}"
        raise ConfigLoadError(msg) from e


def read_groblignore(path: Path) -> list[str]:
    """Return ignore patterns from ``.groblignore`` if present."""

    f = path / DOTIGNORE_CONFIG
    if not f.exists():
        return []
    return [
        line.strip()
        for line in f.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def expand_groups(cfg: dict[str, Any]) -> None:
    """Expand configured exclude groups into explicit patterns."""

    groups = cfg.get("groups", {})
    for target, key in (
        ("exclude_tree", "exclude_tree_groups"),
        ("exclude_print", "exclude_print_groups"),
    ):
        for group_name in cfg.get(key, []):
            for pat in groups.get(group_name, []):
                cfg.setdefault(target, [])
                if pat not in cfg[target]:
                    cfg[target].append(pat)


def read_config(
    base_path: Path,
    *,
    ignore_default: bool = False,
) -> dict[str, Any]:
    """Read configuration from ``base_path`` and merge defaults."""

    toml_path = base_path / TOML_CONFIG
    json_path = base_path / JSON_CONFIG
    ignore_path = base_path / DOTIGNORE_CONFIG
    pyproject_path = base_path / "pyproject.toml"

    if not toml_path.exists() and (json_path.exists() or ignore_path.exists()):
        print("Found legacy configuration files. Migrating to .grobl.config.toml...")
        migrate_config(base_path, assume_yes=True)

    cfg: dict[str, Any] = {} if ignore_default else load_default_config()

    if toml_path.exists():
        cfg.update(load_toml_config(toml_path))
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

    expand_groups(cfg)

    return cfg


# ─── Config Migration Helpers ────────────────────────────────────────────────


def collect_old_configs(path: Path) -> list[Path]:
    """Return legacy configuration files located in ``path``."""

    out: list[Path] = []
    for name in (JSON_CONFIG, DOTIGNORE_CONFIG):
        p = path / name
        if p.exists():
            out.append(p)
    return out


def build_merged_config(path: Path) -> dict[str, Any]:
    """Merge legacy configs with defaults and return a new config dict."""

    cfg = load_default_config()
    for old in collect_old_configs(path):
        if old.name == JSON_CONFIG:
            cfg.update(load_json_config(old))
        elif old.name == DOTIGNORE_CONFIG:
            for pat in read_groblignore(path):
                cfg.setdefault("exclude_tree", [])
                if pat not in cfg["exclude_tree"]:
                    cfg["exclude_tree"].append(pat)
    return cfg


def prompt_delete(files: list[Path], *, assume_yes: bool = False) -> None:
    """Delete ``files`` after user confirmation."""

    for f in files:
        if assume_yes:
            f.unlink()
            print(f"Deleted {f.name}")
            continue
        resp = input(f"Delete old file {f.name}? (y/N): ").strip().lower()
        if resp == "y":
            f.unlink()
            print(f"Deleted {f.name}")
        else:
            print(f"Kept {f.name}")


def migrate_config(
    path: Path, *, assume_yes: bool = False, to_stdout: bool = False
) -> None:
    """Migrate legacy configuration files to the TOML format."""

    toml_path = path / TOML_CONFIG
    if toml_path.exists():
        print(f"{TOML_CONFIG} already exists.")
        return

    old_files = collect_old_configs(path)
    if not old_files:
        print(f"No {JSON_CONFIG} or {DOTIGNORE_CONFIG} to migrate.")
        return

    new_cfg = build_merged_config(path)
    new_toml = tomlkit.dumps(new_cfg)

    print(f"\n=== New TOML ({TOML_CONFIG}): ===")
    print(new_toml)
    if not to_stdout:
        toml_path.write_text(new_toml, encoding="utf-8")
        prompt_delete(old_files, assume_yes=assume_yes)
        print(f"\nMigration complete → {TOML_CONFIG}")
    else:
        prompt_delete(old_files, assume_yes=assume_yes)
