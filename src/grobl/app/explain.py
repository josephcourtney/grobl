"""Application logic for explain output."""

from __future__ import annotations

import json
import operator
from typing import TYPE_CHECKING, Any

import click

from grobl.constants import InclusionLevel
from grobl.directory import (
    TraverseConfig,
    inspect_symlink,
    should_follow_symlink,
    symlink_target_is_selected,
)
from grobl.provenance import format_content_reason, inclusion_reason_to_dict
from grobl.resource_limits import UNLIMITED_RESOURCE_LIMITS, ResourceBudget, ResourceLimits
from grobl.token_counting import count_tokens
from grobl.utils import detect_text, logical_absolute, read_text

if TYPE_CHECKING:
    from pathlib import Path

    from grobl.directory import SymlinkInfo
    from grobl.ignore import LayeredIgnoreMatcher


def validate_existing_paths(paths: tuple[Path, ...]) -> list[Path]:
    """Validate explain targets without dereferencing symlinks."""
    validated: list[Path] = []
    for path in paths:
        logical = logical_absolute(path)
        try:
            logical.lstat()
        except OSError as err:
            msg = f"path not found: {path}"
            raise click.UsageError(msg) from err
        validated.append(logical)
    return validated


def build_explain_entries(
    *,
    paths: tuple[Path, ...],
    ignores: LayeredIgnoreMatcher,
    limits: ResourceLimits = UNLIMITED_RESOURCE_LIMITS,
    repo_root: Path | None = None,
    follow_symlinks: bool = False,
    allow_external_symlinks: bool = False,
) -> list[dict[str, Any]]:
    """Return sorted explain entries for the given targets."""
    validated_paths = sorted(
        validate_existing_paths(paths),
        key=lambda path: tuple(part.casefold() for part in path.parts),
    )
    if not validated_paths:
        return []
    root = logical_absolute(repo_root or validated_paths[0].parent)
    traversal = TraverseConfig(
        paths=validated_paths,
        base=root,
        repo_root=root,
        follow_symlinks=follow_symlinks,
        allow_external_symlinks=allow_external_symlinks,
    )
    budget = ResourceBudget(limits)
    return sorted(
        (_explain_entry(path, ignores, budget, traversal) for path in validated_paths),
        key=operator.itemgetter("path"),
    )


def render_explain(entries: list[dict[str, Any]], *, explain_format: str) -> str:
    """Render explain entries in the requested format."""
    normalized_format = explain_format.lower()
    if normalized_format == "human":
        normalized_format = "markdown"
    return _render_json(entries) if normalized_format == "json" else _render_human(entries)


def _build_reason(reason: dict[str, Any] | None) -> str:
    if reason is None:
        return "none"
    parts = [f"pattern={reason['pattern']}", f"state={reason['state']}"]
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
        lines.extend((f"Path: {entry['path']}", f"  state: {entry['state']}"))
        if entry.get("reason"):
            lines.append(f"    reason: {_build_reason(entry['reason'])}")
        symlink = entry.get("symlink")
        if isinstance(symlink, dict):
            lines.append(f"  symlink: {symlink['target']}")
            if symlink.get("resolved_target"):
                lines.append(f"    resolved: {symlink['resolved_target']}")
            lines.extend((f"    target scope: {symlink['target_scope']}", f"    disposition: {symlink['disposition']}"))
        tree = entry["tree"]
        lines.append(f"  tree: {'included' if tree['included'] else 'excluded'}")
        content = entry["content"]
        lines.append(f"  content: {'included' if content['included'] else 'excluded'}")
        if content.get("reason") and content.get("reason") != entry.get("reason"):
            lines.append(f"    reason: {_build_reason(content['reason'])}")
        if entry.get("text_detection"):
            details = entry["text_detection"]
            detail = details.get("detail") or "binary file"
            lines.append(f"  text detection: binary ({detail})")
        limits = entry.get("resource_limits")
        if limits:
            lines.append(
                "  resource limits: "
                f"file-bytes={limits['max_file_bytes'] or 'unlimited'}; "
                f"total-bytes={limits['max_total_bytes'] or 'unlimited'}; "
                f"tokens={limits['max_tokens'] or 'unlimited'}"
            )
    lines.append("")
    return "\n".join(lines)


def _render_json(entries: list[dict[str, Any]]) -> str:
    return json.dumps(entries, sort_keys=True, indent=2) + "\n"


