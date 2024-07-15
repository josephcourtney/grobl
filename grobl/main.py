import argparse
import json
import logging
import re
import tomllib
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
    logging.debug(f"Checking path: {path} against patterns: {patterns}")
    for pattern in patterns:
        try:
            # Escape special characters in pattern and replace wildcard characters with regex equivalents
            regex_pattern = re.escape(pattern).replace(r'\*', '.*').replace(r'\?', '.')
            if re.fullmatch(regex_pattern, str(path)):
                return True
        except re.error as e:
            logging.error(f"Regex error with pattern: {pattern} - {e}")
    return False


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
                and not match_exclude_patterns(item, exclude_patterns)
            )
        ]
        for index, item in enumerate(sorted(items, key=lambda x: x.name)):
            connector = "├── " if index < len(items) - 1 else "└── "
            yield f"{prefix}{connector}{item.name}"
            if item.is_dir():
                new_prefix = f"{prefix}{'│   ' if index < len(items) - 1 else '    '}"
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
        logging.error(f"File not found: {file_path}")
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
    return ""


def traverse_and_print_files(
    paths: list[Path],
    exclude_patterns: list[str] | None = None,
    exclude_files_from_printing: list[str] | None = None,
    file_type_patterns: list[str] | None = None,
) -> str:
    paths = [p.resolve() for p in paths]
    common_ancestor = find_common_ancestor(paths)
    exclude_patterns = exclude_patterns or []
    exclude_files_from_printing = exclude_files_from_printing or []
    output = []

    def traverse_subtree(current_path: Path) -> None:
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
            elif (
                item.is_file()
                and is_text_file(item)
                and not match_exclude_patterns(item, exclude_files_from_printing)
                and (not file_type_patterns or match_exclude_patterns(item, file_type_patterns))
            ):
                relative_path = item.relative_to(common_ancestor.parent)
                output.append(f"\n{relative_path}:")
                output.append("```")
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


def detect_project_types(paths: list[Path], project_types_config: dict) -> list[str]:
    project_types = set()
    for path in paths:
        for project_type, markers in project_types_config.items():
            if any((path / marker).exists() for marker in markers):
                project_types.add(project_type)
    return list(project_types)


def read_config_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main():
    setup_logging()

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
    parser.add_argument(
        "--output-format",
        choices=["plain", "json", "markdown"],
        default="plain",
        help="Specify the output format",
    )
    parser.add_argument("--config-file", type=Path, help="Path to a configuration file (JSON)")
    parser.add_argument(
        "--file-types", nargs="*", default=[], help="Patterns to include specific file types for printing"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Set logging level based on debug flag
    if args.debug:
        setup_logging(logging.DEBUG)
    else:
        setup_logging(logging.INFO)

    # Load configuration from file if provided
    config_file_settings = {}
    if args.config_file:
        config_file_settings = read_config_file(args.config_file)

    project_types_config = config_file_settings.get("project_types", {})
    ignore_patterns = config_file_settings.get("ignore_patterns", {})

    # Gather configurations from pyproject.toml files
    configs = gather_configs(args.paths)

    # Detect project types
    project_types = detect_project_types(args.paths, project_types_config)

    # Merge exclusion patterns for all detected project types
    project_exclude_patterns = []
    for project_type in project_types:
        project_exclude_patterns.extend(ignore_patterns.get(project_type, {}).get("exclude_tree", []))

    # Merge CLI arguments with pyproject.toml configurations, config file, and default values
    exclude_tree_patterns = (
        configs["exclude_tree"] + args.exclude_tree + config_file_settings.get("exclude_tree", [])
        or project_exclude_patterns
    )
    exclude_print_patterns = (
        configs["exclude_print"] + args.exclude_print + config_file_settings.get("exclude_print", []) or []
    )

    # Combine the exclusion patterns for tree and print
    combined_exclude_patterns = list(set(exclude_tree_patterns + exclude_print_patterns))

    tree_output = tree_structure_to_string(args.paths, combined_exclude_patterns)
    files_output = traverse_and_print_files(
        args.paths, combined_exclude_patterns, combined_exclude_patterns, args.file_types
    )

    final_output = f"{tree_output}\n\n{files_output}"

    if args.output_format == "json":
        final_output = json.dumps({"tree": tree_output, "files": files_output}, indent=4)
    elif args.output_format == "markdown":
        final_output = f"## Directory Tree\n```\n{tree_output}\n```\n## File Contents\n{files_output}"

    pyperclip.copy(final_output)
    print("Output copied to clipboard")


if __name__ == "__main__":
    main()
