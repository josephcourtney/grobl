"""Root CLI argument normalization and context storage."""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import click

from grobl.constants import IgnorePolicy

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from collections.abc import Set as AbstractSet

DEFAULT_COMMAND = "scan"
VERBOSE_DEBUG_THRESHOLD = 2

_HELP_FLAGS = {"-h", "--help"}
_VERSION_FLAGS = {"-V", "--version"}
_VERBOSE_FLAGS = {"--verbose"}


@dataclass(frozen=True, slots=True)
class RootContextOptions:
    config_path: Path | None
    payload_format: str
    copy: bool
    output: Path | None
    summary: str
    summary_style: str | None
    summary_to: str
    summary_output: Path | None
    ignore_policy: str
    ignore_defaults_flag: bool
    no_ignore_config_flag: bool
    no_ignore_flag: bool


def store_root_context(
    *,
    ctx: click.Context | None,
    config_path: Path | None,
    payload_format: str,
    copy: bool,
    output: Path | None,
    summary: str,
    summary_style: str | None,
    summary_to: str,
    summary_output: Path | None,
    ignore_defaults: bool,
    no_ignore_config: bool,
    no_ignore: bool,
    ignore_policy: str,
) -> None:
    """Persist resolved root options for subcommands."""
    if ctx is None:
        return
    final_ignore_policy = _effective_ignore_policy(
        ignore_policy=ignore_policy,
        ignore_defaults=ignore_defaults,
        no_ignore_config=no_ignore_config,
        no_ignore=no_ignore,
    )
    ctx.obj = ctx.obj or {}
    ctx.obj.update(
        asdict(
            RootContextOptions(
                config_path=config_path,
                payload_format=payload_format,
                copy=copy,
                output=output,
                summary=summary,
                summary_style=summary_style,
                summary_to=summary_to,
                summary_output=summary_output,
                ignore_policy=final_ignore_policy,
                ignore_defaults_flag=ignore_defaults,
                no_ignore_config_flag=no_ignore_config,
                no_ignore_flag=no_ignore,
            )
        )
    )


def resolve_log_level(*, verbose: int, log_level: str | None) -> int:
    """Resolve the effective log level from root flags."""
    if log_level:
        return getattr(logging, log_level.upper())
    if verbose >= VERBOSE_DEBUG_THRESHOLD:
        return logging.DEBUG
    if verbose == 1:
        return logging.INFO
    return logging.WARNING


def build_command_option_map(commands: Mapping[str, click.Command]) -> dict[str, set[str]]:
    """Return the long option names declared by each subcommand."""
    option_map: dict[str, set[str]] = {}
    for name, command in commands.items():
        option_map[name] = {
            opt_name
            for param in command.params
            if isinstance(param, click.Option)
            for opt_name in param.opts
            if opt_name.startswith("--")
        }
    return option_map


def normalize_argv(
    args: list[str],
    *,
    command_options: Mapping[str, AbstractSet[str]] | None,
) -> list[str]:
    """Normalize root argv so global flags remain global regardless of position."""
    if command_options is None:
        return args
    command_names = set(command_options)
    if not command_names:
        return args

    pre, post, has_ddash = _split_on_ddash(args)
    tail = (["--"] if has_ddash else []) + post
    if any(token in _VERSION_FLAGS for token in pre):
        return args

    normalized_pre = _route_help_flags(pre, command_names)
    return _reorder_root_options(normalized_pre, command_options=command_options, tail=tail)


def inject_default_scan(
    args: list[str],
    *,
    command_names: Iterable[str] | None = None,
) -> list[str]:
    """Insert ``scan`` when the first non-global token looks like a scan target."""
    normalized = list(args)
    if command_names is None:
        return normalized

    known_commands = set(command_names)
    if not known_commands:
        return normalized

    pre = normalized[: normalized.index("--")] if "--" in normalized else normalized
    if any(token in known_commands for token in pre):
        return normalized

    idx = _first_non_global_index(normalized)
    if idx is None:
        normalized.append(DEFAULT_COMMAND)
        return normalized

    token = normalized[idx]
    if token in known_commands:
        return normalized
    if _should_inject_for_token(token):
        normalized.insert(idx, DEFAULT_COMMAND)
        return normalized

    msg = (
        f"Unknown command: {token}\n"
        "See `grobl --help`.\n"
        "If you meant to scan a path, ensure it exists or run `grobl scan <path>`."
    )
    raise click.UsageError(msg)


def _effective_ignore_policy(
    *,
    ignore_policy: str,
    ignore_defaults: bool,
    no_ignore_config: bool,
    no_ignore: bool,
) -> str:
    if ignore_policy != IgnorePolicy.AUTO.value:
        return ignore_policy
    if no_ignore:
        return IgnorePolicy.NONE.value
    if no_ignore_config:
        return IgnorePolicy.DEFAULTS.value
    if ignore_defaults:
        return IgnorePolicy.CONFIG.value
    return ignore_policy


