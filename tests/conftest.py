from __future__ import annotations

import operator
import re
import xml.etree.ElementTree as ET  # noqa: S405
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ._workspace_path import ensure_workspace_packages_importable

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

ensure_workspace_packages_importable()


# --- Coverage XML discovery/parsing ------------------------------------------
def _find_coverage_xml_paths(
    root: Path = Path(), patterns: Sequence[str] = (".coverage.xml", "coverage.xml")
) -> list[Path]:
    """Return a list of coverage XML files found under `root` matching `patterns`."""
    files: list[Path] = []
    for pat in patterns:
        files.extend(root.rglob(pat))
    # de-duplicate while keeping order
    seen: set[Path] = set()
    out: list[Path] = []
    for p in files:
        if p not in seen and p.is_file():
            seen.add(p)
            out.append(p)
    return out


def _read_coverage_xml_file(path: Path) -> ET.Element | None:
    """Parse one coverage XML file and return its root, or None on error."""
    try:
        return ET.parse(path).getroot()  # noqa: S314 - parsing trusted local file
    except ET.ParseError:
        return None


def _read_all_coverage_roots(root: Path = Path()) -> list[ET.Element]:
    """Locate and parse all coverage XML files under `root`."""
    roots: list[ET.Element] = []
    for path in _find_coverage_xml_paths(root):
        r = _read_coverage_xml_file(path)
        if r is not None:
            roots.append(r)
    return roots


# --- Existing helpers (unchanged) --------------------------------------------
def _parse_condition_coverage(text: str) -> tuple[int, int] | None:
    m = re.search(r"\((\d+)/(\d+)\)", text)
    if not m:
        return None
    return int(m[1]), int(m[2])


def _iter_class_stats(root: ET.Element) -> Iterable[tuple[str, int, int, float, int, int, float]]:
    """Yield per-class stats from one coverage XML root.

    (filename, statements, missed, line_rate, branch_total, branch_covered, branch_rate)
    """
    for cls in root.findall(".//class"):
        filename = cls.get("filename", "")
        lines_node = cls.find("lines")
        lines = [] if lines_node is None else list(lines_node.findall("line"))

        statements = len(lines)
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
                if (parsed := _parse_condition_coverage(cc)) is not None:
                    covered, total = parsed
                    branch_total += total
                    branch_covered += covered

        branch_rate = (branch_covered / branch_total) if branch_total else 0.0
        yield filename, statements, missed, line_rate, branch_total, branch_covered, branch_rate


# --- Table formatting (unchanged) --------------------------------------------
def _normalize_headers(headers: Sequence[Sequence[str]]) -> list[tuple[str, ...]]:
    max_depth = max(len(h) for h in headers)
    return [tuple(("",) * (max_depth - len(h)) + tuple(h)) for h in headers]


def _compute_col_widths(headers: Sequence[Sequence[str]], rows: Sequence[Sequence[Any]]) -> list[int]:
    norm_headers = _normalize_headers(headers)
    ncols = len(headers)
    widths: list[int] = []
    for col in range(ncols):
        col_texts = [str(r[col]) for r in rows]
        col_texts.append(str(norm_headers[col][-1]))
        widths.append(max((len(x) for x in col_texts), default=0))
    return widths


def _adjust_widths_for_grouping(norm_headers: list[tuple[str, ...]], col_widths: list[int]) -> None:
    if not norm_headers:
        return
    max_depth = len(norm_headers[0])
    ncols = len(norm_headers)
    for level in range(max_depth):
        level_values = [norm_headers[col][level] for col in range(ncols)]
        start = 0
        while start < ncols:
            label = str(level_values[start])
            end = start
            while end < ncols and level_values[end] == level_values[start]:
                end += 1
            span = end - start
            if label.strip() and span > 0:
                span_width = sum(col_widths[start:end]) + (span - 1) * 3
                label_len = len(label)
                if label_len > span_width:
                    extra = label_len - span_width
                    base_add = extra // span
                    rem = extra % span
                    for idx in range(start, end):
                        col_widths[idx] += base_add + (1 if (idx - start) < rem else 0)
            start = end


