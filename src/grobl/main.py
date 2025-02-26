import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pyperclip

# Centralized error messages
ERROR_MSG_NO_COMMON_ANCESTOR = "No common ancestor found"
ERROR_MSG_EMPTY_PATHS = "The list of paths is empty"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Utility function for escaping Markdown characters
def escape_markdown(text: str) -> str:
    """Escape Markdown special characters in a string."""
    markdown_chars = r"([*_#\[\]{}()>+-.!])"
    return re.sub(markdown_chars, r"\\\1", text)


# Custom exceptions for specific errors
class PathNotFoundError(Exception):
    pass


# Clipboard abstraction for flexibility in testing
class ClipboardInterface:
    def copy(self, content: str) -> None:
        raise NotImplementedError


class PyperclipClipboard(ClipboardInterface):
    def copy(self, content: str) -> None:  # noqa: PLR6301
        pyperclip.copy(content)


# Core utility for finding a common ancestor path
def find_common_ancestor(paths: list[Path]) -> Path:
    """Find the common ancestor directory for a list of paths."""
    if not paths:
        raise ValueError(ERROR_MSG_EMPTY_PATHS)

    common_ancestor = paths[0].resolve()
    for path in map(Path.resolve, paths[1:]):
        while not path.is_relative_to(common_ancestor):
            common_ancestor = common_ancestor.parent
            if common_ancestor == Path("/"):
                raise PathNotFoundError(ERROR_MSG_NO_COMMON_ANCESTOR)
    return common_ancestor


# Directory tree builder class
@dataclass
class DirectoryTreeBuilder:
    base_path: Path
    exclude_patterns: list[str]
    tree_output: list[str] = field(default_factory=list)
    file_contents: list[str] = field(default_factory=list)
    file_metadata: list[str] = field(default_factory=list)
    total_lines: int = 0
    total_characters: int = 0

    def add_file(self, file_path: Path, lines: int, characters: int, content: str) -> None:
        """Add file metadata and contents to the builder."""
        if file_path.suffix == "md":
            content = content.replace("```", r"\`\`\`")

        relative_path = file_path.relative_to(self.base_path)
        self.file_metadata.append(f"{relative_path}: ({lines} lines | {characters} characters)")
        self.file_contents.extend([f"\n{relative_path}:", "```", content, "```"])
        self.total_lines += lines
        self.total_characters += characters

    def add_file_to_tree(self, file_path: Path, prefix: str, *, is_last: bool) -> None:
        """Add a file entry to the tree output."""
        connector = "└── " if is_last else "├── "
        self.tree_output.append(f"{prefix}{connector}{escape_markdown(file_path.name)}")

    def add_directory(self, directory_path: Path, prefix: str, *, is_last: bool) -> None:
        """Add a directory entry to the tree output."""
        connector = "└── " if is_last else "├── "
        self.tree_output.append(f"{prefix}{connector}{escape_markdown(directory_path.name)}")

    def build_tree(self) -> str:
        """Build the full directory tree as a string."""
        return "\n".join([self.base_path.name, *self.tree_output])

    def build_file_contents(self) -> str:
        """Build the collected file contents as a string."""
        return "\n".join(self.file_contents)

    def build_metadata(self) -> str:
        """Build the collected file metadata as a string."""
        return "\n".join(self.file_metadata)

    def get_totals(self) -> tuple[int, int]:
        """Get the total lines and characters."""
        return self.total_lines, self.total_characters


# Filter files and directories based on exclude patterns
def filter_items(
    items: list[Path], paths: list[Path], exclude_patterns: list[str], base_path: Path
) -> list[Path]:
    """Filter directory items based on inclusion paths and exclude patterns."""
    filtered = []
    for item in items:
        is_included = any(item.is_relative_to(p) for p in paths)
        is_excluded = match_exclude_patterns(item, exclude_patterns, base_path)
        if is_included and not is_excluded and not item.name.startswith("."):
            filtered.append(item)
    return filtered


def match_exclude_patterns(path: Path, patterns: list[str], base_path: Path) -> bool:
    """Check if a path matches any exclude patterns."""
    relative_path = path.relative_to(base_path)
    return any(relative_path.match(pattern) for pattern in patterns)


@dataclass
class TraversalConfig:
    paths: list[Path]
    exclude_patterns: list[str]
    base_path: Path


