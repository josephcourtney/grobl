from __future__ import annotations

import re
import xml.etree.ElementTree as ET  # noqa: S405
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence


# --------------------------- Models ------------------------------------------
@dataclass(frozen=True)
class LineAgg:
    hits: int = 0
    br_cov: int = 0
    br_tot: int = 0


@dataclass
class FileAgg:
    lines: dict[int, LineAgg]  # lineno -> agg


@dataclass(slots=True)
class ReportConfig:
    """Configuration for coverage report generation."""

    root: Path = field(default_factory=Path)
    patterns: Sequence[str] = (".coverage.xml", "coverage.xml")
    include: str | None = None
    exclude: str | None = None
    rel_to: Path | None = field(default_factory=Path)
    sort: str = "file"  # "stmt_cov", "br_cov", "miss"
    show_branches: bool = True
    green_threshold: float = 90.0
    yellow_threshold: float = 75.0
    fail_under_line: float | None = None
    fail_under_branch: float | None = None


@dataclass(slots=True)
class Totals:
    """Aggregate statement and branch coverage counts."""

    stmt_total: int = 0
    stmt_hit: int = 0
    br_total: int = 0
    br_hit: int = 0

    def add(self, *, stmt_total: int, stmt_hit: int, br_total: int, br_hit: int) -> None:
        self.stmt_total += stmt_total
        self.stmt_hit += stmt_hit
        self.br_total += br_total
        self.br_hit += br_hit


