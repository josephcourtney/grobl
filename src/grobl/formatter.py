"""Output formatting helpers."""


def human_summary(
    tree_lines: list[str],
    total_lines: int,
    total_chars: int,
    *,
    table: str = "full",
) -> str:
    """Build a human-readable summary table and return it as a string."""
    if table == "none":
        return ""

    if table == "compact":
        return f"Total lines: {total_lines}\nTotal characters: {total_chars}\n"

    max_width = max(len(line) for line in tree_lines) if tree_lines else len(" Project Summary ")
    title = " Project Summary "
    bar = "═" * max((max_width - len(title)) // 2, 0)

    out: list[str] = []
    out.append(f"{bar}{title}{bar}")
    out.extend(tree_lines)
    out.extend((
        "─" * max_width,
        f"Total lines: {total_lines}",
        f"Total characters: {total_chars}",
        "═" * max_width,
    ))
    return "\n".join(out) + ("\n" if out else "")
