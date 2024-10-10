import logging
from collections.abc import Callable, Generator
from pathlib import Path

import pyperclip


class PathNotFoundError(Exception):
    pass


class ClipboardHandler:
    @staticmethod
    def copy(content: str) -> None:
        pyperclip.copy(content)


def setup_logging(level=logging.INFO):
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")


def find_common_ancestor(paths: list[Path]) -> Path:
    if not paths:
        msg = "The list of paths is empty"
        raise ValueError(msg)

    common_ancestor = Path(paths[0]).resolve()

    for _path in paths[1:]:
        path = Path(_path).resolve()
        while not path.is_relative_to(common_ancestor):
            common_ancestor = common_ancestor.parent

            if common_ancestor == Path("/"):
                msg = "No common ancestor found"
                raise PathNotFoundError(msg)

    return common_ancestor


def match_exclude_patterns(path: Path, patterns: list[str], base_path: Path) -> bool:
    """Check if a path matches any of the exclude patterns using Path.match."""
    relative_path = path.relative_to(base_path)
    return any(relative_path.match(pattern) for pattern in patterns)


def traverse_directory_tree(
    current_path: Path,
    paths: list[Path],
    exclude_patterns: list[str],
    base_path: Path,
    callback: Callable[[Path], None]
) -> None:
    items = _get_filtered_items(current_path, paths, exclude_patterns, base_path)  # Removed 'self'
    for item in sorted(items, key=lambda x: x.name):
        callback(item)
        if item.is_dir():
            traverse_directory_tree(item, paths, exclude_patterns, base_path, callback)


def _get_filtered_items(current_path: Path, paths: list[Path], exclude_patterns: list[str], base_path: Path) -> list[Path]:
    return [
        item for item in current_path.iterdir()
        if (
            any(item.is_relative_to(p) for p in paths)
            and not item.name.startswith(".")
            and not match_exclude_patterns(item, exclude_patterns, base_path)
        )
    ]


def enumerate_file_tree(
    paths: list[Path], exclude_patterns: list[str] | None = None
) -> Generator[str, None, None]:
    paths = [p.resolve() for p in paths]
    common_ancestor = find_common_ancestor(paths)
    yield common_ancestor.name

    def generate_subtree(current_path: Path, prefix: str) -> Generator[str, None, None]:
        items = list(current_path.iterdir())
        items = [
            item
            for item in items
            if (
                any(item.is_relative_to(p) for p in paths)
                and not item.name.startswith(".")
                and not match_exclude_patterns(item, exclude_patterns, common_ancestor)
            )
        ]
        for index, item in enumerate(sorted(items, key=lambda x: x.name)):
            connector = "├── " if index < len(items) - 1 else "└── "
            new_prefix = f"{prefix}{'|   ' if index < len(items) - 1 else '    '}"
            yield f"{prefix}{connector}{item.name}"
            if item.is_dir() and not match_exclude_patterns(item, exclude_patterns, common_ancestor):
                yield from generate_subtree(item, new_prefix)

    yield from generate_subtree(common_ancestor, "")


def tree_structure_to_string(paths: list[Path], exclude_patterns: list[str] | None = None) -> str:
    return "\n".join(enumerate_file_tree(paths, exclude_patterns))


def is_text_file(file_path: Path) -> bool:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read()
        return True
    except (UnicodeDecodeError, FileNotFoundError, OSError) as e:
        return False


def read_file_contents(file_path: Path) -> str:
    if not is_text_file(file_path):
        return ""
    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as file:
            return file.read()
    except FileNotFoundError:
        logging.exception("File not found: %s", file_path)  # Replaced f-string with % formatting
    except Exception:
        logging.exception("Error reading file %s", file_path)  # Replaced f-string with % formatting
    return ""


def count_lines(file_path: Path) -> int:
    """Count the number of lines in a file."""
    if not file_path.is_file():
        return 0
    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as file:
            return sum(1 for _ in file)
    except Exception:
        logging.exception("Error reading file for line count %s", file_path)
    return 0


def collect_file_data(item: Path, common_ancestor: Path, clipboard_output: list[str], terminal_output: list[str], total_lines: int) -> int:
    if item.is_file() and is_text_file(item):
        relative_path = item.relative_to(common_ancestor.parent)
        line_count = count_lines(item)  # Count lines
        clipboard_output.extend((f"\n{relative_path}:", "```", read_file_contents(item), "```"))
        terminal_output.append(f"{relative_path}: ({line_count} lines)")
        total_lines += line_count  # Add to total line count
    return total_lines


def traverse_and_collect(
        paths: list[Path],
        exclude_patterns: list[str],
        callback: Callable[[Path], None]
) -> None:
    common_ancestor = find_common_ancestor(paths)
    traverse_directory_tree(common_ancestor, paths, exclude_patterns, common_ancestor, callback)


def traverse_and_print_files(
    paths: list[Path],
    exclude_patterns: list[str] | None = None,
) -> tuple[str, str, int]:
    # Ensure paths are resolved
    paths = [p.resolve() for p in paths]
    common_ancestor = find_common_ancestor(paths)
    exclude_patterns = exclude_patterns or []

    clipboard_output = []
    terminal_output = []
    total_lines = 0

    def collect_file_data_wrapper(item: Path) -> None:
        nonlocal total_lines, clipboard_output, terminal_output
        total_lines = collect_file_data(item, common_ancestor, clipboard_output, terminal_output, total_lines)

    # Shorten line length
    traverse_directory_tree(
        common_ancestor, paths, exclude_patterns, common_ancestor, collect_file_data_wrapper
    )

    return "\n".join(clipboard_output), "\n".join(terminal_output), total_lines


def read_groblignore(path: Path) -> list[str]:
    """Read the .groblignore file and return a list of patterns to ignore."""
    ignore_patterns = []
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            ignore_patterns = [line.strip() for line in file if line.strip() and not line.startswith("#")]
    return ignore_patterns


def print_summary(file_tree: str, total_lines: int) -> None:
    """Print the summary of the copied content."""
    print("\n--- Summary of Copied Content ---")
    print(file_tree)
    print(f"\nTotal Lines Copied: {total_lines}")
    print("---------------------------------")


def copy_to_clipboard(content: str) -> None:
    """Abstract clipboard functionality for easier testing."""
    pyperclip.copy(content)


def main():
    setup_logging()

    paths = [Path(p) for p in ["./"]]
    ignore_patterns = read_groblignore(Path(".groblignore"))

    tree_output = tree_structure_to_string(paths, ignore_patterns)
    files_output, terminal_output, total_lines = traverse_and_print_files(paths, ignore_patterns)

    final_output = f"{tree_output}\n\n{files_output}"

    clipboard_handler = ClipboardHandler()
    clipboard_handler.copy(final_output)  # Copy the output to clipboard without line counts
    print("Output copied to clipboard")

    print_summary(terminal_output, total_lines)


if __name__ == "__main__":
    main()
