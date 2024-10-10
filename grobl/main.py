import logging
import re
from collections.abc import Generator
from pathlib import Path

import pyperclip


class PathNotFoundError(Exception):
    pass


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

            if common_ancestor == common_ancestor.root:
                msg = "No common ancestor found"
                raise PathNotFoundError(msg)

    return common_ancestor


def match_exclude_patterns(path: Path, patterns: list[str]) -> bool:
    """Check if a path matches any of the exclude patterns using regex."""
    logging.debug("Checking path: %s against patterns: %s", path, patterns)
    for pattern in patterns:
        try:
            regex_pattern = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
            if re.fullmatch(regex_pattern, str(path)):
                return True
        except re.error:
            logging.exception("Regex error with pattern: %s", pattern)
    return False


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
                and not match_exclude_patterns(item, exclude_patterns)
            )
        ]
        for index, item in enumerate(sorted(items, key=lambda x: x.name)):
            connector = "├── " if index < len(items) - 1 else "└── "
            new_prefix = f"{prefix}{'|   ' if index < len(items) - 1 else '    '}"
            yield f"{prefix}{connector}{item.name}"
            if item.is_dir():
                yield from generate_subtree(item, new_prefix)

    yield from generate_subtree(common_ancestor, "")


def tree_structure_to_string(paths: list[Path], exclude_patterns: list[str] | None = None) -> str:
    return "\n".join(enumerate_file_tree(paths, exclude_patterns))


def is_text_file(file_path: Path) -> bool:
    text_file_extensions = {".py", ".md", ".txt", ".json", ".html", ".css", ".js", ".ts", ".rs", ".toml"}
    return file_path.suffix in text_file_extensions


def read_file_contents(file_path: Path) -> str:
    if not is_text_file(file_path):
        return ""
    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as file:
            return file.read()
    except FileNotFoundError:
        logging.exception("File not found: %s", file_path)
    except Exception:
        logging.exception("Error reading file %s", file_path)
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


def traverse_and_print_files(
    paths: list[Path],
    exclude_patterns: list[str] | None = None,
) -> tuple[str, str, int]:  # Return file output, terminal output, and total lines
    paths = [p.resolve() for p in paths]
    common_ancestor = find_common_ancestor(paths)
    exclude_patterns = exclude_patterns or []

    clipboard_output = []  # For the clipboard content
    terminal_output = []  # For the terminal summary
    total_lines = 0  # Initialize total line count

    def traverse_subtree(current_path: Path) -> None:
        nonlocal total_lines  # Use nonlocal to modify outer variable
        items = list(current_path.iterdir())
        items = [
            item
            for item in items
            if (
                any(item.is_relative_to(p) for p in paths)
                and not item.name.startswith(".")
                and not match_exclude_patterns(item, exclude_patterns)
            )
        ]
        for item in sorted(items, key=lambda x: x.name):
            if item.is_dir():
                traverse_subtree(item)
            elif item.is_file() and is_text_file(item):
                relative_path = item.relative_to(common_ancestor.parent)
                line_count = count_lines(item)  # Count lines
                clipboard_output.append(f"\n{relative_path}:")
                clipboard_output.append("```")
                clipboard_output.append(read_file_contents(item))
                clipboard_output.append("```")
                terminal_output.append(f"{relative_path}: ({line_count} lines)")
                total_lines += line_count  # Add to total line count

    traverse_subtree(common_ancestor)
    return "\n".join(clipboard_output), "\n".join(terminal_output), total_lines  # Return outputs


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


def main():
    setup_logging()

    paths = [Path(p) for p in ["./"]]
    ignore_patterns = read_groblignore(Path(".groblignore"))

    tree_output = tree_structure_to_string(paths, ignore_patterns)
    files_output, terminal_output, total_lines = traverse_and_print_files(paths, ignore_patterns)

    final_output = f"{tree_output}\n\n{files_output}"

    pyperclip.copy(final_output)  # Copy the output to clipboard without line counts
    print("Output copied to clipboard")

    # Print summary with line counts for terminal
    print_summary(terminal_output, total_lines)


if __name__ == "__main__":
    main()
