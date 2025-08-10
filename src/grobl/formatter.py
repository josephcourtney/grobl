"""Output formatting helpers."""

import re


def escape_markdown(text: str) -> str:
    """Escape Markdown metacharacters in ``text``."""

    markdown_chars = r"([*_#\[\]{}()>+\-.!])"
    return re.sub(markdown_chars, r"\\\1", text)


def human_summary(
    tree_lines: list[str],
    total_lines: int,
    total_chars: int,
    *,
    total_tokens: int | None = None,
    tokenizer: str | None = None,
    budget: int | None = None,
) -> None:
    """Print a human-readable summary table.

    ``tokenizer`` is accepted for backwards compatibility but is no longer
    displayed in the summary title.
    """

    max_width = max(len(line) for line in tree_lines)
    title = " Project Summary "
    bar = "═" * ((max_width - len(title)) // 2)
    print(f"{bar}{title}{bar}")
    for line in tree_lines:
        print(line)
    print("─" * max_width)
    print(f"Total lines: {total_lines}")
    print(f"Total characters: {total_chars}")
    if total_tokens is not None:
        line = f"Total tokens: {total_tokens}"
        if budget:
            pct = total_tokens / budget if budget else 0
            line += f" ({pct:.0%} of {budget:,} token budget)"
        print(line)
    print("═" * max_width)
