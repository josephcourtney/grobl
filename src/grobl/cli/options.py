"""Reusable Click option builders for CLI subcommands."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from grobl.constants import ContentScope

CommandDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]

_IGNORE_OPTION_DECORATORS: tuple[CommandDecorator, ...] = (
    click.option("--exclude", multiple=True, help="Add a tree+content exclude pattern"),
    click.option("--include", multiple=True, help="Add a tree+content include (negated) pattern"),
    click.option(
        "--exclude-file",
        "exclude_file",
        multiple=True,
        type=click.Path(path_type=Path, exists=False),
        help="Exclude a specific file path (tree + content)",
    ),
    click.option(
        "--include-file",
        "include_file",
        multiple=True,
        type=click.Path(path_type=Path, exists=False),
        help="Include a specific file path (tree + content; negated internally)",
    ),
    click.option("--exclude-tree", multiple=True, help="Add a tree-only exclude pattern"),
    click.option("--include-tree", multiple=True, help="Add a tree-only include (negated) pattern"),
    click.option(
        "--exclude-content",
        multiple=True,
        help="Add a content-only exclude pattern (controls text capture)",
    ),
    click.option(
        "--include-content",
        multiple=True,
        help="Add a content-only include (negated) pattern",
    ),
    click.option("--add-ignore", multiple=True, help="Additional ignore pattern for this run"),
    click.option(
        "--remove-ignore",
        multiple=True,
        help="Unignore an ignore pattern for this run (runtime layer; last match wins)",
    ),
    click.option("--unignore", multiple=True, help="Ignore exception pattern for this run"),
    click.option(
        "--ignore-file",
        multiple=True,
        type=click.Path(path_type=Path),
        help="Read ignore patterns from file (one per line)",
    ),
)

_PATHS_ARGUMENT: CommandDecorator = click.argument(
    "paths",
    nargs=-1,
    type=click.Path(path_type=Path),
)


def _apply_decorators(
    func: Callable[..., Any],
    decorators: tuple[CommandDecorator, ...],
) -> Callable[..., Any]:
    wrapped: Callable[..., Any] = func
    for decorator in reversed(decorators):
        wrapped = decorator(wrapped)
    return wrapped


def add_ignore_options(func: Callable[..., Any]) -> Callable[..., Any]:
    """Attach the shared ignore/runtime options to a subcommand."""
    return _apply_decorators(func, _IGNORE_OPTION_DECORATORS)


def add_scope_option(func: Callable[..., Any]) -> Callable[..., Any]:
    """Attach the shared scan scope option."""
    decorators: tuple[CommandDecorator, ...] = (
        click.option(
            "--scope",
            type=click.Choice([scope.value for scope in ContentScope], case_sensitive=False),
            default=ContentScope.ALL.value,
            help="Content scope for payload generation",
        ),
    )
    return _apply_decorators(func, decorators)


def add_paths_argument(func: Callable[..., Any]) -> Callable[..., Any]:
    """Attach the shared paths argument."""
    return _PATHS_ARGUMENT(func)
