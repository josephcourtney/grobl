import re


def escape_markdown(text: str) -> str:
    """Escape Markdown metacharacters."""
    markdown_chars = r"([*_#\[\]{}()>+\-.!])"
    return re.sub(markdown_chars, r"\\\1", text)


def human_summary(tree_lines: list[str], total_lines: int, total_chars: int) -> None:
    max_width = max(len(line) for line in tree_lines)
    title = " Project Summary "
    bar = "═" * ((max_width - len(title)) // 2)
    print(f"{bar}{title}{bar}")
    for line in tree_lines:
        print(line)
    print("─" * max_width)
    print(f"Total lines: {total_lines}")
    print(f"Total characters: {total_chars}")
    print("═" * max_width)
