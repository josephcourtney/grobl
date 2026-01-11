"""Top-level CLI wiring that enforces spec-compliant behavior."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from grobl import __version__
from grobl.constants import IgnorePolicy, PayloadFormat, SummaryDestination, SummaryFormat, TableStyle

from .common import exit_on_broken_pipe
from .completions import completions
from .explain import explain
from .init import init
from .scan import scan
from .version import version

if TYPE_CHECKING:
    from collections.abc import Iterable

# Threshold for -vv to map to DEBUG
DEFAULT_COMMAND = "scan"
VERBOSE_DEBUG_THRESHOLD = 2

CLI_CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
}

_HELP_FLAGS = {"-h", "--help"}
_VERSION_FLAGS = {"-V", "--version"}
_VERBOSE_FLAGS = {"--verbose"}

ROOT_EPILOG = """\
Default behavior:
  Running `grobl` or `grobl <path>` is shorthand for `grobl scan <path>`.
  If you intended to scan a path but it does not exist, use `grobl scan <path>`
  to see scan-specific diagnostics.

Examples:
  grobl
  grobl .
  grobl src tests
  grobl scan --format json --output payload.json
  grobl scan --summary json --summary-to stdout
  grobl scan --ignore-policy defaults --add-ignore '*.min.js' src
  grobl explain README.md --format json
  grobl explain docs --include-content 'docs/**'
"""


class RootGroup(click.Group):
    """Group subclass that injects scan and keeps help concise."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        # Click parses group options only before the command token.
        # We normalize argv to support "global options anywhere" and "-h scan" behavior.
        normalized = _normalize_argv(list(args), commands=self.commands)
        normalized = _inject_default_scan(list(normalized), commands=self.commands)
        normalized = _normalize_argv(list(normalized), commands=self.commands)
        return super().parse_args(ctx, normalized)

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        super().format_help(ctx, formatter)
        formatter.write_paragraph()
        formatter.write_text(f"Use `grobl {DEFAULT_COMMAND} --help` for scan options and examples.")


