import argparse
import sys
from pathlib import Path

from .clipboard import ClipboardInterface, PyperclipClipboard
from .config import migrate_config, read_config
from .directory import DirectoryTreeBuilder, traverse_dir
from .errors import ConfigLoadError
from .formatter import human_summary
from .utils import find_common_ancestor, is_text, read_text


def process_paths(
    paths: list[Path],
    cfg: dict,
    clipboard: ClipboardInterface,
    builder: DirectoryTreeBuilder,
) -> None:
    resolved = [p.resolve() for p in paths]
    common = find_common_ancestor(resolved)

    builder.base_path = common  # ensure base_path is set correctly

    excl_tree = cfg.get("exclude_tree", [])
    excl_print = cfg.get("exclude_print", [])
    current_item = {"path": None}  # Mutable container to track current file/dir

    def collect(item: Path, prefix: str, *, is_last: bool) -> None:
        current_item["path"] = item
        if item.is_dir():
            builder.add_directory(item, prefix, is_last=is_last)
        elif item.is_file():
            builder.add_file_to_tree(item, prefix, is_last=is_last)
            if is_text(item):
                rel = item.relative_to(common)
                content = read_text(item)
                ln, ch = len(content.splitlines()), len(content)
                builder.record_metadata(rel, ln, ch)
                if not any(rel.match(p) for p in excl_print):
                    builder.add_file(item, rel, ln, ch, content)

    config_tuple = ([p.resolve() for p in paths], excl_tree, common)
    traverse_dir(common, config_tuple, collect)

    tree_xml = "\n".join(builder.build_tree())
    files_xml = builder.build_file_contents()
    ttag = cfg.get("include_tree_tags")
    ftag = cfg.get("include_file_tags")
    llm_out = f'<{ttag}>\n{tree_xml}\n</{ttag}>\n<{ftag} name="{common.name}">\n{files_xml}\n</{ftag}>'
    clipboard.copy(llm_out)

    summary = builder.build_tree(include_metadata=True)
    human_summary(summary, builder.total_lines, builder.total_characters)

    # Return useful state for debug
    return current_item["path"], common

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="grobl",
        description="Directory-to-Markdown utility with TOML config support",
    )
    parser.add_argument(
        "--ignore-defaults",
        "-I",
        action="store_true",
        help="Ignore bundled default exclude patterns",
    )
    parser.add_argument(
        "--no-gitignore",
        action="store_false",
        dest="use_gitignore",
        help="Do not merge patterns from .gitignore",
    )
    subs = parser.add_subparsers(dest="command")
    subs.add_parser("migrate-config", help="Migrate existing JSON or .groblignore → new TOML config")

    args = parser.parse_args()
    cwd = Path()

    if args.command == "migrate-config":
        migrate_config(cwd)
        sys.exit(0)

    try:
        cfg = read_config(
            base_path=cwd, ignore_default=args.ignore_defaults, use_gitignore=args.use_gitignore
        )
    except ConfigLoadError as err:
        print(err, file=sys.stderr)
        sys.exit(1)

    clipboard = PyperclipClipboard()
    builder = DirectoryTreeBuilder(base_path=cwd, exclude_patterns=cfg.get("exclude_tree", []))

    try:
        last_item, common = process_paths([cwd], cfg, clipboard, builder)
    except KeyboardInterrupt:
        print("\nInterrupted by user. Dumping debug info:")
        print(f"cwd: {cwd}")
        print(f"common ancestor: {common}")
        print(f"last item: {last_item}")
        print(f"exclude_tree: {cfg.get('exclude_tree')}")
        print(f"exclude_print: {cfg.get('exclude_print')}")
        print(f"files seen: {len(builder.file_tree_entries)}")
        print(f"total lines: {builder.total_lines}")
        print(f"total characters: {builder.total_characters}")
        sys.exit(130)

if __name__ == "__main__":
    main()
