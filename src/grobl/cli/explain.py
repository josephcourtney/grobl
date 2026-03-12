"""CLI command implementation for the ``grobl explain`` workflow."""

from __future__ import annotations

import json
import operator
import sys
from typing import TYPE_CHECKING, Any

import click

from grobl.cli.common import ScanParams
from grobl.config import load_config, resolve_config_base
from grobl.constants import (
    EXIT_CONFIG,
    ContentScope,
    PayloadFormat,
    SummaryFormat,
    TableStyle,
)
from grobl.errors import ConfigLoadError
from grobl.provenance import exclusion_reason_to_dict, format_content_reason
from grobl.utils import detect_text

from .options import add_ignore_options, add_paths_argument
from .runtime import (
    IgnoreCLIArgs,
    assemble_layered_ignores,
    ensure_paths_within_repo,
    gather_runtime_ignore_patterns,
    global_cli_options,
    resolve_runtime_paths,
    warn_legacy_ignore_flags,
)

if TYPE_CHECKING:
    from pathlib import Path

    from grobl.ignore import LayeredIgnoreMatcher

EXPLAIN_EPILOG = """\
Examples:
  grobl explain .
  grobl explain --format json src
  grobl explain --include-content 'docs/**' docs
  grobl explain README.md --format human
"""


def _validate_expand_paths(paths: tuple[Path, ...]) -> list[Path]:
    validated: list[Path] = []
    for path in paths:
        try:
            path.lstat()
        except OSError as err:
            msg = f"path not found: {path}"
            raise click.UsageError(msg) from err
        validated.append(path.resolve(strict=False))
    return validated


def _build_reason(reason: dict[str, Any] | None) -> str:
    if reason is None:
        return "none"
    parts = [f"pattern={reason['pattern']}"]
    if reason.get("negated"):
        parts.append("negated")
    parts.extend((f"source={reason['source']}", f"base={reason['base_dir']}"))
    if reason.get("config_path"):
        parts.append(f"config={reason['config_path']}")
    if reason.get("detail"):
        parts.append(f"detail={reason['detail']}")
    return "; ".join(parts)


def _render_human(entries: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for entry in entries:
        lines.append(f"Path: {entry['path']}")
        tree = entry["tree"]
        lines.append(f"  tree: {'included' if tree['included'] else 'excluded'}")
        if tree.get("reason"):
            lines.append(f"    reason: {_build_reason(tree['reason'])}")
        content = entry["content"]
        lines.append(f"  content: {'included' if content['included'] else 'excluded'}")
        if content.get("reason"):
            lines.append(f"    reason: {_build_reason(content['reason'])}")
        if entry.get("text_detection"):
            details = entry["text_detection"]
            detail = details.get("detail") or "binary file"
            lines.append(f"  text detection: binary ({detail})")
    lines.append("")
    return "\n".join(lines)


def _render_json(entries: list[dict[str, Any]]) -> str:
    return json.dumps(entries, sort_keys=True, indent=2) + "\n"


def _explain_entry(abs_path: Path, ignores: LayeredIgnoreMatcher) -> dict[str, Any]:
    is_dir = abs_path.is_dir()
    tree_decision = ignores.explain_tree(abs_path, is_dir=is_dir)
    content_decision = ignores.explain_content(abs_path, is_dir=is_dir)

    tree_reason = exclusion_reason_to_dict(tree_decision.reason) if tree_decision.reason else None
    entry: dict[str, Any] = {
        "path": str(abs_path),
        "tree": {"included": not tree_decision.excluded, "reason": tree_reason},
    }

    content_included = not content_decision.excluded
    content_reason: dict[str, Any] | None = None
    text_detection: dict[str, Any] | None = None

    if content_decision.excluded and content_decision.reason is not None:
        content_reason = exclusion_reason_to_dict(content_decision.reason)
    elif abs_path.is_file() and not content_decision.excluded:
        detection = detect_text(abs_path)
        if not detection.is_text:
            content_included = False
            content_reason = format_content_reason(
                detection_detail=detection.detail,
                subject=abs_path,
            )
            detail = detection.detail or "binary file"
            text_detection = {"is_text": False, "detail": detail}

    entry["content"] = {"included": content_included, "reason": content_reason}
    if text_detection is not None:
        entry["text_detection"] = text_detection

    return entry


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
def explain(  # noqa: PLR0914
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

    validated_paths = _validate_expand_paths(requested_paths)
    entries = sorted(
        (_explain_entry(path, ignores) for path in validated_paths),
        key=operator.itemgetter("path"),
    )

    normalized_format = explain_format.lower()
    if normalized_format == "human":
        normalized_format = "markdown"

    click.echo(
        _render_json(entries) if normalized_format == "json" else _render_human(entries),
        nl=False,
    )