def traverse_directory_tree(
    current_path: Path,
    config: TraversalConfig,
    callback: Callable[[Path, str, bool], None],
    prefix: str = "",
) -> None:
    items = filter_items(
        list(current_path.iterdir()), config.paths, config.exclude_patterns, config.base_path
    )
    sorted_items = sorted(items, key=lambda x: x.name)
    for index, item in enumerate(sorted_items):
        is_last = index == len(sorted_items) - 1
        callback(item, prefix, is_last=is_last)
        if item.is_dir():
            new_prefix = f"{prefix}    " if is_last else f"{prefix}|   "
            traverse_directory_tree(
                item,
                config,
                callback,
                new_prefix,
            )


# Reading file contents and line counts
def is_text_file(file_path: Path) -> bool:
    """Determine if a file is a readable text file."""
    try:
        with file_path.open("r", encoding="utf-8") as f:
            f.read()
    except (UnicodeDecodeError, FileNotFoundError, OSError):
        return False
    return True


def read_file_contents(file_path: Path) -> str:
    """Read the contents of a file."""
    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as file:
            return file.read()
    except Exception:
        logger.exception("Error reading file %s", file_path)
    return ""


def count_lines(file_path: Path) -> tuple[int, int]:
    """Count the number of lines and characters in a file."""
    try:
        content = read_file_contents(file_path)
        return len(content.splitlines()), len(content)
    except Exception:
        logger.exception("Error reading file for line count %s", file_path)
    return 0, 0


# Main processing logic
def process_paths(paths: list[Path], exclude_patterns: list[str], clipboard: ClipboardInterface) -> None:
    """Process the given paths to generate and copy outputs."""
    # Resolve paths and find common ancestor
    resolved_paths = [p.resolve() for p in paths]
    common_ancestor = find_common_ancestor(resolved_paths)

    # Initialize the builder
    builder = DirectoryTreeBuilder(base_path=common_ancestor, exclude_patterns=exclude_patterns)

    # Traverse the directory tree
    def collect_data(item: Path, prefix: str, *, is_last: bool) -> None:
        if item.is_dir():
            builder.add_directory(item, prefix, is_last=is_last)
        elif item.is_file() and is_text_file(item):
            builder.add_file_to_tree(item, prefix, is_last=is_last)  # Include files in the tree
            lines, characters = count_lines(item)
            content = read_file_contents(item)
            builder.add_file(item, lines, characters, content)

    traverse_directory_tree(
        common_ancestor, TraversalConfig(resolved_paths, exclude_patterns, common_ancestor), collect_data
    )

    # Generate outputs
    tree_output = builder.build_tree()
    file_contents = builder.build_file_contents()
    metadata_output = builder.build_metadata()
    total_lines, total_characters = builder.get_totals()

    final_output = f"{tree_output}\n\n{file_contents}"

    # Copy to clipboard and print
    clipboard.copy(final_output)
    print("Output copied to clipboard")
    print_summary(metadata_output, total_lines, total_characters)


def read_groblignore(path: Path) -> list[str]:
    """Read the .groblignore file and return patterns to ignore."""
    ignore_patterns = [
        ".groblignore",
        ".gitignore",
        ".git/",
        ".gitmodules/",
        ".venv/",
        ".python-version",
        "package-lock.json",
        "uv.lock",
        "build/",
        "dist/",
        "node_modules/",
        "__pycache__/",
        ".mypy_cache/",
        ".pytest_cache/",
        "cov.xml",
        "ruff.toml",
    ]
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            ignore_patterns.extend([
                line.strip() for line in file if line.strip() and not line.startswith("#")
            ])
    return list(set(ignore_patterns))


def print_summary(metadata: str, total_lines: int, total_characters: int) -> None:
    """Print a summary of the processed content."""
    print("\n--- Summary of Copied Content ---")
    print(metadata)
    print(f"\nTotal Lines: {total_lines}")
    print(f"Total Characters: {total_characters}")
    print("---------------------------------")


# Main entry point
def main() -> None:
    paths = [Path(p) for p in ["./"]]
    ignore_patterns = read_groblignore(Path(".groblignore"))
    clipboard = PyperclipClipboard()
    process_paths(paths, ignore_patterns, clipboard)


if __name__ == "__main__":
    main()