def _apply_full_file_limits(
    abs_path: Path,
    *,
    file_bytes: int | None,
    budget: ResourceBudget,
) -> tuple[bool, dict[str, Any] | None]:
    limits = budget.limits
    tokens = 0
    actual_bytes = file_bytes
    if limits.max_tokens is not None or actual_bytes is None:
        try:
            content = read_text(abs_path)
        except OSError as err:
            return False, format_content_reason(
                detection_detail=f"read error: {err}",
                subject=abs_path,
            )
        tokens = count_tokens(content) if limits.max_tokens is not None else 0
        actual_bytes = file_bytes if file_bytes is not None else len(content.encode("utf-8"))

    if actual_bytes is None:
        return True, None

    budget_reason = budget.accept(
        abs_path,
        file_bytes=actual_bytes,
        tokens=tokens,
    )
    return budget_reason is None, budget_reason


def _evaluate_full_file(
    abs_path: Path,
    budget: ResourceBudget,
) -> tuple[bool, dict[str, Any] | None, dict[str, Any] | None]:
    try:
        file_bytes = abs_path.stat().st_size
    except OSError:
        file_bytes = None

    if file_bytes is not None:
        budget_reason = budget.preflight(abs_path, file_bytes=file_bytes)
        if budget_reason is not None:
            return False, budget_reason, None

    detection = detect_text(abs_path)
    if not detection.is_text:
        detail = detection.detail or "binary file"
        return (
            False,
            format_content_reason(detection_detail=detection.detail, subject=abs_path),
            {"is_text": False, "detail": detail},
        )

    content_included, content_reason = _apply_full_file_limits(
        abs_path,
        file_bytes=file_bytes,
        budget=budget,
    )
    return content_included, content_reason, None


def _symlink_disposition(
    info: SymlinkInfo,
    traversal: TraverseConfig,
    *,
    level: InclusionLevel,
    may_reinclude_descendant: bool,
) -> str:
    if info.broken:
        return "broken target; not followed"
    if not traversal.follow_symlinks:
        return "not followed; symlink following is disabled"
    if info.external and not traversal.allow_external_symlinks:
        return "not followed; target is outside the repository root"
    if symlink_target_is_selected(info, traversal.paths):
        return "not followed; target is already selected through its real path"
    if level is InclusionLevel.OMIT:
        if info.target_is_dir and may_reinclude_descendant:
            return "followed to evaluate re-included descendants"
        return "not followed; path is omitted"
    if info.target_is_file and level is InclusionLevel.TREE_ONLY:
        return "not followed; content state is tree_only"
    if not info.target_is_dir and not info.target_is_file:
        return "not followed; unsupported target type"
    return "followed"


def _explain_entry(
    abs_path: Path,
    ignores: LayeredIgnoreMatcher,
    budget: ResourceBudget,
    traversal: TraverseConfig,
) -> dict[str, Any]:
    limits = budget.limits
    symlink_info = inspect_symlink(abs_path, root=traversal.repo_root) if abs_path.is_symlink() else None
    is_dir = symlink_info.target_is_dir if symlink_info is not None else abs_path.is_dir()
    decision = ignores.explain_inclusion(abs_path, is_dir=is_dir)
    reason = inclusion_reason_to_dict(decision.reason) if decision.reason is not None else None

    entry: dict[str, Any] = {
        "path": str(abs_path),
        "state": decision.level.value,
        "reason": reason,
        "resource_limits": limits.to_dict(),
        "tree": {
            "included": decision.level is not InclusionLevel.OMIT,
            "reason": reason if decision.level is InclusionLevel.OMIT else None,
        },
    }

    if symlink_info is not None:
        entry["symlink"] = {
            "target": symlink_info.target,
            "resolved_target": (
                str(symlink_info.resolved_target) if symlink_info.resolved_target is not None else None
            ),
            "target_scope": symlink_info.scope,
            "broken": symlink_info.broken,
            "disposition": _symlink_disposition(
                symlink_info,
                traversal,
                level=decision.level,
                may_reinclude_descendant=(
                    symlink_info.target_is_dir and ignores.may_reinclude_descendant(abs_path)
                ),
            ),
        }

    content_included = decision.level is InclusionLevel.FULL and symlink_info is None
    content_reason: dict[str, Any] | None = reason if decision.level is InclusionLevel.TREE_ONLY else None
    text_detection: dict[str, Any] | None = None

    if symlink_info is not None:
        should_evaluate_file = symlink_info.target_is_file and should_follow_symlink(
            symlink_info,
            traversal,
        )
    else:
        should_evaluate_file = abs_path.is_file()
    should_evaluate_file = should_evaluate_file and decision.level is InclusionLevel.FULL
    if should_evaluate_file:
        content_included, content_reason, text_detection = _evaluate_full_file(abs_path, budget)

    entry["content"] = {"included": content_included, "reason": content_reason}
    if text_detection is not None:
        entry["text_detection"] = text_detection

    return entry
