import argparse
import json
import logging
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pyperclip

# Configuration
CONFIG_FILENAME = ".grobl.config.json"
DEFAULT_CONFIG = {
    "exclude_tree": ["*.jsonl", "*.jsonl.*", "tests/*", "cov.xml", "*.log", "*.tmp"],
    "exclude_print": ["*.json", "*.html"],
    # XML-style tag names for wrapping outputs
    "include_tree_tags": "tree",
    "include_file_tags": "file",
}

# Error messages
ERROR_MSG_NO_COMMON_ANCESTOR = "No common ancestor found"
ERROR_MSG_EMPTY_PATHS = "The list of paths is empty"

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Utility: escape markdown characters
def escape_markdown(text: str) -> str:
    markdown_chars = r"([*_#\[\]{}()>+\-.!])"
    return re.sub(markdown_chars, r"\\\1", text)


# Custom exception
class PathNotFoundError(Exception):
    pass


# Clipboard interface
class ClipboardInterface:
    def copy(self, content: str) -> None:
        raise NotImplementedError


class PyperclipClipboard(ClipboardInterface):
    def copy(self, content: str) -> None:
        pyperclip.copy(content)


# Find common ancestor path
def find_common_ancestor(paths: list[Path]) -> Path:
    if not paths:
        raise ValueError(ERROR_MSG_EMPTY_PATHS)
    common = paths[0].resolve()
    for p in map(Path.resolve, paths[1:]):
        while not p.is_relative_to(common):
            common = common.parent
            if common == Path("/"):
                raise PathNotFoundError(ERROR_MSG_NO_COMMON_ANCESTOR)
    return common


# Directory tree builder
@dataclass
class DirectoryTreeBuilder:
    base_path: Path
    exclude_patterns: list[str]
    tree_output: list[str] = field(default_factory=list)
    file_contents: list[str] = field(default_factory=list)
    total_lines: int = 0
    total_characters: int = 0
    file_tree_entries: list[tuple[int, Path]] = field(default_factory=list)
    file_metadata: dict[str, tuple[int, int]] = field(default_factory=dict)

    def add_directory(self, directory_path: Path, prefix: str, *, is_last: bool) -> None:
        connector = "└── " if is_last else "├── "
        self.tree_output.append(f"{prefix}{connector}{directory_path.name}")

    def add_file_to_tree(self, file_path: Path, prefix: str, *, is_last: bool) -> None:
        connector = "└── " if is_last else "├── "
        rel = file_path.relative_to(self.base_path)
        line = f"{prefix}{connector}{file_path.name}"
        self.tree_output.append(line)
        self.file_tree_entries.append((len(self.tree_output) - 1, rel))

    def add_file(self, file_path: Path, lines: int, characters: int, content: str) -> None:
        if file_path.suffix == ".md":
            content = content.replace("```", r"\`\`\`")
        rel = file_path.relative_to(self.base_path)
        self.file_metadata[str(rel)] = (lines, characters)
        self.file_contents.extend([
            f'<file:content name="{rel}" lines="{lines}" chars="{characters}">',
            content,
            "</file:content>",
        ])
        self.total_lines += lines
        self.total_characters += characters

    def build_tree(self, include_metadata: bool = False) -> list[str]:
        output = []
        if include_metadata:
            # compute widths
            name_width = max(len(line) for line in self.tree_output)
            max_line = max((len(str(v[0])) for v in self.file_metadata.values()), default=1)
            max_char = max((len(str(v[1])) for v in self.file_metadata.values()), default=1)
            entry_map = dict(self.file_tree_entries)
            for idx, text in enumerate(self.tree_output):
                if idx in entry_map:
                    rel = entry_map[idx]
                    if str(rel) in self.file_metadata:
                        ln, ch = self.file_metadata[str(rel)]
                        marker = " "
                    else:
                        ln, ch = 0, 0
                        marker = "*"
                    padded = f"{text:<{name_width}} {ln:>{max_line}} {ch:>{max_char}} {marker}"
                    output.append(padded)
                else:
                    output.append(text)
        else:
            output = self.tree_output.copy()
        return [self.base_path.name, *output]

    def build_file_contents(self) -> str:
        return "\n".join(self.file_contents)


# Filter directory items
def filter_items(items: list[Path], paths: list[Path], patterns: list[str], base: Path) -> list[Path]:
    res = []
    for item in items:
        if not any(item.is_relative_to(p) for p in paths):
            continue
        if any(item.relative_to(base).match(pat) for pat in patterns):
            continue
        res.append(item)
    return sorted(res, key=lambda x: x.name)


