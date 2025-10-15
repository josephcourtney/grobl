"""Directory traversal helpers and tree rendering utilities."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast

from pathspec import PathSpec

# Tree rendering glyphs are captured as constants to keep string literals
# consistent across the codebase and the tests that assert on them.
LAST_CONNECTOR = "└── "
BRANCH_CONNECTOR = "├── "
CONFIG_WITHOUT_SPEC_LENGTH = 3


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
    _file_contents: list[str] = field(default_factory=list)

    def record_metadata(self, rel: Path, lines: int, chars: int) -> None:
        """Record line/character counts without capturing the file contents."""
        self._metadata[str(rel)] = (lines, chars, False)

    def add_file(self, file_path: Path, rel: Path, lines: int, chars: int, content: str) -> None:
        """Record metadata plus sanitized content for ``rel``."""
        self._metadata[str(rel)] = (lines, chars, True)
        if file_path.suffix == ".md":
            content = content.replace("```", r"\`\`\`")
        self._file_contents.extend([
            (f'<file:content name="{rel}" lines="{lines}" chars="{chars}">'),
            content,
            "</file:content>",
        ])

    def metadata_items(self) -> Iterable[tuple[str, tuple[int, int, bool]]]:
        """Yield recorded metadata keyed by relative path string."""
        return self._metadata.items()

    def get_metadata(self, key: str) -> tuple[int, int, bool] | None:
        """Return metadata for ``key`` if known."""
        return self._metadata.get(key)

    def contents(self) -> list[str]:
        """Return captured file content payloads for rendering."""
        return list(self._file_contents)


@dataclass(slots=True)
class BinaryCollector:
    """Maintain metadata about binary files encountered during traversal."""

    _details: dict[str, dict] = field(default_factory=dict)

    def record(self, rel: Path, details: dict) -> None:
        """Store ``details`` for the binary file located at ``rel``."""
        self._details[str(rel)] = dict(details)

    def get(self, key: str) -> dict | None:
        """Return stored metadata for ``key`` if available."""
        return self._details.get(key)


@dataclass(slots=True)  # "Use __slots__ to reduce memory if many nodes are created"
class DirectoryTreeBuilder:
    """Collect directory information (no rendering/formatting here)."""

    base_path: Path
    exclude_patterns: list[str]

    tree: TreeCollector = field(default_factory=TreeCollector)
    files: FileCollector = field(default_factory=FileCollector)
    binaries: BinaryCollector = field(default_factory=BinaryCollector)

    # Totals
    total_lines: int = 0
    total_characters: int = 0
    all_total_lines: int = 0
    all_total_characters: int = 0

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

    def file_contents(self) -> list[str]:
        """Return captured file content payloads."""
        return self.files.contents()

    def file_tree_entries(self) -> list[tuple[int, Path]]:
        """Return tree indices paired with file paths for later augmentation."""
        return self.tree.entries()

    def get_binary_details(self, key: str) -> dict | None:
        """Return binary metadata for ``key`` if known."""
        return self.binaries.get(key)

    def ordered_entries(self) -> list[tuple[str, Path]]:
        """Return ordered entries as ("dir"|"file", relpath)."""
        return self.tree.ordered()

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
        self.files.add_file(file_path, rel, lines, chars, content)
        self.total_lines += lines
        self.total_characters += chars

    def record_binary_details(self, rel: Path, details: dict) -> None:
        """Record metadata about a binary artifact at ``rel``."""
        self.binaries.record(rel, details)


def _to_git_path(p: Path, *, is_dir: bool) -> str:
    """Return POSIX-like path string suitable for gitignore matching.

    For directories, append a trailing slash to preserve directory-only patterns.
    """
    s = p.as_posix()
    return s + ("/" if is_dir and not s.endswith("/") else "")


def filter_items(
    items: list[Path], paths: list[Path], patterns: list[str], base: Path, spec: PathSpec | None = None
) -> list[Path]:
    """Filter ``items`` against ``paths`` and ``patterns`` using gitignore semantics."""
    # Compile once per call if not provided (keeps backward compatibility for direct calls in tests)
    spec = spec or PathSpec.from_lines("gitwildmatch", patterns)
    results: list[Path] = []
    for item in items:
        if not any(item.is_relative_to(p) for p in paths):
            continue
        rel = item.relative_to(base)
        rel_git = _to_git_path(rel, is_dir=item.is_dir())
        if spec.match_file(rel_git):
            continue
        results.append(item)
    return sorted(results, key=lambda x: x.name)


def traverse_dir(
    path: Path,
    config: tuple[list[Path], list[str], Path] | tuple[list[Path], list[str], Path, PathSpec],
    callback: TreeCallback,
    prefix: str = "",
) -> None:
    """Depth-first traversal applying ``callback`` to each item."""
    if len(config) == CONFIG_WITHOUT_SPEC_LENGTH:
        paths, patterns, base = cast(tuple[list[Path], list[str], Path], config)  # noqa: TC006 - runtime tuple unpacking
        spec: PathSpec | None = None
    else:
        paths, patterns, base, spec = cast(tuple[list[Path], list[str], Path, PathSpec], config)  # noqa: TC006 - runtime tuple unpacking
    items = filter_items(list(path.iterdir()), paths, patterns, base, spec)
    for idx, item in enumerate(items):
        is_last = idx == len(items) - 1
        callback(item, prefix, is_last=is_last)
        # Do not follow directory symlinks by default to avoid cycles
        if item.is_dir() and not item.is_symlink():
            next_prefix = "    " if is_last else "│   "
            traverse_dir(item, config, callback, prefix + next_prefix)
