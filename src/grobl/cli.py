import argparse
import sys
from pathlib import Path

from .clipboard import ClipboardInterface, PyperclipClipboard, StdoutClipboard
from .config import migrate_config, read_config
from .directory import DirectoryTreeBuilder, traverse_dir
from .errors import ConfigLoadError
from .formatter import human_summary
from .utils import find_common_ancestor, is_text, read_text


def process_paths(
    paths: list[Path],
    cfg: dict,
    clipboard: ClipboardInterface,
    builder: DirectoryTreeBuilder | None = None,
) -> DirectoryTreeBuilder:
    resolved = [p.resolve() for p in paths]
    common = find_common_ancestor(resolved)

    excl_tree = cfg.get("exclude_tree", [])
    excl_print = cfg.get("exclude_print", [])

    if builder is None:
        builder = DirectoryTreeBuilder(base_path=common, exclude_patterns=excl_tree)
    else:
        builder.base_path = common  # ensure base_path is set correctly
        # keep existing exclude patterns - ``traverse_dir`` handles filtering

    current_item: dict[str, Path | None] = {
        "path": None
    }  # Mutable container to track current file/dir

    def collect(item: Path, prefix: str, *, is_last: bool) -> None:
        current_item["path"] = item
        if item.is_dir():
            builder.add_directory(item, prefix, is_last=is_last)
        elif item.is_file():
            builder.add_file_to_tree(item, prefix, is_last=is_last)
            rel = item.relative_to(common)
            if is_text(item):
                content = read_text(item)
                ln, ch = len(content.splitlines()), len(content)
                builder.record_metadata(rel, ln, ch)
                if not any(rel.match(p) for p in excl_print):
                    builder.add_file(item, rel, ln, ch, content)
            else:
                builder.record_metadata(rel, 0, item.stat().st_size)

    config_tuple = ([p.resolve() for p in paths], excl_tree, common)
    traverse_dir(common, config_tuple, collect)

    tree_xml = "\n".join(builder.build_tree())
    files_xml = builder.build_file_contents()
    ttag = cfg.get("include_tree_tags")
    ftag = cfg.get("include_file_tags")
    llm_out = (
        f'<{ttag} root="{common.name}">\n{tree_xml}\n</{ttag}>\n'
        f'<{ftag} root="{common.name}">\n{files_xml}\n</{ftag}>'
    )
    clipboard.copy(llm_out)

    summary = builder.build_tree(include_metadata=True)
    human_summary(summary, builder.total_lines, builder.total_characters)
    return builder


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
        "--no-groblignore",
        action="store_false",
        dest="use_groblignore",
        help="Do not merge patterns from .groblignore",
    )
    parser.add_argument("paths", nargs="*", type=Path, help="Directories to scan")
    parser.add_argument(
        "--no-clipboard",
        action="store_true",
        help="Print output to stdout instead of copying to clipboard",
    )
    parser.add_argument("--output", type=Path, help="Write output to a file")
    parser.add_argument(
        "--add-ignore",
        action="append",
        default=[],
        help="Additional ignore pattern for this run",
    )
    parser.add_argument(
        "--remove-ignore",
        action="append",
        default=[],
        help="Ignore pattern to remove for this run",
    )
    subs = parser.add_subparsers(dest="command")
    mig = subs.add_parser(
        "migrate-config", help="Migrate existing JSON or .groblignore → new TOML config"
    )
    mig.add_argument(
        "--yes", action="store_true", help="Delete old files without prompting"
    )
    mig.add_argument("--stdout", action="store_true", help="Print new config to stdout")

    args = parser.parse_args()
    cwd = Path()

    if args.command == "migrate-config":
        migrate_config(cwd, assume_yes=args.yes, to_stdout=args.stdout)
        sys.exit(0)

    paths = args.paths or [cwd]
    if args.ignore_defaults:
        common_dirs = {"node_modules", "venv", ".venv", "env", "site-packages"}
        for p in paths:
            for d in common_dirs:
                if (p / d).exists():
                    resp = (
                        input(
                            f"Warning: scanning may include '{d}', which can be large. Continue? (y/N): "
                        )
                        .strip()
                        .lower()
                    )
                    if resp != "y":
                        sys.exit(1)
                    break
            else:
                continue
            break

    try:
        cfg = read_config(
            base_path=cwd,
            ignore_default=args.ignore_defaults,
            use_groblignore=args.use_groblignore,
        )
    except ConfigLoadError as err:
        print(err, file=sys.stderr)
        sys.exit(1)

    for pat in args.add_ignore:
        cfg.setdefault("exclude_tree", [])
        if pat not in cfg["exclude_tree"]:
            cfg["exclude_tree"].append(pat)
    for pat in args.remove_ignore:
        if pat in cfg.get("exclude_tree", []):
            cfg["exclude_tree"].remove(pat)

    clipboard: ClipboardInterface
    if args.output:
        clipboard = StdoutClipboard(args.output)
    elif args.no_clipboard:
        clipboard = StdoutClipboard()
    else:
        clipboard = PyperclipClipboard(fallback=StdoutClipboard())

    builder = DirectoryTreeBuilder(
        base_path=cwd, exclude_patterns=cfg.get("exclude_tree", [])
    )

    try:
        process_paths(paths, cfg, clipboard, builder)
    except KeyboardInterrupt:
        print("\nInterrupted by user. Dumping debug info:")
        print(f"cwd: {cwd}")
        print(f"exclude_tree: {cfg.get('exclude_tree')}")
        print(f"exclude_print: {cfg.get('exclude_print')}")

        print("DirectoryTreeBuilder(")
        print(f"    base_path         = {builder.base_path}")
        print(f"    total_lines       = {builder.total_lines}")
        print(f"    total_characters  = {builder.total_characters}")
        # print(f"    exclude_patterns  = {builder.exclude_patterns}")
        # print(f"    tree_output       = {builder.tree_output}")
        # print(f"    all_metadata      = {builder.all_metadata}")
        # print(f"    included_metadata = {builder.included_metadata}")
        # print(f"    file_contents     = {builder.file_contents}")
        print(f"    file_tree_entries = {builder.file_tree_entries}")
        print(")")

        raise


if __name__ == "__main__":
    main()
