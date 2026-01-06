"""CLI entrypoint for emitting shell completion scripts."""

from __future__ import annotations

from typing import Final

import click

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
    click.get_current_context(silent=True)
    prog = "grobl"
    var = "_GROBL_COMPLETE"
    template = COMPLETION_TEMPLATES[shell]
    print(template.format(var=var, prog=prog))
