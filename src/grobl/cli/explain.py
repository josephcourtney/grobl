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
    resolve_runtime_paths,
)
from grobl.constants import (
    EXIT_CONFIG,
    ContentScope,
    PayloadFormat,
    SummaryFormat,
    TableStyle,
)
from grobl.errors import ConfigLoadError

from .help_format import LiteralEpilogCommand
from .options import add_config_option, add_ignore_options, add_ignore_policy_options, add_paths_argument

if TYPE_CHECKING:
    from pathlib import Path

EXPLAIN_EPILOG = """\
Examples:
  grobl explain .
    Show tree and content decisions for the current directory.

  grobl explain README.md --format human
    Inspect one path in a human-readable form.

  grobl explain --format json src
    Emit machine-readable diagnostics for scripting.

  grobl explain --include-content 'docs/**' docs
    Verify an override before running a full scan.
"""


@click.command(cls=LiteralEpilogCommand, epilog=EXPLAIN_EPILOG)
@add_config_option
@add_ignore_policy_options
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
    config_path: Path | None,
    ignore_defaults: bool,
    no_ignore_config: bool,
    no_ignore: bool,
    ignore_policy: str,
    explain_format: str,
    paths: tuple[Path, ...],
) -> None:
    """Explain why paths are included or excluded for tree and content output."""
    ignore_args = IgnoreCLIArgs.from_values(
        exclude=exclude,
        include=include,
        exclude_file=exclude_file,
        include_file=include_file,
        exclude_tree=exclude_tree,
        include_tree=include_tree,
        exclude_content=exclude_content,
        include_content=include_content,
    )

    requested_paths, repo_root = resolve_runtime_paths(paths)
    ensure_paths_within_repo(repo_root=repo_root, requested_paths=requested_paths, ctx=ctx)
    config_base = resolve_config_base(base_path=repo_root, explicit_config=config_path)

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
            explicit_config=config_path,
            ignore_defaults=False,
        )
    except ConfigLoadError as err:
        print(err, file=sys.stderr)
        raise SystemExit(EXIT_CONFIG) from err

    params = ScanParams(
        scope=ContentScope.ALL,
        summary_style=TableStyle.AUTO,
        config_path=config_path,
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
        ignore_policy=ignore_policy,
        ignore_defaults_flag=ignore_defaults,
        no_ignore_config_flag=no_ignore_config,
        no_ignore_flag=no_ignore,
        runtime_exclude=runtime_exclude,
        runtime_include=runtime_include,
        runtime_exclude_tree=runtime_exclude_tree,
        runtime_include_tree=runtime_include_tree,
        runtime_exclude_content=runtime_exclude_content,
        runtime_include_content=runtime_include_content,
    )

    entries = build_explain_entries(paths=requested_paths, ignores=ignores)
    click.echo(render_explain(entries, explain_format=explain_format), nl=False)
