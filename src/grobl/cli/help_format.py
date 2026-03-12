"""Custom Click command classes for literal epilog rendering."""

from __future__ import annotations

import click


class LiteralEpilogCommand(click.Command):
    """Render epilog text literally so multi-line examples stay aligned."""

    def format_epilog(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:  # noqa: ARG002
        if self.epilog:
            formatter.write_paragraph()
            formatter.write(f"{self.epilog}\n")


class LiteralEpilogGroup(click.Group):
    """Group variant that also renders epilog text literally."""

    def format_epilog(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:  # noqa: ARG002
        if self.epilog:
            formatter.write_paragraph()
            formatter.write(f"{self.epilog}\n")