# Traverse directory tree
def traverse_dir(
    path: Path, config: tuple[list[Path], list[str], Path], callback: Callable, prefix: str = ""
) -> None:
    paths, patterns, base = config
    for idx, item in enumerate(filter_items(list(path.iterdir()), paths, patterns, base)):
        last = idx == len(list(path.iterdir())) - 1
        callback(item, prefix, is_last=last)
        if item.is_dir():
            next_prefix = "    " if last else "│   "
            traverse_dir(item, config, callback, prefix + next_prefix)


# File helpers
def is_text(file_path: Path) -> bool:
    try:
        file_path.read_text(encoding="utf-8")
        return True
    except Exception:
        return False


def read_text(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        logger.exception("Reading %s failed", file_path)
        return ""


# Read old .groblignore


def read_groblignore(path: Path) -> list[str]:
    file = path / ".groblignore"
    if not file.exists():
        return []
    return [
        line.strip()
        for line in file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


# Read JSON config, with fallback to .groblignore


def read_config(path: Path) -> dict:
    cfg = DEFAULT_CONFIG.copy()
    config_file = path / CONFIG_FILENAME
    if config_file.exists():
        try:
            user_conf = json.loads(config_file.read_text(encoding="utf-8"))
            cfg.update(user_conf)
        except json.JSONDecodeError as e:
            logger.exception("Error parsing %s: %s", CONFIG_FILENAME, e)
    else:
        old = read_groblignore(path)
        if old:
            logger.warning("Detected .groblignore; use 'grobl migrate-config' to convert.")
            cfg["exclude_tree"] = old
    return cfg


# Migrate .groblignore to JSON config


def migrate_config(path: Path) -> None:
    config_file = path / CONFIG_FILENAME
    old = path / ".groblignore"
    if config_file.exists():
        print(f"{CONFIG_FILENAME} already exists.")
        return
    if not old.exists():
        print("No .groblignore found.")
        return
    patterns = read_groblignore(path)
    new_cfg = DEFAULT_CONFIG.copy()
    new_cfg["exclude_tree"] = patterns
    with config_file.open("w", encoding="utf-8") as f:
        json.dump(new_cfg, f, indent=2)
    print(f"Migrated .groblignore → {CONFIG_FILENAME}")


# Human-friendly summary
def human_summary(tree_lines: list[str], total_lines: int, total_chars: int) -> None:
    max_len = max(len(l) for l in tree_lines)
    title = " Project Summary "
    bar = "═" * ((max_len - len(title)) // 2)
    print(f"{bar}{title}{bar}")
    for l in tree_lines:
        print(l)
    print("─" * max_len)
    print(f"Total lines: {total_lines}")
    print(f"Total characters: {total_chars}")
    print("═" * max_len)


# Main processing: build tree, copy LLM output, print summary


def process_paths(paths: list[Path], cfg: dict, clipboard: ClipboardInterface) -> None:
    resolved = [p.resolve() for p in paths]
    common = find_common_ancestor(resolved)
    tree_patterns = cfg.get("exclude_tree", [])
    print_patterns = cfg.get("exclude_print", [])
    builder = DirectoryTreeBuilder(base_path=common, exclude_patterns=tree_patterns)

    def collect(item: Path, prefix: str, *, is_last: bool) -> None:
        if item.is_dir():
            builder.add_directory(item, prefix, is_last=is_last)
        elif item.is_file() and is_text(item):
            builder.add_file_to_tree(item, prefix, is_last=is_last)
            rel = item.relative_to(common)
            if not any(rel.match(p) for p in print_patterns):
                content = read_text(item)
                lines = len(content.splitlines())
                chars = len(content)
                builder.add_file(item, lines, chars, content)

    config_tuple = (resolved, tree_patterns, common)
    traverse_dir(common, config_tuple, collect)

    # Generate LLM-friendly XML
    tree_str = "\n".join(builder.build_tree())
    file_str = builder.build_file_contents()
    tree_tag = cfg.get("include_tree_tags")
    file_tag = cfg.get("include_file_tags")
    llm_output = (
        f"<{tree_tag}>\n{tree_str}\n</{tree_tag}>\n"
        f'<{file_tag} name="{common.name}">\n{file_str}\n</{file_tag}>'
    )
    clipboard.copy(llm_output)

    # Print human summary
    tree_with_meta = builder.build_tree(include_metadata=True)
    # Totals already computed only for included files
    human_summary(tree_with_meta, builder.total_lines, builder.total_characters)


# CLI entry point
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="grobl", description="Directory-to-Markdown utility with JSON config support"
    )
    subs = parser.add_subparsers(dest="command")
    subs.add_parser("migrate-config", help="Convert .groblignore to JSON config")
    args = parser.parse_args()
    base = Path()
    if args.command == "migrate-config":
        migrate_config(base)
        sys.exit(0)
    cfg = read_config(base)
    clipboard = PyperclipClipboard()
    process_paths([base], cfg, clipboard)


if __name__ == "__main__":
    main()
