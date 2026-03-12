"""CLI command implementation for the ``grobl explain`` workflow."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import click

from grobl.app.command_support import ScanParams
from grobl.app.config_loading import load_config, resolve_config_base
from grobl.app.explain import build_explain_entries, render_explain
from grobl.app.scan_runtime import (
    IgnoreCLIArgs,
    assemble_layered_ignores,
    ensure_paths_within_repo,
    gather_runtime_ignore_patterns,
    global_cli_options,
    resolve_runtime_paths,
    warn_legacy_ignore_flags,
)
from grobl.constants import (
    EXIT_CONFIG,
    ContentScope,
    PayloadFormat,
    SummaryFormat,
    TableStyle,
)
from grobl.errors import ConfigLoadError

from .options import add_ignore_options, add_paths_argument

if TYPE_CHECKING:
    from pathlib import Path

EXPLAIN_EPILOG = """\
Examples:
  grobl explain .
  grobl explain --format json src
  grobl explain --include-content 'docs/**' docs
  grobl explain README.md --format human
"""


@click.command(epilog=EXPLAIN_EPILOG)
@add_ignore_options
@click.option(
    "--format",
    "explain_format",
    type=click.Choice(["human", "markdown", "json"], case_sensitive=False),
    default="markdown",
    help="Explain output format",
)
@add_paths_argument
@click.pass_context
def explain(
    ctx: click.Context,
    *,
    exclude: tuple[str, ...],
    include: tuple[str, ...],
    exclude_file: tuple[Path, ...],
    include_file: tuple[Path, ...],
    exclude_tree: tuple[str, ...],
    include_tree: tuple[str, ...],
    exclude_content: tuple[str, ...],
    include_content: tuple[str, ...],
    add_ignore: tuple[str, ...],
    remove_ignore: tuple[str, ...],
    unignore: tuple[str, ...],
    ignore_file: tuple[Path, ...],
    explain_format: str,
    paths: tuple[Path, ...],
) -> None:
    global_options = global_cli_options(ctx)
    ignore_args = IgnoreCLIArgs.from_values(
        exclude=exclude,
        include=include,
        exclude_file=exclude_file,
        include_file=include_file,
        exclude_tree=exclude_tree,
        include_tree=include_tree,
        exclude_content=exclude_content,
        include_content=include_content,
        add_ignore=add_ignore,
        remove_ignore=remove_ignore,
        unignore=unignore,
        ignore_file=ignore_file,
    )
    warn_legacy_ignore_flags(ignore_args)

    requested_paths, repo_root = resolve_runtime_paths(paths)
    ensure_paths_within_repo(repo_root=repo_root, requested_paths=requested_paths, ctx=ctx)
    config_base = resolve_config_base(base_path=repo_root, explicit_config=global_options.config_path)

    (
        runtime_exclude,
        runtime_include,
        runtime_exclude_tree,
        runtime_include_tree,
        runtime_exclude_content,
        runtime_include_content,
    ) = gather_runtime_ignore_patterns(
        repo_root=repo_root,
        ignore_args=ignore_args,
    )

    try:
        load_config(
            base_path=config_base,
            explicit_config=global_options.config_path,
            ignore_defaults=False,
        )
    except ConfigLoadError as err:
        print(err, file=sys.stderr)
        raise SystemExit(EXIT_CONFIG) from err

    params = ScanParams(
        output=None,
        add_ignore=add_ignore,
        remove_ignore=remove_ignore,
        unignore=unignore,
        add_ignore_file=ignore_file,
        scope=ContentScope.ALL,
        summary_style=TableStyle.AUTO,
        config_path=global_options.config_path,
        payload=PayloadFormat.NONE,
        summary=SummaryFormat.NONE,
        payload_copy=False,
        payload_output=None,
        paths=requested_paths,
        repo_root=repo_root,
        pattern_base=config_base,
    )

    ignores = assemble_layered_ignores(
        repo_root=repo_root,
        scan_paths=requested_paths,
        params=params,
        global_options=global_options,
        runtime_exclude=runtime_exclude,
        runtime_include=runtime_include,
        runtime_exclude_tree=runtime_exclude_tree,
        runtime_include_tree=runtime_include_tree,
        runtime_exclude_content=runtime_exclude_content,
        runtime_include_content=runtime_include_content,
    )

    entries = build_explain_entries(paths=requested_paths, ignores=ignores)
    click.echo(render_explain(entries, explain_format=explain_format), nl=False)
