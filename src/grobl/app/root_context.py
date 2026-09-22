"""Root CLI argument normalization helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from collections.abc import Set as AbstractSet

DEFAULT_COMMAND = "scan"
VERBOSE_DEBUG_THRESHOLD = 2

_HELP_FLAGS = {"-h", "--help"}
_VERSION_FLAGS = {"-V", "--version"}
_VERBOSE_FLAGS = {"--verbose"}


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

    return _reorder_root_options(pre, command_options=command_options, tail=tail)


def inject_default_scan(
    args: list[str],
    *,
    command_names: Iterable[str] | None = None,
) -> list[str]:
    """Insert scan unless the first positional token is a known subcommand."""
    normalized = list(args)
    known_commands = set(command_names or ())
    pre = normalized[: normalized.index("--")] if "--" in normalized else normalized

    if not known_commands or any(token in _VERSION_FLAGS for token in pre):
        return normalized

    idx = _first_non_global_index(normalized)
    if idx is None:
        if any(token in _HELP_FLAGS for token in pre):
            return normalized
        normalized.append(DEFAULT_COMMAND)
    elif normalized[idx] not in known_commands:
        normalized.insert(idx, DEFAULT_COMMAND)
    return normalized


def _split_on_ddash(args: list[str]) -> tuple[list[str], list[str], bool]:
    if "--" in args:
        cut = args.index("--")
        return args[:cut], args[cut + 1 :], True
    return args, [], False


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
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            return index
        if arg in _HELP_FLAGS or arg in _VERSION_FLAGS or _is_vflag(arg):
            index += 1
            continue
        skip = _log_level_skip(arg) or _root_opt_skip(arg)
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


ROOT_FLAGS_WITH_VALUES = {
    "--log-level",
}
ROOT_FLAGS_NO_VALUES = {"--debug"}
ROOT_EQUALS_FORMS = tuple(f"{flag}=" for flag in ROOT_FLAGS_WITH_VALUES)
