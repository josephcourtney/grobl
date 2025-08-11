"""Command line interface for grobl."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
import importlib.resources
import tomllib
import click

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
    mode: str = "all",
    table: str = "full",
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

    current_item: dict[str, Path | None] = {"path": None}

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

    llm_parts: list[str] = []
    ttag = cfg.get("include_tree_tags")
    ftag = cfg.get("include_file_tags")
    tree_xml = "\n".join(builder_local.build_tree())
    files_xml = builder_local.build_file_contents()
    if mode in {"all", "tree"}:
        llm_parts.append(
            f'<{ttag} name="{common.name}" path="{common}">\n{tree_xml}\n</{ttag}>'
        )
    if mode in {"all", "files"}:
        llm_parts.append(f'<{ftag} root="{common.name}">\n{files_xml}\n</{ftag}>')
    clipboard.copy("\n".join(llm_parts))

    if mode in {"all", "summary"}:
        summary = builder_local.build_tree(include_metadata=True)
        human_summary(
            summary,
            builder_local.total_lines,
            builder_local.total_characters,
            total_tokens=builder_local.total_tokens if tokens else None,
            tokenizer=tokenizer_name if tokens else None,
            budget=budget,
            table=table,
        )
    return builder_local


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-v", "--verbose", count=True, help="Increase verbosity (use -vv for debug)"
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], case_sensitive=False
    ),
    help="Set log level explicitly",
)
@click.version_option(__version__, "-V", "--version")
@click.pass_context
def cli(ctx: click.Context, verbose: int, log_level: str | None) -> None:
    """Directory-to-Markdown utility with TOML config support."""

    level: int
    if log_level:
        level = getattr(logging, log_level.upper())
    elif verbose >= 2:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(level=level, force=True)


@cli.command()
@click.option(
    "--ignore-defaults",
    "-I",
    is_flag=True,
    help="Ignore bundled default exclude patterns",
)
@click.option(
    "--no-clipboard",
    is_flag=True,
    help="Print output to stdout instead of copying to clipboard",
)
@click.option(
    "--output", type=click.Path(path_type=Path), help="Write output to a file"
)
@click.option(
    "--add-ignore", multiple=True, help="Additional ignore pattern for this run"
)
@click.option(
    "--remove-ignore", multiple=True, help="Ignore pattern to remove for this run"
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactively adjust ignore settings for this run",
)
@click.option("--tokens", is_flag=True, help="Enable token counting")
@click.option("--tokenizer", default="o200k_base", help="Tokenizer name to use")
@click.option("--model", help="Model name to infer tokenizer and token budget")
@click.option(
    "--tokens-for",
    type=click.Choice(["printed", "all"]),
    default="printed",
    help="Which files to count tokens for",
)
@click.option(
    "--budget", type=int, help="Total token budget to display usage percentage"
)
@click.option(
    "--force-tokens", is_flag=True, help="Force tokenization of very large files"
)
@click.option(
    "--mode",
    type=click.Choice(["all", "tree", "summary", "files"]),
    default="all",
    help="Output mode",
)
@click.option(
    "--table",
    type=click.Choice(["full", "compact", "none"]),
    default="full",
    help="Summary table style",
)
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def scan(
    *,
    ignore_defaults: bool,
    no_clipboard: bool,
    output: Path | None,
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
    interactive: bool,
    tokens: bool,
    tokenizer: str,
    model: str | None,
    tokens_for: str,
    budget: int | None,
    force_tokens: bool,
    mode: str,
    table: str,
    paths: tuple[Path, ...],
) -> None:
    cwd = Path()
    paths = paths or (cwd,)
    if ignore_defaults:
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
                        raise SystemExit(1)
                    break
            else:
                continue
            break

    try:
        cfg = read_config(base_path=cwd, ignore_default=ignore_defaults)
    except ConfigLoadError as err:
        print(err, file=sys.stderr)
        raise SystemExit(1)

    if interactive:
        interactive_edit_config(list(paths), cfg, save=False)

    for pat in add_ignore:
        cfg.setdefault("exclude_tree", [])
        if pat not in cfg["exclude_tree"]:
            cfg["exclude_tree"].append(pat)
    for pat in remove_ignore:
        if pat in cfg.get("exclude_tree", []):
            cfg["exclude_tree"].remove(pat)

    no_clip = no_clipboard or cfg.get("no_clipboard", False)
    tokens_flag = tokens or cfg.get("tokens", False)
    model_arg = model or cfg.get("model")
    budget_val = budget if budget is not None else cfg.get("budget")
    force_tokens_flag = force_tokens or cfg.get("force_tokens", False)
    verbose_flag = cfg.get("verbose", False)
    tokenizer_name = tokenizer
    if model_arg:
        base, tier = (model_arg.split(":", 1) + ["default"])[:2]
        spec = MODEL_SPECS.get(base)
        if spec is None:
            print(f"Unknown model '{model_arg}'", file=sys.stderr)
            raise SystemExit(1)
        tokenizer_name = spec.get("tokenizer", tokenizer_name)
        tokens_flag = True
        if budget_val is None:
            limits = spec.get("budget")
            if isinstance(limits, int):
                budget_val = limits
            elif isinstance(limits, dict):
                budget_val = limits.get(tier) or limits.get("default")

    clipboard: ClipboardInterface
    if output:
        clipboard = StdoutClipboard(output)
    elif no_clip:
        clipboard = StdoutClipboard()
    else:
        clipboard = PyperclipClipboard(fallback=StdoutClipboard())

    builder = DirectoryTreeBuilder(
        base_path=cwd, exclude_patterns=cfg.get("exclude_tree", [])
    )

    try:
        process_paths(
            list(paths),
            cfg,
            clipboard,
            builder,
            tokens=tokens_flag,
            tokenizer_name=tokenizer_name,
            tokens_for=tokens_for,
            budget=budget_val,
            force_tokens=force_tokens_flag,
            verbose=verbose_flag,
            mode=mode,
            table=table,
        )
    except KeyboardInterrupt:
        print_interrupt_diagnostics(cwd, cfg, builder)


@cli.command()
@click.option("--yes", is_flag=True, help="Overwrite without prompt")
def init(yes: bool) -> None:
    """Write default config to project."""

    cwd = Path()
    target = find_project_root(cwd) or cwd
    if target != cwd and not yes:
        resp = input(f"Write {TOML_CONFIG} to {target}? (y/N): ").strip().lower()
        if resp != "y":
            target = cwd
    write_default_config(target)
    print(f"Wrote {TOML_CONFIG} to {target}")


@cli.command()
def models() -> None:  # noqa: D401 - help from decorator
    """List available tiktoken models."""

    try:
        import tiktoken  # type: ignore

        names = sorted(tiktoken.list_encoding_names())
        from collections import defaultdict

        mapping: dict[str, list[str]] = defaultdict(list)
        for model, enc in tiktoken.model.MODEL_TO_ENCODING.items():  # type: ignore[attr-defined]
            mapping[enc].append(model)
    except ModuleNotFoundError:
        print("tiktoken is not installed", file=sys.stderr)
        raise SystemExit(1)
    for name in names:
        if models := ", ".join(sorted(mapping.get(name, []))):
            print(f"{name}: {models}")
        else:
            print(name)


@cli.command()
@click.option("--yes", is_flag=True, help="Delete old files without prompting")
@click.option("--stdout", is_flag=True, help="Print new config to stdout")
def migrate(yes: bool, stdout: bool) -> None:
    """Migrate legacy configuration."""

    cwd = Path()
    migrate_config(cwd, assume_yes=yes, to_stdout=stdout)


@cli.command()
def version() -> None:
    """Print version and exit."""

    print(__version__)


@cli.command()
def config() -> None:  # noqa: D401 - placeholder
    """Configuration management (placeholder)."""

    pass


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


SUBCOMMANDS = {"scan", "init", "config", "models", "migrate", "version"}


def main(argv: list[str] | None = None) -> None:
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
    cli.main(args=argv, prog_name="grobl", standalone_mode=False)


if __name__ == "__main__":
    main()