# --------------------------- Discovery/Parsing -------------------------------
def _find_coverage_xml_paths(root: Path, patterns: Sequence[str]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for pat in patterns:
        for p in root.rglob(pat):
            if p.is_file() and p not in seen:
                seen.add(p)
                out.append(p)
    return out


def _read_coverage_xml_file(path: Path) -> ET.Element | None:
    try:
        return ET.parse(path).getroot()  # noqa: S314 (trusted local file)
    except ET.ParseError:
        return None


def _read_all_coverage_roots(root: Path, patterns: Sequence[str]) -> list[ET.Element]:
    roots: list[ET.Element] = []
    for path in _find_coverage_xml_paths(root, patterns):
        r = _read_coverage_xml_file(path)
        if r is not None:
            roots.append(r)
    return roots


_cond_re = re.compile(r"\(?\s*(\d+)\s*/\s*(\d+)\s*\)?")


def _parse_condition_coverage(text: str) -> tuple[int, int] | None:
    # Accept "50% (1/2)" or "(1/2)" or "1/2"
    m = _cond_re.search(text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _iter_lines(root: ET.Element) -> Iterable[tuple[str, int, int, int, int]]:
    """Yield per-line stats: (filename, lineno, hits, br_covered, br_total)."""
    for cls in root.findall(".//class"):
        fname = cls.get("filename", "")
        lines_node = cls.find("lines")
        if not fname or lines_node is None:
            continue
        for ln in lines_node.findall("line"):
            try:
                lineno = int(ln.get("number", "0"))
            except ValueError:
                continue
            hits = int(ln.get("hits", "0") or 0)
            br_cov = 0
            br_tot = 0
            if ln.get("branch") == "true":
                cc = ln.get("condition-coverage") or ""
                parsed = _parse_condition_coverage(cc)
                if parsed is not None:
                    br_cov, br_tot = parsed
            yield fname, lineno, hits, br_cov, br_tot


# --------------------------- Aggregation -------------------------------------
def _compile_filters(include: str | None, exclude: str | None) -> Callable[[Path], bool]:
    inc = re.compile(include) if include else None
    exc = re.compile(exclude) if exclude else None

    def ok(p: Path) -> bool:
        s = str(p)
        if inc and not inc.search(s):
            return False
        return not (exc and exc.search(s))

    return ok


def _aggregate(roots: Sequence[ET.Element], include: str | None, exclude: str | None) -> dict[str, FileAgg]:
    ok = _compile_filters(include, exclude)
    acc: dict[str, FileAgg] = {}
    for root in roots:
        for fname, lineno, hits, br_cov, br_tot in _iter_lines(root):
            fpath = Path(fname).resolve()
            if not ok(fpath):
                continue
            key = str(fpath)
            fa = acc.setdefault(key, FileAgg(lines={}))
            la = fa.lines.get(lineno, LineAgg())
            # Combine across reports: take max hits and max covered/total
            new_hits = max(la.hits, hits)
            new_br_cov = max(la.br_cov, br_cov)
            new_br_tot = max(la.br_tot, br_tot)
            fa.lines[lineno] = LineAgg(new_hits, new_br_cov, new_br_tot)
    return acc


# --------------------------- Summaries ---------------------------------------
def _summarize_files(acc: dict[str, FileAgg]) -> tuple[list[tuple], Totals]:
    rows_raw: list[tuple] = []
    totals = Totals()
    for fpath, fa in acc.items():
        stmt_total = len(fa.lines)
        stmt_hit = sum(1 for la in fa.lines.values() if la.hits > 0)
        stmt_miss = stmt_total - stmt_hit
        br_total = sum(la.br_tot for la in fa.lines.values())
        br_hit = sum(la.br_cov for la in fa.lines.values())
        br_miss = br_total - br_hit

        totals.add(stmt_total=stmt_total, stmt_hit=stmt_hit, br_total=br_total, br_hit=br_hit)
        rows_raw.append((
            fpath,
            stmt_total,
            stmt_hit,
            stmt_miss,
            (100.0 * stmt_hit / stmt_total) if stmt_total else None,
            br_total,
            br_hit,
            br_miss,
            (100.0 * br_hit / br_total) if br_total else None,
        ))
    return rows_raw, totals


# --------------------------- Formatting --------------------------------------
def _style_percent(pct: float | None, green: float, yellow: float) -> str:
    if pct is None:
        return "n/a"
    v = round(pct)
    if v >= green:
        return f"[green]{v}%[/green]"
    if v >= yellow:
        return f"[yellow]{v}%[/yellow]"
    return f"[red]{v}%[/red]"


def _style_miss(n: int) -> str:
    return f"[red]{n}[/red]" if n else f"[green]{n}[/green]"


def _relativize(path: str, rel_to: Path | None) -> str:
    if not rel_to:
        return path
    try:
        return str(Path(path).resolve().relative_to(rel_to.resolve()))
    except (OSError, ValueError):
        return path


# --------------------------- Table -------------------------------------------
def _build_table(
    rows: Sequence[Sequence[str]],
    totals: Sequence[str],
    *,
    show_branches: bool,
) -> Table:
    table = Table(title="Coverage Report", box=box.SIMPLE_HEAVY, header_style="bold", expand=True)

    table.add_column("File", style="cyan", overflow="fold")
    table.add_column("Stmt\nTot.", justify="right")
    table.add_column("Stmt\nHit", justify="right")
    table.add_column("Stmt\nMiss", justify="right")
    table.add_column("Stmt\nCov.", justify="right")

    if show_branches:
        table.add_column("Branch\nTot.", justify="right")
        table.add_column("Branch\nHit", justify="right")
        table.add_column("Branch\nMiss", justify="right")
        table.add_column("Branch\nCov.", justify="right")

    for r in rows:
        if show_branches:
            table.add_row(*r)
        else:
            table.add_row(*r[:5])

    table.add_section()
    if show_branches:
        table.add_row(*totals)
    else:
        table.add_row(*totals[:5])
    return table


# --------------------------- Main --------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    del argv
    config = ReportConfig()

    roots = _read_all_coverage_roots(config.root, config.patterns)
    if not roots:
        return 0

    acc = _aggregate(roots, config.include, config.exclude)
    if not acc:
        return 0

    # Per-file
    rows_raw, totals = _summarize_files(acc)

    # Sorting
    keyfuncs = {
        "file": lambda r: (Path(r[0]), r[0]),
        "stmt_cov": lambda r: (-(r[4] or -1), r[0]),
        "br_cov": lambda r: (-(r[8] or -1), r[0]),
        "miss": lambda r: (-(r[3] + r[7]), r[0]),
    }
    rows_raw.sort(key=keyfuncs[config.sort])

    # Render rows
    stmt_cov_overall = (100.0 * totals.stmt_hit / totals.stmt_total) if totals.stmt_total else None
    br_cov_overall = (100.0 * totals.br_hit / totals.br_total) if totals.br_total else None

    def fmt_row(r):
        file_rel = _relativize(r[0], config.rel_to)
        return [
            file_rel,
            str(r[1]),
            str(r[2]),
            _style_miss(r[3]),
            _style_percent(r[4], config.green_threshold, config.yellow_threshold),
            str(r[5]),
            str(r[6]),
            _style_miss(r[7]),
            _style_percent(r[8], config.green_threshold, config.yellow_threshold),
        ]

    rows = [fmt_row(r) for r in rows_raw]

    totals = [
        "[bold]Overall[/bold]",
        f"[bold]{totals.stmt_total}[/bold]",
        f"[bold]{totals.stmt_hit}[/bold]",
        f"[bold]{totals.stmt_total - totals.stmt_hit}[/bold]",
        f"[bold]{_style_percent(stmt_cov_overall, config.green_threshold, config.yellow_threshold)}[/bold]",
        f"[bold]{totals.br_total}[/bold]",
        f"[bold]{totals.br_hit}[/bold]",
        f"[bold]{totals.br_total - totals.br_hit}[/bold]",
        f"[bold]{_style_percent(br_cov_overall, config.green_threshold, config.yellow_threshold)}[/bold]",
    ]

    console = Console()
    console.print()
    console.print(_build_table(rows, totals, show_branches=config.show_branches))
    console.print()

    # CI thresholds
    fail = False
    if config.fail_under_line is not None and (stmt_cov_overall or 0.0) < config.fail_under_line:
        fail = True
    if config.fail_under_branch is not None and (br_cov_overall or 0.0) < config.fail_under_branch:
        fail = True
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
