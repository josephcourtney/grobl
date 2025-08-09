import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from .clipboard import ClipboardInterface, PyperclipClipboard, StdoutClipboard
from .config import migrate_config, read_config
from .directory import DirectoryTreeBuilder, traverse_dir
from .editor import interactive_edit_config
from .errors import ConfigLoadError
from .formatter import human_summary
from .tokens import (
    TokenizerNotAvailableError,
    count_tokens,
    load_cache,
    load_tokenizer,
    save_cache,
)
from .utils import find_common_ancestor, is_text, read_text

# Mapping of known model names to their input token limits. These values are
# based on published OpenAI model specifications. The ``default`` tier is used
# when no explicit subscription tier is supplied (e.g. ``gpt-4o``). Additional
# tiers can be specified using ``model:tier`` syntax, such as ``gpt-4o:plus``.
MODEL_TOKEN_LIMITS: dict[str, dict[str, int]] = {
    "gpt-4o": {"default": 128_000},
    "gpt-4o-mini": {"default": 64_000},
    "gpt-4.1": {"default": 128_000},
    "gpt-4.1-mini": {"default": 128_000},
    # Future models can be added here as they become available. Tests may
    # monkeypatch this mapping for custom scenarios.
}


def process_paths(
    paths: list[Path],
    cfg: dict,
    clipboard: ClipboardInterface,
    builder: DirectoryTreeBuilder | None = None,
    *,
    tokens: bool = False,
    tokenizer_name: str = "o200k_base",
    tokens_for: str = "printed",
    budget: int | None = None,
    force_tokens: bool = False,
    verbose: bool = False,
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
    assert builder is not None
    builder_local = builder

    def _zero(_text: str) -> int:
        return 0

    tokenizer_fn: Callable[[str], int] = _zero
    token_cache: dict[str, dict[str, int]] = {}
    cache_path = common / ".grobl.tokens.json"
    if tokens:
        try:
            tokenizer_fn = load_tokenizer(tokenizer_name)
        except TokenizerNotAvailableError as err:
            print(err, file=sys.stderr)
            sys.exit(1)
        except ValueError as err:
            print(err, file=sys.stderr)
            sys.exit(1)
        token_cache = load_cache(cache_path)
        if verbose:
            try:
                import tiktoken  # type: ignore

                ver = getattr(tiktoken, "__version__", "unknown")
            except ModuleNotFoundError:
                ver = "unknown"
            print(f"Tokenizer: {tokenizer_name} (tiktoken {ver})")
            print(f"Token cache: {cache_path}")

    current_item: dict[str, Path | None] = {
        "path": None
    }  # Mutable container to track current file/dir

    def collect(item: Path, prefix: str, *, is_last: bool) -> None:
        current_item["path"] = item
        if item.is_dir():
            builder_local.add_directory(item, prefix, is_last=is_last)
        elif item.is_file():
            builder_local.add_file_to_tree(item, prefix, is_last=is_last)
            rel = item.relative_to(common)
            if is_text(item):
                content = read_text(item)
                ln, ch = len(content.splitlines()), len(content)
                tk = 0
                should_count = tokens and (
                    tokens_for == "all" or not any(rel.match(p) for p in excl_print)
                )
                if should_count:
                    tk = count_tokens(
                        content,
                        item,
                        tokenizer_fn,
                        token_cache,
                        force=force_tokens,
                        warn=lambda m: print(m),
                    )
                builder_local.record_metadata(rel, ln, ch, tk)
                if not any(rel.match(p) for p in excl_print):
                    builder_local.add_file(item, rel, ln, ch, tk, content)
            else:
                builder_local.record_metadata(rel, 0, item.stat().st_size, 0)

    config_tuple = ([p.resolve() for p in paths], excl_tree, common)
    traverse_dir(common, config_tuple, collect)

    if tokens:
        save_cache(token_cache, cache_path)

    tree_xml = "\n".join(builder_local.build_tree())
    files_xml = builder_local.build_file_contents()
    ttag = cfg.get("include_tree_tags")
    ftag = cfg.get("include_file_tags")
    llm_out = (
        f'<{ttag} name="{common.name}" path="{common}">\n{tree_xml}\n</{ttag}>\n'
        f'<{ftag} root="{common.name}">\n{files_xml}\n</{ftag}>'
    )
    clipboard.copy(llm_out)

    summary = builder_local.build_tree(include_metadata=True)
    human_summary(
        summary,
        builder_local.total_lines,
        builder_local.total_characters,
        total_tokens=builder_local.total_tokens if tokens else None,
        tokenizer=tokenizer_name if tokens else None,
        budget=budget,
    )
    return builder_local


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
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactively adjust ignore settings for this run",
    )
    parser.add_argument("--tokens", action="store_true", help="Enable token counting")
    parser.add_argument(
        "--tokenizer", default="o200k_base", help="Tokenizer name to use"
    )
    parser.add_argument(
        "--model", help="Model name to infer tokenizer and token budget"
    )
    parser.add_argument(
        "--tokens-for",
        choices=["printed", "all"],
        default="printed",
        help="Which files to count tokens for",
    )
    parser.add_argument(
        "--budget",
        type=int,
        help="Total token budget to display usage percentage",
    )
    parser.add_argument(
        "--force-tokens",
        action="store_true",
        help="Force tokenization of very large files",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--list-token-models",
        action="store_true",
        help="List available tiktoken models and exit",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Delete old files without prompting (migrate-config)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print new config to stdout (migrate-config)",
    )

    args = parser.parse_args()
    cwd = Path()

    command = None
    if args.paths and str(args.paths[0]) in {"migrate-config", "edit-config"}:
        command = str(args.paths.pop(0))

    if args.list_token_models:
        try:
            import tiktoken  # type: ignore

            names = sorted(tiktoken.list_encoding_names())
            from collections import defaultdict

            mapping: dict[str, list[str]] = defaultdict(list)
            for model, enc in tiktoken.model.MODEL_TO_ENCODING.items():
                mapping[enc].append(model)
        except ModuleNotFoundError:
            print("tiktoken is not installed", file=sys.stderr)
            sys.exit(1)
        for name in names:
            models = ", ".join(sorted(mapping.get(name, [])))
            if models:
                print(f"{name}: {models}")
            else:
                print(name)
        sys.exit(0)

    if command == "migrate-config":
        migrate_config(cwd, assume_yes=args.yes, to_stdout=args.stdout)
        sys.exit(0)
    if command == "edit-config":
        cfg = read_config(
            base_path=cwd,
            ignore_default=args.ignore_defaults,
            use_groblignore=args.use_groblignore,
        )
        interactive_edit_config([cwd], cfg, save=True)
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

    if args.interactive:
        interactive_edit_config(paths, cfg, save=False)

    for pat in args.add_ignore:
        cfg.setdefault("exclude_tree", [])
        if pat not in cfg["exclude_tree"]:
            cfg["exclude_tree"].append(pat)
    for pat in args.remove_ignore:
        if pat in cfg.get("exclude_tree", []):
            cfg["exclude_tree"].remove(pat)
    tokens_flag = args.tokens
    tokenizer_name = args.tokenizer
    budget = args.budget
    if args.model:
        try:
            import tiktoken  # type: ignore

            base, tier = (args.model.split(":", 1) + ["default"])[:2]
            enc = tiktoken.encoding_for_model(base)
            tokenizer_name = enc.name
            tokens_flag = True
            if budget is None:
                limits = MODEL_TOKEN_LIMITS.get(base, {})
                budget = limits.get(tier) or limits.get("default")
        except ModuleNotFoundError:
            print("tiktoken is not installed", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"Unknown model '{args.model}': {exc}", file=sys.stderr)
            sys.exit(1)

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
        process_paths(
            paths,
            cfg,
            clipboard,
            builder,
            tokens=tokens_flag,
            tokenizer_name=tokenizer_name,
            tokens_for=args.tokens_for,
            budget=budget,
            force_tokens=args.force_tokens,
            verbose=args.verbose,
        )
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
