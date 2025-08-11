"""Directory traversal helpers and tree rendering utilities."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class TreeCallback(Protocol):
    """Directory traversal callback.

    The `is_last` parameter is keyword-only to force call-site clarity.
    """

    def __call__(
        self,
        item: Path,
        prefix: str,
        *,
        is_last: bool,
    ) -> None: ...


@dataclass(slots=True)  # "Use __slots__ to reduce memory if many nodes are created"
class DirectoryTreeBuilder:
    """Collect directory information (no rendering/formatting here)."""

    base_path: Path
    exclude_patterns: list[str]

    # -- Internal state (prefixed) --
    _tree_output: list[str] = field(default_factory=list)
    _metadata: dict[str, tuple[int, int, bool]] = field(default_factory=dict)
    _file_contents: list[str] = field(default_factory=list)
    _file_tree_entries: list[tuple[int, Path]] = field(default_factory=list)

    # "Totals for included files (backward compatible fields used by summary)."
    total_lines: int = 0
    total_characters: int = 0

    # "Totals for all files seen (text and binary), derived in record_metadata."
    all_total_lines: int = 0
    all_total_characters: int = 0

    # ----- Read-only accessors (encapsulation) -----
    def tree_output(self) -> list[str]:
        return list(self._tree_output)

    def metadata_items(self) -> Iterable[tuple[str, tuple[int, int, bool]]]:
        return self._metadata.items()

    def get_metadata(self, key: str) -> tuple[int, int, bool] | None:
        return self._metadata.get(key)

    def file_contents(self) -> list[str]:
        return list(self._file_contents)

    def file_tree_entries(self) -> list[tuple[int, Path]]:
        return list(self._file_tree_entries)

    # ----- Mutators (internal use) -----
    def add_directory(
        self,
        directory_path: Path,
        prefix: str,
        *,
        is_last: bool,
    ) -> None:
        """Record a directory in the tree output."""
        connector = "└── " if is_last else "├── "
        self._tree_output.append(f"{prefix}{connector}{directory_path.name}")

    def add_file_to_tree(
        self,
        file_path: Path,
        prefix: str,
        *,
        is_last: bool,
    ) -> None:
        """Add a file entry to the tree without storing its contents."""
        connector = "└── " if is_last else "├── "
        rel = file_path.relative_to(self.base_path)
        self._tree_output.append(f"{prefix}{connector}{file_path.name}")
        self._file_tree_entries.append((len(self._tree_output) - 1, rel))

    def record_metadata(
        self,
        rel: Path,
        lines: int,
        chars: int,
    ) -> None:
        """Record line/char counts for a file and update ALL-file totals."""
        key = str(rel)
        self._metadata[key] = (lines, chars, False)
        self.all_total_lines += lines
        self.all_total_characters += chars

    def add_file(
        self,
        file_path: Path,
        rel: Path,
        lines: int,
        chars: int,
        content: str,
    ) -> None:
        """Store file metadata and content for output (collection only)."""
        self._metadata[str(rel)] = (lines, chars, True)
        if file_path.suffix == ".md":
            content = content.replace("```", r"\`\`\`")
        self._file_contents.extend([
            (f'<file:content name="{rel}" lines="{lines}" chars="{chars}">'),
            content,
            "</file:content>",
        ])
        self.total_lines += lines
        self.total_characters += chars


def filter_items(items: list[Path], paths: list[Path], patterns: list[str], base: Path) -> list[Path]:
    """Filter ``items`` against ``paths`` and ``patterns``."""
    results: list[Path] = []
    for item in items:
        if not any(item.is_relative_to(p) for p in paths):
            continue
        if any(item.relative_to(base).match(pat) for pat in patterns):
            continue
        results.append(item)
    return sorted(results, key=lambda x: x.name)


def traverse_dir(
    path: Path,
    config: tuple[list[Path], list[str], Path],
    callback: TreeCallback,
    prefix: str = "",
) -> None:
    """Depth-first traversal applying ``callback`` to each item."""
    paths, patterns, base = config
    items = filter_items(list(path.iterdir()), paths, patterns, base)
    for idx, item in enumerate(items):
        is_last = idx == len(items) - 1
        callback(item, prefix, is_last=is_last)
        if item.is_dir():
            next_prefix = "    " if is_last else "│   "
            traverse_dir(item, config, callback, prefix + next_prefix)
