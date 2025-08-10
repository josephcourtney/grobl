from pathlib import Path

import pytest

from grobl.directory import DirectoryTreeBuilder
from grobl.formatter import escape_markdown, human_summary


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hello *world*", r"Hello \*world\*"),
        ("_underscore_", r"\_underscore\_"),
        ("#header", r"\#header"),
        ("(parentheses)", r"\(parentheses\)"),
        ("normal text", "normal text"),
        ("multiple * _ # []", r"multiple \* \_ \# \[\]"),
    ],
)
def test_escape_markdown(text, expected):
    assert escape_markdown(text) == expected


def test_add_md_file_escapes_backticks(tmp_path):
    builder = DirectoryTreeBuilder(tmp_path, [])
    rel = Path("example.md")
    builder.add_file(
        tmp_path / "example.md", rel, 1, 10, 0, "Some content with ``` backticks."
    )
    out = builder.build_file_contents()
    assert r"\`\`\`" in out


def test_human_summary_budget(capsys):
    human_summary(
        [
            "project",
        ],
        10,
        20,
        total_tokens=24956,
        tokenizer="o200k_base",
        budget=32_000,
    )
    out = capsys.readouterr().out
    first_line = out.splitlines()[0]
    assert first_line.strip() == "Project Summary"
    assert "o200k_base" not in first_line
    assert "Total tokens: 24956 (78% of 32,000 token budget)" in out