def _split_on_ddash(args: list[str]) -> tuple[list[str], list[str], bool]:
    if "--" in args:
        cut = args.index("--")
        return args[:cut], args[cut + 1 :], True
    return args, [], False


def _route_help_flags(pre: list[str], command_names: set[str]) -> list[str]:
    if not any(token in _HELP_FLAGS for token in pre):
        return pre
    command_index = next((index for index, token in enumerate(pre) if token in command_names), None)
    if command_index is None:
        return pre
    stripped = [token for token in pre if token not in _HELP_FLAGS]
    command_index = next((index for index, token in enumerate(stripped) if token in command_names), None)
    if command_index is None:
        return pre
    return [*stripped[: command_index + 1], "--help", *stripped[command_index + 1 :]]


def _reorder_root_options(
    pre: list[str],
    *,
    command_options: Mapping[str, AbstractSet[str]],
    tail: list[str],
) -> list[str]:
    command_names = set(command_options)
    command_index = next((index for index, token in enumerate(pre) if token in command_names), None)
    if command_index is None:
        return [*pre, *tail]
    before_command = pre[:command_index]
    after_command = pre[command_index + 1 :]
    command_token = pre[command_index]
    extracted, remaining = _extract_root_options(after_command, local_options=command_options[command_token])
    return [*before_command, *extracted, command_token, *remaining, *tail]


def _extract_root_options(
    tokens: list[str],
    *,
    local_options: AbstractSet[str],
) -> tuple[list[str], list[str]]:
    extracted: list[str] = []
    remaining: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in local_options or any(token.startswith(f"{opt}=") for opt in local_options):
            remaining.append(token)
            if token in local_options and token in ROOT_FLAGS_WITH_VALUES and index + 1 < len(tokens):
                remaining.append(tokens[index + 1])
                index += 2
            else:
                index += 1
            continue
        if token in ROOT_FLAGS_NO_VALUES or _is_vflag(token):
            extracted.append(token)
            index += 1
            continue
        if token in ROOT_FLAGS_WITH_VALUES:
            extracted.append(token)
            if index + 1 < len(tokens):
                extracted.append(tokens[index + 1])
                index += 2
            else:
                index += 1
            continue
        if any(token.startswith(f"{flag}=") for flag in ROOT_FLAGS_WITH_VALUES):
            extracted.append(token)
            index += 1
            continue
        remaining.append(token)
        index += 1
    return extracted, remaining


def _first_non_global_index(args: list[str]) -> int | None:
    if "--" in args:
        ddash = args.index("--")
        return None if ddash + 1 >= len(args) else ddash + 1

    index = 0
    while index < len(args):
        token = args[index]
        if token in _HELP_FLAGS or token in _VERSION_FLAGS or _is_vflag(token):
            index += 1
            continue
        skip = _log_level_skip(token) or _root_opt_skip(token)
        if skip:
            index += skip
            continue
        break
    return None if index >= len(args) else index


def _is_vflag(flag: str) -> bool:
    if flag in _VERBOSE_FLAGS:
        return True
    if flag == "-":
        return False
    stripped = flag.lstrip("-")
    return bool(stripped) and set(stripped) == {"v"}


def _log_level_skip(flag: str) -> int:
    if flag == "--log-level":
        return 2
    if flag.startswith("--log-level="):
        return 1
    return 0


def _root_opt_skip(flag: str) -> int:
    if flag in ROOT_FLAGS_WITH_VALUES:
        return 2
    if flag in ROOT_FLAGS_NO_VALUES:
        return 1
    for prefix in ROOT_EQUALS_FORMS:
        if flag.startswith(prefix):
            return 1
    return 0


def _should_inject_for_token(token: str) -> bool:
    if token.startswith("-"):
        return True
    return _resolves_to_existing_path(token)


def _resolves_to_existing_path(token: str) -> bool:
    try:
        expanded = os.path.expandvars(token)
        try:
            candidate = Path(expanded).expanduser()
        except RuntimeError:
            return False
        candidate.lstat()
    except OSError:
        return False
    return True


ROOT_FLAGS_WITH_VALUES = {
    "--log-level",
    "--config",
    "--format",
    "--output",
    "--summary",
    "--summary-style",
    "--summary-to",
    "--summary-output",
    "--ignore-policy",
}
ROOT_FLAGS_NO_VALUES = {
    "--copy",
    "--ignore-defaults",
    "--no-ignore-config",
    "--no-ignore",
}
ROOT_EQUALS_FORMS = tuple(f"{flag}=" for flag in ROOT_FLAGS_WITH_VALUES)
