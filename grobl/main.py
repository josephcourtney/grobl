import argparse
import tomllib
from collections.abc import Generator
from pathlib import Path

import pyperclip


class PathNotFoundError(Exception):
    pass


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


def enumerate_file_tree(
    paths: list[Path], exclude_patterns: list[str] | None = None
) -> Generator[str, None, None]:
    paths = [p.resolve() for p in paths]
    common_ancestor = find_common_ancestor(paths)
    yield common_ancestor.name

    def generate_subtree(current_path: Path, prefix: str):
        items = list(current_path.iterdir())
        items = [
            item
            for item in items
            if (
                any(item.is_relative_to(p) for p in paths)
                and not item.name.startswith(".")
                and not any(item.match(pattern) for pattern in exclude_patterns)
            )
        ]
        for index, item in enumerate(sorted(items, key=lambda x: x.name)):
            connector = "├── " if index < len(items) - 1 else "└── "
            yield f"{prefix}{connector}{item.name}"
            if item.is_dir():
                new_prefix = f"{prefix}{"│   " if index < len(items) - 1 else "    "}"
                yield from generate_subtree(item, new_prefix)

    yield from generate_subtree(common_ancestor, "")


def tree_structure_to_string(paths: list[Path], exclude_patterns: list[str] | None = None) -> str:
    return "\n".join(enumerate_file_tree(paths, exclude_patterns))


def is_text_file(file_path: Path) -> bool:
    text_file_extensions = {".py", ".md", ".txt", ".json", ".html", ".css", ".js"}
    return file_path.suffix in text_file_extensions


def read_file_contents(file_path: Path) -> str:
    with file_path.open("r", encoding="utf-8", errors="ignore") as file:
        return file.read()


def traverse_and_print_files(
    paths: list[Path],
    exclude_patterns: list[str] | None = None,
    exclude_files_from_printing: list[str] | None = None,
) -> str:
    paths = [p.resolve() for p in paths]
    common_ancestor = find_common_ancestor(paths)
    exclude_files_from_printing = exclude_files_from_printing or []
    output = []

    def traverse_subtree(current_path: Path):
        items = list(current_path.iterdir())
        items = [
            item
            for item in items
            if (
                any(item.is_relative_to(p) for p in paths)
                and not item.name.startswith(".")
                and not any(item.match(pattern) for pattern in exclude_patterns)
            )
        ]
        for item in sorted(items, key=lambda x: x.name):
            if item.is_dir():
                traverse_subtree(item)
            elif (
                item.is_file()
                and is_text_file(item)
                and not any(item.match(pattern) for pattern in exclude_files_from_printing)
            ):
                relative_path = item.relative_to(common_ancestor.parent)
                output.append(f"\n{relative_path}:\n```")
                output.append(read_file_contents(item))
                output.append("```")

    traverse_subtree(common_ancestor)
    return "\n".join(output)


def parse_pyproject_toml(path: Path) -> dict[str, list[str]]:
    config = {"exclude_tree": [], "exclude_print": []}
    if path.exists():
        with path.open("rb") as file:
            data = tomllib.load(file)
            tool_settings = data.get("tool", {}).get("grobl", {})
            config["exclude_tree"] = tool_settings.get("exclude_tree", [])
            config["exclude_print"] = tool_settings.get("exclude_print", [])
    return config


def gather_configs(paths: list[Path]) -> dict[str, list[str]]:
    common_ancestor = find_common_ancestor(paths)
    current_path = common_ancestor

    final_config = {"exclude_tree": [], "exclude_print": []}

    while current_path != current_path.parent:
        config_path = current_path / "pyproject.toml"
        config = parse_pyproject_toml(config_path)
        final_config["exclude_tree"].extend(config["exclude_tree"])
        final_config["exclude_print"].extend(config["exclude_print"])
        current_path = current_path.parent

    return final_config


def main():
    parser = argparse.ArgumentParser(
        description="Generate a file tree and print contents of valid text files."
    )
    parser.add_argument("paths", nargs="+", type=Path, help="List of file paths to include in the tree")
    parser.add_argument(
        "--exclude-tree", nargs="*", default=[], help="Patterns to exclude from the tree display"
    )
    parser.add_argument(
        "--exclude-print", nargs="*", default=[], help="Patterns to exclude from file printing"
    )
    args = parser.parse_args()

    # Default patterns
    default_exclude_tree = ["*.jsonl", "*.jsonl.*", "tests/*", "cov.xml", "*.log", "*.tmp"]
    default_exclude_print = ["*.json", "*.html"]

    # Gather configurations from pyproject.toml files
    configs = gather_configs(args.paths)

    # Merge CLI arguments with pyproject.toml configurations and default values
    exclude_tree_patterns = configs["exclude_tree"] + args.exclude_tree or default_exclude_tree
    exclude_print_patterns = configs["exclude_print"] + args.exclude_print or default_exclude_print

    tree_output = tree_structure_to_string(args.paths, exclude_tree_patterns)
    files_output = traverse_and_print_files(args.paths, exclude_tree_patterns, exclude_print_patterns)

    final_output = f"{tree_output}\n\n{files_output}"
    pyperclip.copy(final_output)
    print("Output copied to clipboard")


if __name__ == "__main__":
    main()
