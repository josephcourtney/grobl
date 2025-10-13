"""CLI entrypoint for emitting shell completion scripts."""

from __future__ import annotations

import sys
from typing import Final

import click

from grobl.constants import EXIT_USAGE

COMPLETION_TEMPLATES: Final[dict[str, str]] = {
    "bash": (
        '_grobl_completion() {{ eval "$(env {var}=bash_source {prog} "$@")"; }}\n'
        "complete -F _grobl_completion {prog}"
    ),
    "zsh": 'autoload -U compinit; compinit\neval "$(env {var}=zsh_source {prog})"',
    "fish": "eval (env {var}=fish_source {prog})",
}


@click.command()
@click.option(
    "--shell",
    type=click.Choice(["bash", "zsh", "fish"], case_sensitive=False),
    required=True,
    help="Target shell to generate completion script for",
)
def completions(shell: str) -> None:
    """Print shell completion script for the given shell."""
    prog = "grobl"
    var = "_GROBL_COMPLETE"
    try:
        template = COMPLETION_TEMPLATES[shell]
    except KeyError as err:  # pragma: no cover - defensive
        print(f"Unsupported shell: {shell}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE) from err
    print(template.format(var=var, prog=prog))
