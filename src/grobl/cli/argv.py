"""Argument normalization helpers for the root CLI group."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from collections.abc import Set as AbstractSet

DEFAULT_COMMAND = "scan"

_HELP_FLAGS = {"-h", "--help"}
_VERSION_FLAGS = {"-V", "--version"}
_VERBOSE_FLAGS = {"--verbose"}


def build_command_option_map(commands: Mapping[str, click.Command]) -> dict[str, set[str]]:
    """Return the long option names declared by each subcommand."""
    option_map: dict[str, set[str]] = {}
    for name, command in commands.items():
        local_options = {
            opt_name
            for param in command.params
            if isinstance(param, click.Option)
            for opt_name in param.opts
            if opt_name.startswith("--")
        }
        option_map[name] = local_options
    return option_map


def normalize_argv(
    args: list[str],
    *,
    command_options: Mapping[str, AbstractSet[str]] | None,
) -> list[str]:
    """
    Normalize argv.

      - global options recognized anywhere (move them before command)
      - `--` terminates option parsing (do not move tokens after `--`)
      - `grobl -h scan` behaves like `grobl scan -h` (route help to the subcommand).
    """
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
    """Insert ``scan`` when the first non-global token warrants it."""
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


def _split_on_ddash(args: list[str]) -> tuple[list[str], list[str], bool]:
    if "--" in args:
        cut = args.index("--")
        return args[:cut], args[cut + 1 :], True
    return args, [], False


def _route_help_flags(pre: list[str], command_names: set[str]) -> list[str]:
    if not any(token in _HELP_FLAGS for token in pre):
        return pre
    command_index = next(
        (index for index, token in enumerate(pre) if token in command_names),
        None,
    )
    if command_index is None:
        return pre
    stripped = [token for token in pre if token not in _HELP_FLAGS]
    command_index = next(
        (index for index, token in enumerate(stripped) if token in command_names),
        None,
    )
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
    command_index = next(
        (index for index, token in enumerate(pre) if token in command_names),
        None,
    )
    if command_index is None:
        return [*pre, *tail]
    before_command = pre[:command_index]
    after_command = pre[command_index + 1 :]
    command_token = pre[command_index]
    extracted, remaining = _extract_root_options(
        after_command,
        local_options=command_options[command_token],
    )
    reordered = [*before_command, *extracted, command_token, *remaining]
    return [*reordered, *tail]


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
ROOT_FLAGS_NO_VALUES = {"--copy", "--ignore-defaults", "--no-ignore-config", "--no-ignore"}
ROOT_EQUALS_FORMS = tuple(f"{flag}=" for flag in ROOT_FLAGS_WITH_VALUES)
