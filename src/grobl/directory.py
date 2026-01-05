"""Directory traversal helpers and tree rendering utilities."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

# Tree rendering glyphs are captured as constants to keep string literals
# consistent across the codebase and the tests that assert on them.
LAST_CONNECTOR = "└── "
BRANCH_CONNECTOR = "├── "


class TreeCallback(Protocol):
    """Directory traversal callback.

    Return True to descend into a directory, False to prune recursion.
    The `is_last` parameter is keyword-only to force call-site clarity.
    """

    def __call__(
        self,
        item: Path,
        prefix: str,
        *,
        is_last: bool,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class TraverseConfig:
    """Configuration controlling directory traversal filtering."""

    paths: list[Path]
    base: Path
    repo_root: Path

    def ordering_key(self, p: Path) -> str:
        """Deterministic ordering: POSIX relpath from repo_root, case-folded."""
        try:
            rel = p.relative_to(self.repo_root)
        except ValueError:
            # Caller should prevent this; fall back to absolute.
            rel = p
        return rel.as_posix().casefold()


@dataclass(slots=True)
class TreeCollector:
    _tree_output: list[str] = field(default_factory=list)
    _file_tree_entries: list[tuple[int, Path]] = field(default_factory=list)
    _ordered: list[tuple[str, Path]] = field(default_factory=list)

    def add_dir(self, base: Path, directory_path: Path, prefix: str, *, is_last: bool) -> None:
        """Record a directory in the rendered tree output."""
        connector = LAST_CONNECTOR if is_last else BRANCH_CONNECTOR
        self._tree_output.append(f"{prefix}{connector}{directory_path.name}/")
        rel = directory_path.relative_to(base)
        self._ordered.append(("dir", rel))

    def add_file(self, base: Path, file_path: Path, prefix: str, *, is_last: bool) -> None:
        """Record a file in the tree output and metadata structures."""
        connector = LAST_CONNECTOR if is_last else BRANCH_CONNECTOR
        rel = file_path.relative_to(base)
        self._tree_output.append(f"{prefix}{connector}{file_path.name}")
        self._file_tree_entries.append((len(self._tree_output) - 1, rel))
        self._ordered.append(("file", rel))

    def lines(self) -> list[str]:
        """Return a copy of the accumulated tree lines."""
        return list(self._tree_output)

    def entries(self) -> list[tuple[int, Path]]:
        """Return recorded file entries pairing tree index to relative path."""
        return list(self._file_tree_entries)

    def ordered(self) -> list[tuple[str, Path]]:
        """Return entries in visitation order tagged with their item type."""
        return list(self._ordered)


@dataclass(slots=True)
class FileCollector:
    """Store metadata and content for files encountered during traversal."""

    _metadata: dict[str, tuple[int, int, bool]] = field(default_factory=dict)
    _json_file_blobs: list[dict[str, Any]] = field(default_factory=list)

    def record_metadata(self, rel: Path, lines: int, chars: int) -> None:
        """Record line/character counts without capturing the file contents."""
        self._metadata[str(rel)] = (lines, chars, False)

    def add_file(self, file_path: Path, rel: Path, lines: int, chars: int, content: str) -> None:
        """Record metadata plus sanitized content for ``rel``."""
        self._metadata[str(rel)] = (lines, chars, True)
        if file_path.suffix == ".md":
            content = content.replace("```", r"\`\`\`")
        self._json_file_blobs.append({"name": str(rel), "lines": lines, "chars": chars, "content": content})

    def metadata_items(self) -> Iterable[tuple[str, tuple[int, int, bool]]]:
        """Yield recorded metadata keyed by relative path string."""
        return self._metadata.items()

    def get_metadata(self, key: str) -> tuple[int, int, bool] | None:
        """Return metadata for ``key`` if known."""
        return self._metadata.get(key)

    def files_json(self) -> list[dict[str, Any]]:
        """Return JSON-safe blobs describing captured files."""
        return list(self._json_file_blobs)


@dataclass(frozen=True, slots=True)
class FileSummary:
    """Immutable snapshot of per-file inclusion metadata."""

    lines: int
    chars: int
    included: bool

    def as_tuple(self) -> tuple[int, int, bool]:
        return self.lines, self.chars, self.included


@dataclass(frozen=True, slots=True)
class SummaryTotals:
    """Snapshot exposing totals and inclusion state from a builder."""

    total_lines: int
    total_characters: int
    all_total_lines: int
    all_total_characters: int
    _files: Mapping[str, FileSummary]
    _directories_with_files: frozenset[Path]
    _directories_with_included: frozenset[Path]

    def to_dict(self) -> dict[str, int]:
        return {
            "total_lines": self.total_lines,
            "total_characters": self.total_characters,
            "all_total_lines": self.all_total_lines,
            "all_total_characters": self.all_total_characters,
        }

    def iter_files(self) -> Iterable[tuple[str, FileSummary]]:
        return tuple(self._files.items())

    def metadata_items(self) -> Iterable[tuple[str, tuple[int, int, bool]]]:
        return tuple((path, record.as_tuple()) for path, record in self._files.items())

    def for_path(self, rel: str | Path) -> FileSummary | None:
        return self._files.get(str(rel))

    def is_included(self, rel: str | Path) -> bool:
        record = self.for_path(rel)
        return False if record is None else record.included

    def marker_for_file(self, rel: Path) -> str:
        return "[INCLUDED:FULL]" if self.is_included(rel) else "[NOT_INCLUDED]"

    def marker_for_directory(self, rel: Path) -> str | None:
        if rel in self._directories_with_files and rel not in self._directories_with_included:
            return "[NOT_INCLUDED]"
        return None


@dataclass(slots=True)
class TotalsTracker:
    """Mutable accumulator for inclusion and aggregate totals."""

    total_lines: int = 0
    total_characters: int = 0
    all_total_lines: int = 0
    all_total_characters: int = 0

    def record_seen(self, *, lines: int, chars: int) -> None:
        self.all_total_lines += lines
        self.all_total_characters += chars

    def record_included(self, *, lines: int, chars: int) -> None:
        self.total_lines += lines
        self.total_characters += chars

    def snapshot(self, metadata: Mapping[str, tuple[int, int, bool]]) -> SummaryTotals:
        files = {
            path: FileSummary(lines=ln, chars=ch, included=inc) for path, (ln, ch, inc) in metadata.items()
        }
        directories_with_files: set[Path] = set()
        directories_with_included: set[Path] = set()
        root = Path()
        for path_str, record in files.items():
            rel = Path(path_str)
            parent = rel.parent
            while parent != root:
                directories_with_files.add(parent)
                if record.included:
                    directories_with_included.add(parent)
                parent = parent.parent
        return SummaryTotals(
            total_lines=self.total_lines,
            total_characters=self.total_characters,
            all_total_lines=self.all_total_lines,
            all_total_characters=self.all_total_characters,
            _files=files,
            _directories_with_files=frozenset(directories_with_files),
            _directories_with_included=frozenset(directories_with_included),
        )


@dataclass(slots=True)  # "Use __slots__ to reduce memory if many nodes are created"
class DirectoryTreeBuilder:
    """Collect directory information (no rendering/formatting here)."""

    base_path: Path
    exclude_patterns: list[str]

    tree: TreeCollector = field(default_factory=TreeCollector)
    files: FileCollector = field(default_factory=FileCollector)
    _totals: TotalsTracker = field(default_factory=TotalsTracker)

    # ----- Read-only accessors (encapsulation) -----
    def tree_output(self) -> list[str]:
        """Expose the collected tree lines for rendering."""
        return self.tree.lines()

    def metadata_items(self) -> Iterable[tuple[str, tuple[int, int, bool]]]:
        """Iterate over the recorded file metadata."""
        return self.files.metadata_items()

    def get_metadata(self, key: str) -> tuple[int, int, bool] | None:
        """Return stored metadata for ``key`` if it exists."""
        return self.files.get_metadata(key)

    def file_tree_entries(self) -> list[tuple[int, Path]]:
        """Return tree indices paired with file paths for later augmentation."""
        return self.tree.entries()

    def ordered_entries(self) -> list[tuple[str, Path]]:
        """Return ordered entries as ("dir"|"file", relpath)."""
        return self.tree.ordered()

    def files_json(self) -> list[dict[str, Any]]:
        """Return JSON payloads for included files."""
        return self.files.files_json()

    # ----- Mutators (internal use) -----
    def add_directory(
        self,
        directory_path: Path,
        prefix: str,
        *,
        is_last: bool,
    ) -> None:
        """Record a directory in the tree output."""
        self.tree.add_dir(self.base_path, directory_path, prefix, is_last=is_last)

    def add_file_to_tree(
        self,
        file_path: Path,
        prefix: str,
        *,
        is_last: bool,
    ) -> None:
        """Add a file entry to the tree without storing its contents."""
        self.tree.add_file(self.base_path, file_path, prefix, is_last=is_last)

    def record_metadata(
        self,
        rel: Path,
        lines: int,
        chars: int,
    ) -> None:
        """Record line/char counts for a file and update ALL-file totals."""
        self.files.record_metadata(rel, lines, chars)
        self._totals.record_seen(lines=lines, chars=chars)

    def add_file(
        self,
        file_path: Path,
        rel: Path,
        lines: int,
        chars: int,
        content: str,
    ) -> None:
        """Store file metadata and content for output (collection only)."""
        self.files.add_file(file_path, rel, lines, chars, content)
        self._totals.record_included(lines=lines, chars=chars)

    def summary_totals(self) -> SummaryTotals:
        """Return a snapshot exposing totals and inclusion metadata."""
        metadata = dict(self.files.metadata_items())
        return self._totals.snapshot(metadata)


def filter_items(items: list[Path], config: TraverseConfig) -> list[Path]:
    """Filter ``items`` to those relevant to the requested paths; ordering is deterministic.

    Include:
      - items under any requested scan path
      - ancestors of any requested scan path (so we can descend from repo_root)
    """
    results: list[Path] = []
    for item in items:
        if not any(item.is_relative_to(p) or p.is_relative_to(item) for p in config.paths):
            continue
        results.append(item)
    return sorted(results, key=config.ordering_key)


def traverse_dir(
    path: Path,
    config: TraverseConfig,
    callback: TreeCallback,
    prefix: str = "",
) -> None:
    """Depth-first traversal applying ``callback`` to each item."""
    items = filter_items(list(path.iterdir()), config)
    for idx, item in enumerate(items):
        is_last = idx == len(items) - 1
        should_descend = callback(item, prefix, is_last=is_last)

        # Do not follow directory symlinks by default to avoid cycles
        if item.is_dir() and not item.is_symlink() and should_descend:
            next_prefix = "    " if is_last else "│   "
            traverse_dir(item, config, callback, prefix + next_prefix)
