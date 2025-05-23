import importlib.resources
import json
import tomllib
from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError

from .errors import ConfigLoadError

# Configuration filenames
DOTIGNORE_CONFIG = ".groblignore"
JSON_CONFIG = ".grobl.config.json"
TOML_CONFIG = ".grobl.config.toml"


def load_default_config() -> dict:
    try:
        cfg_path = importlib.resources.files("grobl.resources").joinpath("default_config.toml")
        with cfg_path.open("r", encoding="utf-8") as f:
            text = f.read()

    except OSError as err:
        msg = f"Error loading default configuration: {err}"
        raise ConfigLoadError(msg) from err
    return tomllib.loads(text)


def load_toml_config(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    try:
        return tomlkit.loads(raw)
    except TOMLKitError as e:
        msg = f"Error parsing {TOML_CONFIG}: {e}"
        raise ConfigLoadError(msg) from e


def load_json_config(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        msg = f"Error parsing {JSON_CONFIG}: {e}"
        raise ConfigLoadError(msg) from e


def read_groblignore(path: Path) -> list[str]:
    f = path / DOTIGNORE_CONFIG
    if not f.exists():
        return []
    return [
        line.strip()
        for line in f.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def merge_gitignore(cfg: dict, base_path: Path) -> None:
    patterns = read_groblignore(base_path)
    if not patterns:
        return
    cfg.setdefault("exclude_tree", [])
    for pat in patterns:
        if pat not in cfg["exclude_tree"]:
            cfg["exclude_tree"].append(pat)


# Boolean flags are keyword-only to avoid FBT001/FBT002
def read_config(
    base_path: Path,
    *,
    ignore_default: bool = False,
    use_gitignore: bool = True,
) -> dict:
    toml_path = base_path / TOML_CONFIG
    json_path = base_path / JSON_CONFIG

    cfg: dict = {} if ignore_default else load_default_config()

    if toml_path.exists():
        cfg.update(load_toml_config(toml_path))
    elif json_path.exists():
        cfg.update(load_json_config(json_path))

    if use_gitignore:
        merge_gitignore(cfg, base_path)

    return cfg


# ─── Config Migration Helpers ────────────────────────────────────────────────


def collect_old_configs(path: Path) -> list[Path]:
    out: list[Path] = []
    for name in (JSON_CONFIG, DOTIGNORE_CONFIG):
        p = path / name
        if p.exists():
            out.append(p)
    return out


def build_merged_config(path: Path) -> dict:
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


def prompt_delete(files: list[Path]) -> None:
    for f in files:
        resp = input(f"Delete old file {f.name}? (y/N): ").strip().lower()
        if resp == "y":
            f.unlink()
            print(f"Deleted {f.name}")
        else:
            print(f"Kept {f.name}")


def migrate_config(path: Path) -> None:
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
    toml_path.write_text(new_toml, encoding="utf-8")

    prompt_delete(old_files)
    print(f"\nMigration complete → {TOML_CONFIG}")
