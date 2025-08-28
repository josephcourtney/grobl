from __future__ import annotations

import sys

import click

from grobl.constants import EXIT_USAGE


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
    if shell == "bash":
        print(
            f'_grobl_completion() {{ eval "$(env {var}=bash_source {prog} "$@")"; }}\n'
            f"complete -F _grobl_completion {prog}"
        )
    elif shell == "zsh":
        print(f'autoload -U compinit; compinit\n_eval "$(env {var}=zsh_source {prog})"')
    elif shell == "fish":
        print(f"eval (env {var}=fish_source {prog})")
    else:  # pragma: no cover - defensive
        print(f"Unsupported shell: {shell}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)
