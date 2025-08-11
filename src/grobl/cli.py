"""Command line interface for grobl."""

from __future__ import annotations

import argparse
import logging
import sys

from collections.abc import Callable
from pathlib import Path
from typing import Any
import importlib.resources
import tomllib

from grobl import __version__
from grobl.clipboard import ClipboardInterface, PyperclipClipboard, StdoutClipboard
from grobl.config import TOML_CONFIG, migrate_config, read_config, write_default_config
from grobl.directory import DirectoryTreeBuilder, traverse_dir
from grobl.editor import interactive_edit_config
from grobl.errors import ConfigLoadError
from grobl.formatter import human_summary
from grobl.tokens import (
    TokenizerNotAvailableError,
    count_tokens,
    load_cache,
    load_tokenizer,
    save_cache,
)
from grobl.utils import find_common_ancestor, find_project_root, is_text, read_text


def _load_model_specs() -> dict[str, dict]:
    """Load bundled model specifications and aliases from resources."""

    cfg_path = importlib.resources.files("grobl.resources").joinpath("models.toml")
    data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    models = data.get("models", {})
    aliases = data.get("aliases", {})
    for alias, target in aliases.items():
        if target in models:
            models[alias] = models[target]
    return models


MODEL_SPECS: dict[str, dict] = _load_model_specs()


