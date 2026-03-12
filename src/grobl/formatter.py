"""Output formatting helpers."""

from __future__ import annotations

from grobl.metadata_visibility import DEFAULT_METADATA_VISIBILITY, MetadataVisibility


def human_summary(
    tree_lines: list[str],
    total_lines: int,
    total_chars: int,
    total_tokens: int,
    *,
    visibility: MetadataVisibility = DEFAULT_METADATA_VISIBILITY,
    table: str = "full",
    notes: list[str] | None = None,
) -> str:
    """Build a human-readable summary table and return it as a string."""
    notes = [] if notes is None else notes
    total_rows: list[str] = []
    if visibility.lines:
        total_rows.append(f"Total lines: {total_lines}")
    if visibility.chars:
        total_rows.append(f"Total characters: {total_chars}")
    if visibility.tokens:
        total_rows.append(f"Total tokens: {total_tokens}")
    if table == "compact":
        note_lines = "".join(f"Note: {note}\n" for note in notes)
        total_text = "".join(f"{row}\n" for row in total_rows)
        return f"{note_lines}{total_text}"

    max_width = max(len(line) for line in tree_lines) if tree_lines else len(" Project Summary ")
    title = " Project Summary "
    bar = "═" * max((max_width - len(title)) // 2, 0)

    out: list[str] = []
    out.append(f"{bar}{title}{bar}")
    out.extend(tree_lines)
    if total_rows:
        out.append("─" * max_width)
        out.extend(total_rows)
    out.extend(f"Note: {note}" for note in notes)
    out.append("═" * max_width)
    return "\n".join(out) + ("\n" if out else "")