def _render_header_level(level_values: Sequence[str], col_widths: Sequence[int]) -> str:
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


def format_table(headers: Sequence[Sequence[str]], rows: Sequence[Sequence[Any]]) -> str:
    if not headers:
        return ""
    norm_headers = _normalize_headers(headers)
    col_widths = _compute_col_widths(headers, rows)
    _adjust_widths_for_grouping(norm_headers, col_widths)

    header_lines: list[str] = []
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


# --- Aggregation across many coverage files -----------------------------------
def _aggregate_class_stats(roots: Sequence[ET.Element]) -> list[tuple[str, int, int, int, int, int]]:
    """Aggregate per-class stats across many XML roots by source filename.

    Returns rows as: (filename, stmt_tot, stmt_hit, stmt_miss, br_tot, br_hit)
    """
    acc: dict[str, dict[str, int]] = defaultdict(
        lambda: {"stmt_tot": 0, "stmt_miss": 0, "br_tot": 0, "br_hit": 0}
    )
    for root in roots:
        for fname, statements, missed, _line_rate, br_tot, br_hit, _br_rate in _iter_class_stats(root):
            if not fname or "src/" not in fname:
                continue
            a = acc[fname]
            a["stmt_tot"] += statements
            a["stmt_miss"] += missed
            a["br_tot"] += br_tot
            a["br_hit"] += br_hit

    rows: list[tuple[str, int, int, int, int, int]] = []
    for fname, a in acc.items():
        stmt_tot = a["stmt_tot"]
        stmt_miss = a["stmt_miss"]
        stmt_hit = stmt_tot - stmt_miss
        br_tot = a["br_tot"]
        br_hit = a["br_hit"]
        rows.append((fname, stmt_tot, stmt_hit, stmt_miss, br_tot, br_hit))
    return rows


# --- Pytest hook --------------------------------------------------------------
def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:
    """Pytest hook that prints a grouped Markdown table of coverage for files (combined across many XMLs)."""
    roots = _read_all_coverage_roots(Path())
    if not roots:
        return

    agg = _aggregate_class_stats(roots)
    if not agg:
        return

    # Per-file rows with recomputed percentages
    raw_rows = [
        (
            fname,
            stmt_tot,
            stmt_hit,
            stmt_miss,
            (f"{(stmt_hit / stmt_tot) * 100:.0f}%" if stmt_tot else "n/a"),
            br_tot,
            br_hit,
            (br_tot - br_hit),
            (f"{(br_hit / br_tot) * 100:.0f}%" if br_tot else "n/a"),
        )
        for (fname, stmt_tot, stmt_hit, stmt_miss, br_tot, br_hit) in sorted(agg, key=operator.itemgetter(0))
    ]

    # Totals
    sum_stmt_tot = sum(r[1] for r in raw_rows)
    sum_stmt_hit = sum(r[2] for r in raw_rows)
    sum_stmt_miss = sum(r[3] for r in raw_rows)
    stmt_cov = f"{(sum_stmt_hit / sum_stmt_tot) * 100:.0f}%" if sum_stmt_tot else "n/a"

    sum_br_tot = sum(r[5] for r in raw_rows)
    sum_br_hit = sum(r[6] for r in raw_rows)
    sum_br_miss = sum(r[7] for r in raw_rows)
    br_cov = f"{(sum_br_hit / sum_br_tot) * 100:.0f}%" if sum_br_tot else "n/a"

    headers = (
        ("Coverage Report", "", "File"),
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
    spacer_row = ("", "", "", "", "", "", "", "", "")
    total_row = (
        "Overall",
        sum_stmt_tot,
        sum_stmt_hit,
        sum_stmt_miss,
        stmt_cov,
        sum_br_tot,
        sum_br_hit,
        sum_br_miss,
        br_cov,
    )
    terminalreporter.write(format_table(headers, [*raw_rows, spacer_row, total_row]))
    terminalreporter.write_line("")
    terminalreporter.write_line("")
