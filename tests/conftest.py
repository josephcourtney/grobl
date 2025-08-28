from __future__ import annotations

import operator
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


def _read_coverage_xml() -> ET.Element | None:
    """Return parsed .coverage.xml root or None if missing / invalid."""
    path = Path(".coverage.xml")
    if not path.exists():
        return None
    try:
        return ET.parse(path).getroot()
    except ET.ParseError:
        return None


def _parse_condition_coverage(text: str) -> tuple[int, int] | None:
    """Parse a condition-coverage string like '(1/2)' and return (covered, total)."""
    m = re.search(r"\((\d+)/(\d+)\)", text)
    if not m:
        return None
    # use indexing for re.Match groups
    return int(m[1]), int(m[2])


def _iter_class_stats(root: ET.Element) -> Iterable[tuple[str, int, int, float, int, int, float]]:
    """Yield per-class coverage statistics:
    (filename, statements, missed, line_rate, branch_total, branch_covered, branch_rate).
    """
    for cls in root.findall(".//class"):
        filename = cls.get("filename", "")
        lines_node = cls.find("lines")
        lines = [] if lines_node is None else list(lines_node.findall("line"))

        statements = len(lines)
        # simplified sum of booleans (True == 1)
        missed = sum(ln.get("hits", "0") == "0" for ln in lines)

        try:
            line_rate = float(cls.get("line-rate", "0"))
        except ValueError:
            line_rate = 0.0

        branch_total = 0
        branch_covered = 0
        for ln in lines:
            if ln.get("branch") == "true":
                cc = ln.get("condition-coverage") or ""
                # use named expression to parse and test in one step
                if (parsed := _parse_condition_coverage(cc)) is not None:
                    covered, total = parsed
                    branch_total += total
                    branch_covered += covered

        branch_rate = (branch_covered / branch_total) if branch_total else 0.0
        yield filename, statements, missed, line_rate, branch_total, branch_covered, branch_rate


# --- Table formatting helpers -------------------------------------------------
def _normalize_headers(headers: Sequence[Sequence[str]]) -> list[tuple[str, ...]]:
    max_depth = max(len(h) for h in headers)
    return [tuple(("",) * (max_depth - len(h)) + tuple(h)) for h in headers]


def _compute_col_widths(headers: Sequence[Sequence[str]], rows: Sequence[Sequence[Any]]) -> list[int]:
    """Compute minimal column widths based on bottom header (leaf) and cell contents."""
    norm_headers = _normalize_headers(headers)
    ncols = len(headers)
    widths: list[int] = []
    for col in range(ncols):
        col_texts = [str(r[col]) for r in rows]
        # only include the bottom-level header for width calculation
        col_texts.append(str(norm_headers[col][-1]))
        widths.append(max((len(x) for x in col_texts), default=0))
    return widths


def _adjust_widths_for_grouping(norm_headers: list[tuple[str, ...]], col_widths: list[int]) -> None:
    """Ensure group header labels fit into their spanned columns by expanding widths minimally."""
    if not norm_headers:
        return
    max_depth = len(norm_headers[0])
    ncols = len(norm_headers)
    for level in range(max_depth):
        level_values = [norm_headers[col][level] for col in range(ncols)]
        start = 0
        while start < ncols:
            label = str(level_values[start])
            # find span of identical group labels
            end = start
            while end < ncols and level_values[end] == level_values[start]:
                end += 1
            span = end - start
            if label.strip() and span > 0:
                span_width = sum(col_widths[start:end]) + (span - 1) * 3  # account for " | "
                label_len = len(label)
                if label_len > span_width:
                    extra = label_len - span_width
                    base_add = extra // span
                    rem = extra % span
                    for idx in range(start, end):
                        col_widths[idx] += base_add + (1 if (idx - start) < rem else 0)
            start = end


def _render_header_level(level_values: Sequence[str], col_widths: Sequence[int]) -> str:
    """Render one level of grouped header values."""
    parts: list[str] = []
    n = len(level_values)
    idx = 0
    while idx < n:
        label = str(level_values[idx])
        end = idx
        while end < n and level_values[end] == level_values[idx]:
            end += 1
        span_width = sum(col_widths[idx:end]) + (end - idx - 1) * 3
        cell = " " * span_width if not label.strip() else label.center(span_width)
        parts.append(cell)
        idx = end
    return "| " + " | ".join(parts) + " |"


# --- Public function ---------------------------------------------------------
def format_table(headers: Sequence[Sequence[str]], rows: Sequence[Sequence[Any]]) -> str:
    """Format a Markdown table with hierarchical headers, grouping parent headers.

    headers: sequence of column header tuples (from parent to child).
    rows: sequence of row sequences (one sequence per row, matching number of headers).
    Returns the full Markdown string for the table.
    """
    if not headers:
        return ""

    norm_headers = _normalize_headers(headers)
    col_widths = _compute_col_widths(headers, rows)
    _adjust_widths_for_grouping(norm_headers, col_widths)

    # Build header lines by transposing norm_headers (levels)
    header_lines: list[str] = []
    # transpose manually to avoid depending on zip(strict=...) availability
    max_depth = len(norm_headers[0])
    for level in range(max_depth):
        level_values = [norm_headers[col][level] for col in range(len(norm_headers))]
        header_lines.append(_render_header_level(level_values, col_widths))

    sep_parts = ["-" * w for w in col_widths]
    sep_line = "| " + " | ".join(sep_parts) + " |"

    data_lines: list[str] = []
    for row in rows:
        parts = [str(val).rjust(w) for val, w in zip(row, col_widths, strict=False)]
        data_lines.append("| " + " | ".join(parts) + " |")

    return "\n".join([*header_lines, sep_line, *data_lines])


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:
    """Pytest hook that prints a grouped Markdown table of coverage for grobl files."""
    root = _read_coverage_xml()
    if root is None:
        return

    # Build rows only for files under grobl/ or src/grobl/
    raw_rows = [
        (
            fname,
            total_statements,
            total_statements - uncovered,
            uncovered,
            (f"{line_rate * 100:.0f}%" if line_rate else "n/a"),
            total_branches,
            covered_branches,
            total_branches - covered_branches,
            (f"{(covered_branches / total_branches) * 100:.0f}%" if total_branches else "n/a"),
        )
        for fname, total_statements, uncovered, line_rate, total_branches, covered_branches, _br_rate in _iter_class_stats(
            root
        )
        if fname and ("src/grobl/" in fname or fname.startswith("grobl/"))
    ]

    if not raw_rows:
        return

    raw_rows.sort(key=operator.itemgetter(0))

    headers = (
        (
            "Coverage Report",
            "",
            "File",
        ),
        ("Coverage Report", "Statements", "Tot."),
        ("Coverage Report", "Statements", "Hit"),
        ("Coverage Report", "Statements", "Miss"),
        ("Coverage Report", "Statements", "Cov."),
        ("Coverage Report", "Branches", "Tot."),
        ("Coverage Report", "Branches", "Hit"),
        ("Coverage Report", "Branches", "Miss"),
        ("Coverage Report", "Branches", "Cov."),
    )

    terminalreporter.write_line("")
    terminalreporter.write(format_table(headers, raw_rows))
    terminalreporter.write_line("")
    terminalreporter.write_line("")
