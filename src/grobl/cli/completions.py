"""CLI entrypoint for emitting shell completion scripts."""

from __future__ import annotations

from typing import Final

import click

from .help_format import LiteralEpilogCommand

COMPLETION_TEMPLATES: Final[dict[str, str]] = {
    "bash": (
        '_grobl_completion() {{ eval "$(env {var}=bash_source {prog} "$@")"; }}\n'
        "complete -F _grobl_completion {prog}"
    ),
    "zsh": 'autoload -U compinit; compinit\neval "$(env {var}=zsh_source {prog})"',
    "fish": "eval (env {var}=fish_source {prog})",
}

COMPLETIONS_EPILOG = """\
Examples:
  grobl completions --shell bash
    Print a Bash completion script to stdout.

  grobl completions --shell zsh > ~/.zfunc/_grobl
    Save a Zsh completion file in a common location.

  grobl completions --shell fish > ~/.config/fish/completions/grobl.fish
    Install Fish completions for the current user.
"""


@click.command(cls=LiteralEpilogCommand, epilog=COMPLETIONS_EPILOG)
@click.option(
    "--shell",
    type=click.Choice(["bash", "zsh", "fish"], case_sensitive=False),
    required=True,
    help="Shell to generate a completion script for",
)
def completions(shell: str) -> None:
    """Print a shell completion script."""
    click.get_current_context(silent=True)
    prog = "grobl"
    var = "_GROBL_COMPLETE"
    template = COMPLETION_TEMPLATES[shell]
    print(template.format(var=var, prog=prog))