def process_paths(
    paths: list[Path],
    cfg: dict[str, Any],
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
    """Traverse ``paths`` and emit formatted output."""

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

    def collect(item: Path, prefix: str, is_last: bool) -> None:
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


SUBCOMMANDS = {"scan", "init", "config", "models", "migrate", "version"}


def main(argv: list[str] | None = None) -> None:
    """CLI entry point with subcommands."""

    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["scan"]
    elif argv[0] not in SUBCOMMANDS and argv[0] not in {
        "-h",
        "--help",
        "-V",
        "--version",
    }:
        idx = 0
        while idx < len(argv):
            arg = argv[idx]
            if arg.startswith("-v"):
                idx += 1
                continue
            if arg == "--log-level":
                idx += 2
                continue
            if arg.startswith("--log-level="):
                idx += 1
                continue
            break
        argv.insert(idx, "scan")

    parser = argparse.ArgumentParser(
        prog="grobl",
        description="Directory-to-Markdown utility with TOML config support",
    )
    parser.add_argument("-V", "--version", action="version", version=__version__)
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (use -vv for debug)",
    )
    parser.add_argument(
        "--log-level",
        type=str.upper,
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Set log level explicitly",
    )

    subparsers = parser.add_subparsers(dest="command")

    scan = subparsers.add_parser("scan", help="Scan directories")
    scan.add_argument(
        "--ignore-defaults",
        "-I",
        action="store_true",
        help="Ignore bundled default exclude patterns",
    )
    scan.add_argument("paths", nargs="*", type=Path, help="Directories to scan")
    scan.add_argument(
        "--no-clipboard",
        action="store_true",
        help="Print output to stdout instead of copying to clipboard",
    )
    scan.add_argument("--output", type=Path, help="Write output to a file")
    scan.add_argument(
        "--add-ignore",
        action="append",
        default=[],
        help="Additional ignore pattern for this run",
    )
    scan.add_argument(
        "--remove-ignore",
        action="append",
        default=[],
        help="Ignore pattern to remove for this run",
    )
    scan.add_argument(
        "--interactive",
        action="store_true",
        help="Interactively adjust ignore settings for this run",
    )
    scan.add_argument("--tokens", action="store_true", help="Enable token counting")
    scan.add_argument("--tokenizer", default="o200k_base", help="Tokenizer name to use")
    scan.add_argument("--model", help="Model name to infer tokenizer and token budget")
    scan.add_argument(
        "--tokens-for",
        choices=["printed", "all"],
        default="printed",
        help="Which files to count tokens for",
    )
    scan.add_argument(
        "--budget",
        type=int,
        help="Total token budget to display usage percentage",
    )
    scan.add_argument(
        "--force-tokens",
        action="store_true",
        help="Force tokenization of very large files",
    )

    init_p = subparsers.add_parser("init", help="Write default config to project")
    init_p.add_argument("--yes", action="store_true", help="Overwrite without prompt")

    subparsers.add_parser("models", help="List available tiktoken models")

    migrate_p = subparsers.add_parser("migrate", help="Migrate legacy configuration")
    migrate_p.add_argument(
        "--yes", action="store_true", help="Delete old files without prompting"
    )
    migrate_p.add_argument(
        "--stdout", action="store_true", help="Print new config to stdout"
    )

    subparsers.add_parser("version", help="Print version and exit")
    subparsers.add_parser("config", help="Configuration management")

    args = parser.parse_args(argv)
    level: int
    if args.log_level:
        level = getattr(logging, args.log_level.upper())
    elif args.verbose >= 2:
        level = logging.DEBUG
    elif args.verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(level=level, force=True)

    cwd = Path()

    if args.command == "version":
        print(__version__)
        sys.exit(0)

    if args.command == "models":
        try:
            import tiktoken  # type: ignore

            names = sorted(tiktoken.list_encoding_names())
            from collections import defaultdict

            mapping: dict[str, list[str]] = defaultdict(list)
            for model, enc in tiktoken.model.MODEL_TO_ENCODING.items():  # type: ignore[attr-defined]
                mapping[enc].append(model)
        except ModuleNotFoundError:
            print("tiktoken is not installed", file=sys.stderr)
            sys.exit(1)
        for name in names:
            if models := ", ".join(sorted(mapping.get(name, []))):
                print(f"{name}: {models}")
            else:
                print(name)
        sys.exit(0)

    if args.command == "migrate":
        migrate_config(cwd, assume_yes=args.yes, to_stdout=args.stdout)
        sys.exit(0)

    if args.command == "init":
        target = find_project_root(cwd) or cwd
        if target != cwd and not args.yes:
            resp = input(f"Write {TOML_CONFIG} to {target}? (y/N): ").strip().lower()
            if resp != "y":
                target = cwd
        write_default_config(target)
        print(f"Wrote {TOML_CONFIG} to {target}")
        sys.exit(0)

    # Default scan behavior
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
        cfg = read_config(base_path=cwd, ignore_default=args.ignore_defaults)
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
    no_clipboard = args.no_clipboard or cfg.get("no_clipboard", False)
    tokens_flag = args.tokens or cfg.get("tokens", False)
    model_arg = args.model or cfg.get("model")
    budget = args.budget if args.budget is not None else cfg.get("budget")
    force_tokens = args.force_tokens or cfg.get("force_tokens", False)
    verbose_flag = args.verbose > 0 or cfg.get("verbose", False)
    tokenizer_name = args.tokenizer
    if model_arg:
        base, tier = (model_arg.split(":", 1) + ["default"])[:2]
        spec = MODEL_SPECS.get(base)
        if spec is None:
            print(f"Unknown model '{model_arg}'", file=sys.stderr)
            raise SystemExit(1)
        tokenizer_name = spec.get("tokenizer", tokenizer_name)
        tokens_flag = True
        if budget is None:
            limits = spec.get("budget")
            if isinstance(limits, int):
                budget = limits
            elif isinstance(limits, dict):
                budget = limits.get(tier) or limits.get("default")

    clipboard: ClipboardInterface
    if args.output:
        clipboard = StdoutClipboard(args.output)
    elif no_clipboard:
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
            force_tokens=force_tokens,
            verbose=verbose_flag,
        )
    except KeyboardInterrupt:
        print_interrupt_diagnostics(cwd, cfg, builder)


def print_interrupt_diagnostics(
    cwd: Path, cfg: dict[str, object], builder: DirectoryTreeBuilder
) -> None:
    """Print diagnostics when the user interrupts execution."""

    print("\nInterrupted by user. Dumping debug info:")
    print(f"cwd: {cwd}")
    print(f"exclude_tree: {cfg.get('exclude_tree')}")
    print(f"exclude_print: {cfg.get('exclude_print')}")

    print("DirectoryTreeBuilder(")
    print(f"    base_path         = {builder.base_path}")
    print(f"    total_lines       = {builder.total_lines}")
    print(f"    total_characters  = {builder.total_characters}")
    print(f"    exclude_patterns  = {builder.exclude_patterns}")
    print(f"    tree_output       = {builder.tree_output}")
    print(f"    all_metadata      = {builder.all_metadata}")
    print(f"    included_metadata = {builder.included_metadata}")
    print(f"    file_contents     = {builder.file_contents}")
    print(f"    file_tree_entries = {builder.file_tree_entries}")
    print(")")

    raise


if __name__ == "__main__":
    main()