@click.group(cls=RootGroup, context_settings=CLI_CONTEXT_SETTINGS, epilog=ROOT_EPILOG)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (use -vv for debug)",
)
@click.option(
    "--log-level",
    type=click.Choice(["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], case_sensitive=False),
    help="Set log level explicitly (overrides -v / -vv).",
)
@click.option("--config", "config_path", type=click.Path(path_type=Path), help="Explicit config file path")
@click.option(
    "--format",
    "payload_format",
    type=click.Choice([p.value for p in PayloadFormat], case_sensitive=False),
    default=PayloadFormat.LLM.value,
    help="Payload format to emit",
)
@click.option("--copy", is_flag=True, help="Copy the payload to the clipboard")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Write the payload to a file path (use '-' for stdout).",
)
@click.option(
    "--summary",
    type=click.Choice([s.value for s in SummaryFormat], case_sensitive=False),
    default=SummaryFormat.AUTO.value,
    help="Summary mode to display",
)
@click.option(
    "--summary-style",
    type=click.Choice([t.value for t in TableStyle], case_sensitive=False),
    default=None,
    help="Summary table style (auto/full/compact; only valid with --summary table)",
)
@click.option(
    "--summary-to",
    type=click.Choice([d.value for d in SummaryDestination], case_sensitive=False),
    default=SummaryDestination.STDERR.value,
    help="Destination for summary output (defaults to stderr)",
)
@click.option(
    "--summary-output",
    type=click.Path(path_type=Path),
    help="File path to write the summary when --summary-to file is selected",
)
@click.option(
    "-I",
    "--ignore-defaults",
    is_flag=True,
    help="Disable bundled default ignore rules (alias for --ignore-policy config)",
)
@click.option(
    "--no-ignore-config",
    is_flag=True,
    help="Disable ignore rules from discovered .grobl.toml files (alias for --ignore-policy defaults)",
)
@click.option(
    "--no-ignore",
    is_flag=True,
    help="Disable all ignore patterns (alias for --ignore-policy none)",
)
@click.option(
    "--ignore-policy",
    type=click.Choice([p.value for p in IgnorePolicy], case_sensitive=False),
    default=IgnorePolicy.AUTO.value,
    help="Ignore source policy: auto|all|none|defaults|config|cli",
)
@click.version_option(__version__, "-V", "--version", message="%(version)s")
def cli(
    *,
    verbose: int,
    log_level: str | None,
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
    """Scan directories and emit LLM/Markdown/JSON payloads (default scan command)."""
    # Stash global options for subcommands.
    ctx = click.get_current_context(silent=True)
    if ctx is not None:
        ctx.obj = ctx.obj or {}
        final_ignore_policy = ignore_policy
        if final_ignore_policy == IgnorePolicy.AUTO.value:
            if no_ignore:
                final_ignore_policy = IgnorePolicy.NONE.value
            elif no_ignore_config:
                final_ignore_policy = IgnorePolicy.DEFAULTS.value
            elif ignore_defaults:
                final_ignore_policy = IgnorePolicy.CONFIG.value
        ctx.obj.update({
            "config_path": config_path,
            "payload_format": payload_format,
            "copy": copy,
            "output": output,
            "summary": summary,
            "summary_style": summary_style,
            "summary_to": summary_to,
            "summary_output": summary_output,
            "ignore_policy": final_ignore_policy,
            "ignore_defaults_flag": ignore_defaults,
            "no_ignore_config_flag": no_ignore_config,
            "no_ignore_flag": no_ignore,
        })
    if log_level:
        level = getattr(logging, log_level.upper())
    elif verbose >= VERBOSE_DEBUG_THRESHOLD:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(level=level, force=True)


def main(argv: list[str] | None = None) -> None:
    """Entry-point wrapper invoked from ``python -m grobl``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        cli.main(args=argv, prog_name="grobl", standalone_mode=False)
    except BrokenPipeError:
        exit_on_broken_pipe()


cli.add_command(scan)
cli.add_command(explain)
cli.add_command(version)
cli.add_command(completions)
cli.add_command(init)


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


def _split_on_ddash(args: list[str]) -> tuple[list[str], list[str], bool]:
    if "--" in args:
        cut = args.index("--")
        return args[:cut], args[cut + 1 :], True
    return args, [], False


def _route_help_flags(pre: list[str], command_names: set[str]) -> list[str]:
    if not any(tok in _HELP_FLAGS for tok in pre):
        return pre
    cmd_pos = next((i for i, tok in enumerate(pre) if tok in command_names), None)
    if cmd_pos is None:
        return pre
    stripped = [tok for tok in pre if tok not in _HELP_FLAGS]
    cmd_pos2 = next((i for i, tok in enumerate(stripped) if tok in command_names), None)
    if cmd_pos2 is None:
        return pre
    return [*stripped[: cmd_pos2 + 1], "--help", *stripped[cmd_pos2 + 1 :]]


def _extract_root_options(tokens: list[str], *, command: str | None = None) -> tuple[list[str], list[str]]:
    extracted: list[str] = []
    remaining: list[str] = []
    i = 0
    explain_format_option = command == "explain"
    while i < len(tokens):
        tok = tokens[i]
        if explain_format_option and tok == "--format":
            remaining.append(tok)
            if i + 1 < len(tokens):
                remaining.append(tokens[i + 1])
                i += 2
            else:
                i += 1
            continue
        if explain_format_option and tok.startswith("--format="):
            remaining.append(tok)
            i += 1
            continue
        if tok in ROOT_FLAGS_NO_VALUES or _is_vflag(tok):
            extracted.append(tok)
            i += 1
            continue
        if tok in ROOT_FLAGS_WITH_VALUES:
            extracted.append(tok)
            if i + 1 < len(tokens):
                extracted.append(tokens[i + 1])
                i += 2
            else:
                i += 1
            continue
        if any(tok.startswith(f"{flag}=") for flag in ROOT_FLAGS_WITH_VALUES):
            extracted.append(tok)
            i += 1
            continue
        remaining.append(tok)
        i += 1
    return extracted, remaining


def _reorder_root_options(
    pre: list[str],
    command_names: set[str],
    tail: list[str],
) -> list[str]:
    cmd_pos = next((i for i, tok in enumerate(pre) if tok in command_names), None)
    if cmd_pos is None:
        return [*pre, *tail]
    before_cmd = pre[:cmd_pos]
    after_cmd = pre[cmd_pos + 1 :]
    command_token = pre[cmd_pos]
    extracted, remaining = _extract_root_options(after_cmd, command=command_token)
    reordered = [*before_cmd, *extracted, command_token, *remaining]
    return [*reordered, *tail]


def _normalize_argv(args: list[str], *, commands: Iterable[str] | None) -> list[str]:
    """
    Normalize argv.

      - global options recognized anywhere (move them before command)
      - `--` terminates option parsing (do not move tokens after `--`)
      - `grobl -h scan` behaves like `grobl scan -h` (route help to the subcommand).
    """
    if commands is None:
        return args
    command_names = set(commands)
    if not command_names:
        return args

    pre, post, has_ddash = _split_on_ddash(args)
    tail = (["--"] if has_ddash else []) + post

    if any(tok in _VERSION_FLAGS for tok in pre):
        return args

    normalized_pre = _route_help_flags(pre, command_names)
    return _reorder_root_options(normalized_pre, command_names, tail)


def _inject_default_scan(
    args: list[str],
    *,
    commands: Iterable[str] | None = None,
) -> list[str]:
    """Insert ``scan`` when the first non-global token warrants it."""
    normalized = list(args)
    if commands is None:
        return normalized

    command_names = set(commands)
    if not command_names:
        return normalized

    # If any explicit command appears before `--` (or anywhere if no `--`),
    # do not inject.
    if "--" in normalized:
        dd = normalized.index("--")
        pre = normalized[:dd]
    else:
        pre = normalized
    if any(tok in command_names for tok in pre):
        return normalized

    scan_exists = DEFAULT_COMMAND in command_names
    idx = _first_non_global_index(normalized)
    if idx is None:
        if scan_exists:
            normalized.append(DEFAULT_COMMAND)
        return normalized

    token = normalized[idx]
    if token in command_names:
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


def _first_non_global_index(args: list[str]) -> int | None:
    """Return the index after skipping global options, or None if none remain."""
    # `--` terminates option parsing: the first token after `--` is non-global for injection.
    if "--" in args:
        dd = args.index("--")
        return None if dd + 1 >= len(args) else dd + 1

    idx = 0
    while idx < len(args):
        token = args[idx]
        if token in _HELP_FLAGS or token in _VERSION_FLAGS:
            idx += 1
            continue
        if _is_vflag(token):
            idx += 1
            continue
        skip = _log_level_skip(token)
        if skip:
            idx += skip
            continue
        # Other root options with values
        skip2 = _root_opt_skip(token)
        if skip2:
            idx += skip2
            continue
        break
    return None if idx >= len(args) else idx


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
    # Root options defined on the group.
    if flag in {
        "--config",
        "--format",
        "--output",
        "--summary",
        "--summary-style",
        "--summary-to",
        "--summary-output",
        "--ignore-policy",
    }:
        return 2
    if flag == "--copy":
        return 1
    # equals forms
    for k in (
        "--config=",
        "--format=",
        "--output=",
        "--summary=",
        "--summary-style=",
        "--summary-to=",
        "--summary-output=",
        "--ignore-policy=",
    ):
        if flag.startswith(k):
            return 1
    return 0


def _should_inject_for_token(token: str) -> bool:
    if token.startswith("-"):
        return True
    # Be conservative: only treat non-flag tokens as scan targets if they resolve
    # to an existing path. This avoids surprising behavior for typos.
    return _resolves_to_existing_path(token)


def _is_path_like(token: str) -> bool:
    return any(char in token for char in (".", "~", "/", "\\"))


def _resolves_to_existing_path(token: str) -> bool:
    # Spec: user expansion includes env var expansion and tilde; existence uses lstat semantics.
    try:
        expanded = os.path.expandvars(token)
        try:
            candidate = Path(expanded).expanduser()
        except RuntimeError:
            return False
        candidate.lstat()  # treat symlink itself as existing even if target missing
    except OSError:
        return False
    else:
        return True
